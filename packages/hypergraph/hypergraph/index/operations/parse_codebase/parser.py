# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Hierarchical AST-based codebase parser for extracting structural knowledge graphs.

Walks a directory of Python source files and extracts a 4-level hierarchy:
  PACKAGE → MODULE → CLASS → METHOD/FUNCTION

Relationships:
  CONTAINS  — structural parent→child
  DEPENDS_ON — package→package (aggregated from imports)
  IMPORTS   — module→module
  INHERITS  — class→class
"""

import ast
import fnmatch
import logging
from collections import defaultdict
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_codebase(
    root_dir: str | Path,
    file_extensions: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    skip_tests: bool = True,
    max_depth: int | None = None,
    file_filter: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse a codebase directory and return entity / relationship DataFrames.

    Parameters
    ----------
    root_dir:
        Root directory to scan.
    file_extensions:
        File extensions to include (default: ``[".py"]``).
    exclude_patterns:
        Glob patterns for paths to skip (matched against relative paths).
    skip_tests:
        Whether to skip test files (``test_*.py``, ``*_test.py``).
    max_depth:
        Maximum directory depth to scan (``None`` = unlimited).
    file_filter:
        If provided, only parse files whose relative paths are in this list.
        Used for diff-only indexing (e.g., branch comparisons).

    Returns
    -------
    tuple of (entities_df, relationships_df)
        DataFrames with columns compatible with Hypergraph's extract_graph output.
    """
    root = Path(root_dir).resolve()
    if not root.is_dir():
        msg = f"Root directory does not exist: {root}"
        raise FileNotFoundError(msg)

    extensions = file_extensions or [".py"]
    excludes = exclude_patterns or [
        "**/venv/**",
        "**/.venv/**",
        "**/__pycache__/**",
        "**/node_modules/**",
        "**/.git/**",
        "**/.tox/**",
        "**/dist/**",
        "**/*.egg-info/**",
    ]

    entities: list[dict] = []
    relationships: list[dict] = []
    # Track which modules belong to which package, and module-level imports
    package_modules: dict[str, list[str]] = defaultdict(list)
    module_imports: dict[str, set[str]] = defaultdict(set)

    # ── Step 1: Discover packages ──
    _discover_packages(root, extensions, excludes, max_depth, entities)

    # ── Step 2: Parse each source file ──
    for filepath in _walk_files(root, extensions, excludes, max_depth, skip_tests, file_filter):
        try:
            source = filepath.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(filepath))
        except SyntaxError:
            logger.warning("Skipping file with syntax error: %s", filepath)
            continue

        module_name = _file_to_module_name(filepath, root)
        package_name = _module_to_package(module_name)

        # Track package→module mapping
        if package_name:
            package_modules[package_name].append(module_name)

        _extract_from_module(
            tree=tree,
            module_name=module_name,
            filepath=filepath,
            entities=entities,
            relationships=relationships,
            module_imports=module_imports,
        )

    # ── Step 3: Add PACKAGE→MODULE CONTAINS relationships ──
    for pkg, modules in package_modules.items():
        for mod in modules:
            relationships.append({
                "source": pkg,
                "target": mod,
                "description": f"contains: package {pkg} contains module {mod.split('.')[-1]}",
                "weight": 1.0,
                "source_id": pkg,
            })

    # ── Step 4: Build PACKAGE→PACKAGE DEPENDS_ON ──
    _build_package_dependencies(
        module_imports=module_imports,
        package_modules=package_modules,
        relationships=relationships,
    )

    entities_df = pd.DataFrame(
        entities, columns=["title", "type", "description", "source_id"]
    )
    relationships_df = pd.DataFrame(
        relationships,
        columns=["source", "target", "description", "weight", "source_id"],
    )

    if len(entities_df) == 0:
        logger.warning("No entities extracted from codebase at %s", root)

    return entities_df, relationships_df


# ---------------------------------------------------------------------------
# File walking & package discovery
# ---------------------------------------------------------------------------


def _walk_files(
    root: Path,
    extensions: list[str],
    exclude_patterns: list[str],
    max_depth: int | None,
    skip_tests: bool = True,
    file_filter: list[str] | None = None,
) -> list[Path]:
    """Collect matching source files under *root*."""
    # If file_filter is provided, resolve those paths directly
    if file_filter is not None:
        files: list[Path] = []
        for rel_path in sorted(file_filter):
            path = root / rel_path
            if not path.is_file():
                continue
            if path.suffix not in extensions:
                continue
            if skip_tests and _is_test_file(path):
                continue
            files.append(path)
        return files

    files = []
    root_depth = len(root.parts)

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in extensions:
            continue

        # depth check
        if max_depth is not None:
            depth = len(path.parts) - root_depth
            if depth > max_depth:
                continue

        relative = str(path.relative_to(root))
        if any(fnmatch.fnmatch(relative, pat) for pat in exclude_patterns):
            continue

        # Skip test files
        if skip_tests and _is_test_file(path):
            continue

        files.append(path)

    return files


def _is_test_file(path: Path) -> bool:
    """Check if a file is a test file based on its name."""
    name = path.stem
    return (
        name.startswith("test_")
        or name.endswith("_test")
        or name == "conftest"
    )


def _discover_packages(
    root: Path,
    extensions: list[str],
    exclude_patterns: list[str],
    max_depth: int | None,
    entities: list[dict],
) -> None:
    """Create PACKAGE entities for directories that contain Python files."""
    root_depth = len(root.parts)
    seen_packages: set[str] = set()

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in extensions:
            continue

        relative = str(path.relative_to(root))
        if any(fnmatch.fnmatch(relative, pat) for pat in exclude_patterns):
            continue

        if max_depth is not None:
            depth = len(path.parts) - root_depth
            if depth > max_depth:
                continue

        # Build package names from the directory chain
        rel_dir = path.parent.relative_to(root)
        parts = list(rel_dir.parts)

        # Create package entities for each level in the path
        for i in range(len(parts)):
            pkg_name = ".".join(parts[: i + 1])
            if pkg_name and pkg_name not in seen_packages:
                seen_packages.add(pkg_name)

                # Try to read package docstring from __init__.py
                init_path = root / "/".join(parts[: i + 1]) / "__init__.py"
                pkg_doc = ""
                if init_path.exists():
                    try:
                        source = init_path.read_text(encoding="utf-8", errors="replace")
                        tree = ast.parse(source)
                        pkg_doc = ast.get_docstring(tree) or ""
                    except SyntaxError:
                        pass

                entities.append({
                    "title": pkg_name,
                    "type": "PACKAGE",
                    "description": _truncate(pkg_doc, 500) or f"Package: {pkg_name}",
                    "source_id": pkg_name,
                })


def _file_to_module_name(filepath: Path, root: Path) -> str:
    """Convert a file path to a dotted Python module name."""
    relative = filepath.relative_to(root)
    parts = list(relative.parts)
    # Strip .py extension from the last part
    if parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    # __init__ -> use parent package name only
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else filepath.stem


def _module_to_package(module_name: str) -> str:
    """Get the immediate parent package of a module."""
    parts = module_name.rsplit(".", 1)
    return parts[0] if len(parts) > 1 else ""


# ---------------------------------------------------------------------------
# AST extraction
# ---------------------------------------------------------------------------


def _extract_from_module(
    tree: ast.Module,
    module_name: str,
    filepath: Path,
    entities: list[dict],
    relationships: list[dict],
    module_imports: dict[str, set[str]],
) -> None:
    """Extract entities and relationships from a single parsed module."""
    source_id = module_name

    # Collect top-level function names for the module description
    top_functions: list[str] = []
    top_classes: list[str] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            top_classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                top_functions.append(_build_signature(node))

    # Module entity with enriched description
    module_doc = ast.get_docstring(tree) or ""
    description_parts = [module_doc or f"Module: {filepath.name}"]
    if top_classes:
        description_parts.append(f"Classes: {', '.join(top_classes)}")
    if top_functions:
        description_parts.append("Functions: " + "; ".join(top_functions[:5]))
        if len(top_functions) > 5:
            description_parts.append(f"  ... and {len(top_functions) - 5} more")

    entities.append({
        "title": module_name,
        "type": "MODULE",
        "description": _truncate("\n".join(description_parts), 800),
        "source_id": source_id,
    })

    # Extract child entities
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            _extract_class(
                node,
                module_name=module_name,
                source_id=source_id,
                entities=entities,
                relationships=relationships,
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _extract_function(
                node,
                parent_name=module_name,
                entity_type="FUNCTION",
                source_id=source_id,
                entities=entities,
                relationships=relationships,
            )
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            _extract_import(
                node,
                module_name=module_name,
                source_id=source_id,
                relationships=relationships,
                module_imports=module_imports,
            )


def _extract_class(
    node: ast.ClassDef,
    module_name: str,
    source_id: str,
    entities: list[dict],
    relationships: list[dict],
) -> None:
    """Extract a class entity plus its methods and relationships."""
    class_fqn = f"{module_name}.{node.name}"
    class_doc = ast.get_docstring(node) or ""
    bases = [_name_from_node(base) for base in node.bases]
    bases_str = ", ".join(b for b in bases if b)

    # Collect method signatures for the class description
    methods: list[str] = []
    public_methods: list[str] = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = _build_signature(item)
            methods.append(item.name)
            if not item.name.startswith("_") or item.name == "__init__":
                public_methods.append(sig)

    # Build rich description
    desc_parts = []
    if class_doc:
        desc_parts.append(class_doc)
    else:
        desc_parts.append(f"Class {node.name}")
    if bases_str:
        desc_parts.append(f"Extends: {bases_str}")
    if public_methods:
        desc_parts.append("Methods: " + "; ".join(public_methods[:8]))
        if len(public_methods) > 8:
            desc_parts.append(f"  ... and {len(public_methods) - 8} more")

    entities.append({
        "title": class_fqn,
        "type": "CLASS",
        "description": _truncate("\n".join(desc_parts), 800),
        "source_id": source_id,
    })

    # CONTAINS: module -> class
    relationships.append({
        "source": module_name,
        "target": class_fqn,
        "description": f"contains: {module_name} defines {node.name}",
        "weight": 1.0,
        "source_id": source_id,
    })

    # INHERITS: child -> parent
    for base in node.bases:
        base_name = _name_from_node(base)
        if base_name:
            base_fqn = f"{module_name}.{base_name}" if "." not in base_name else base_name
            relationships.append({
                "source": class_fqn,
                "target": base_fqn,
                "description": f"inherits: {node.name} extends {base_name}",
                "weight": 1.0,
                "source_id": source_id,
            })

    # Methods as entities
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _extract_function(
                item,
                parent_name=class_fqn,
                entity_type="METHOD",
                source_id=source_id,
                entities=entities,
                relationships=relationships,
            )


def _extract_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    parent_name: str,
    entity_type: str,
    source_id: str,
    entities: list[dict],
    relationships: list[dict],
) -> None:
    """Extract a function/method entity and its relationships."""
    func_fqn = f"{parent_name}.{node.name}"
    func_doc = ast.get_docstring(node) or ""
    signature = _build_signature(node)

    description = func_doc or f"{entity_type.title()} {node.name}"
    if signature:
        description = f"``{signature}``\n{description}"

    entities.append({
        "title": func_fqn,
        "type": entity_type,
        "description": _truncate(description, 500),
        "source_id": source_id,
    })

    # CONTAINS: parent -> function
    relationships.append({
        "source": parent_name,
        "target": func_fqn,
        "description": f"contains: {parent_name} defines {node.name}",
        "weight": 1.0,
        "source_id": source_id,
    })


def _extract_import(
    node: ast.Import | ast.ImportFrom,
    module_name: str,
    source_id: str,
    relationships: list[dict],
    module_imports: dict[str, set[str]],
) -> None:
    """Extract IMPORTS relationships from import statements."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            module_imports[module_name].add(alias.name)
            relationships.append({
                "source": module_name,
                "target": alias.name,
                "description": f"imports: {module_name} imports {alias.name}",
                "weight": 1.0,
                "source_id": source_id,
            })
    elif isinstance(node, ast.ImportFrom) and node.module:
        module_imports[module_name].add(node.module)
        relationships.append({
            "source": module_name,
            "target": node.module,
            "description": f"imports: {module_name} imports from {node.module}",
            "weight": 1.0,
            "source_id": source_id,
        })


def _build_package_dependencies(
    module_imports: dict[str, set[str]],
    package_modules: dict[str, list[str]],
    relationships: list[dict],
) -> None:
    """Build PACKAGE→PACKAGE DEPENDS_ON by aggregating module imports."""
    # Build reverse map: module → package
    module_to_pkg: dict[str, str] = {}
    for pkg, modules in package_modules.items():
        for mod in modules:
            module_to_pkg[mod] = pkg

    # Count inter-package dependencies
    pkg_deps: dict[tuple[str, str], int] = defaultdict(int)
    for module, imports in module_imports.items():
        src_pkg = module_to_pkg.get(module)
        if not src_pkg:
            continue
        for imp in imports:
            # Find the package of the imported module
            tgt_pkg = module_to_pkg.get(imp)
            if not tgt_pkg:
                # Try prefix matching (e.g., import from sub-module)
                for known_mod, known_pkg in module_to_pkg.items():
                    if imp.startswith(known_mod) or known_mod.startswith(imp):
                        tgt_pkg = known_pkg
                        break
            if tgt_pkg and tgt_pkg != src_pkg:
                pkg_deps[(src_pkg, tgt_pkg)] += 1

    for (src, tgt), count in pkg_deps.items():
        relationships.append({
            "source": src,
            "target": tgt,
            "description": f"depends_on: {src} depends on {tgt} ({count} imports)",
            "weight": min(count / 5.0, 3.0),  # Scale weight by import count
            "source_id": src,
        })


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _name_from_node(node: ast.expr) -> str | None:
    """Extract a dotted name from an AST expression node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        value = _name_from_node(node.value)
        if value:
            return f"{value}.{node.attr}"
        return node.attr
    if isinstance(node, ast.Call):
        return _name_from_node(node.func)
    return None


def _build_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Build a human-readable function signature string."""
    args = node.args
    parts: list[str] = []

    # Positional args (skip 'self' and 'cls')
    for arg in args.args:
        if arg.arg in ("self", "cls"):
            continue
        annotation = _annotation_str(arg.annotation)
        name = arg.arg
        parts.append(f"{name}: {annotation}" if annotation else name)

    # *args
    if args.vararg:
        annotation = _annotation_str(args.vararg.annotation)
        name = f"*{args.vararg.arg}"
        parts.append(f"{name}: {annotation}" if annotation else name)

    # **kwargs
    if args.kwarg:
        annotation = _annotation_str(args.kwarg.annotation)
        name = f"**{args.kwarg.arg}"
        parts.append(f"{name}: {annotation}" if annotation else name)

    return_annotation = _annotation_str(node.returns)
    sig = f"{node.name}({', '.join(parts)})"
    if return_annotation:
        sig += f" -> {return_annotation}"

    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
    return prefix + sig


def _annotation_str(node: ast.expr | None) -> str:
    """Best-effort stringification of a type annotation AST node."""
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to *max_len* characters."""
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
