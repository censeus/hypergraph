# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Static AST-based codebase parser for extracting structural knowledge graphs.

Walks a directory of Python source files and extracts entities (modules, classes,
functions, methods) and relationships (imports, containment, inheritance, calls,
decorators) into DataFrames compatible with Hypergraph's entity/relationship schema.
"""

import ast
import fnmatch
import logging
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
    extract_calls: bool = True,
    extract_decorators: bool = True,
    max_depth: int | None = None,
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
    extract_calls:
        Whether to extract ``CALLS`` relationships.
    extract_decorators:
        Whether to extract ``DECORATES`` relationships.
    max_depth:
        Maximum directory depth to scan (``None`` = unlimited).

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

    for filepath in _walk_files(root, extensions, excludes, max_depth):
        try:
            source = filepath.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(filepath))
        except SyntaxError:
            logger.warning("Skipping file with syntax error: %s", filepath)
            continue

        module_name = _file_to_module_name(filepath, root)
        _extract_from_module(
            tree=tree,
            module_name=module_name,
            filepath=filepath,
            source=source,
            entities=entities,
            relationships=relationships,
            extract_calls=extract_calls,
            extract_decorators=extract_decorators,
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
    if len(relationships_df) == 0:
        logger.warning("No relationships extracted from codebase at %s", root)

    return entities_df, relationships_df


# ---------------------------------------------------------------------------
# File walking
# ---------------------------------------------------------------------------


def _walk_files(
    root: Path,
    extensions: list[str],
    exclude_patterns: list[str],
    max_depth: int | None,
) -> list[Path]:
    """Collect matching source files under *root*."""
    files: list[Path] = []
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

        files.append(path)

    return files


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


# ---------------------------------------------------------------------------
# AST extraction
# ---------------------------------------------------------------------------


def _extract_from_module(
    tree: ast.Module,
    module_name: str,
    filepath: Path,
    source: str,
    entities: list[dict],
    relationships: list[dict],
    extract_calls: bool,
    extract_decorators: bool,
) -> None:
    """Extract entities and relationships from a single parsed module."""
    source_id = module_name

    # Module entity
    module_doc = ast.get_docstring(tree) or ""
    entities.append({
        "title": module_name,
        "type": "MODULE",
        "description": _truncate(module_doc, 500) or f"Module: {filepath.name}",
        "source_id": source_id,
    })

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            _extract_class(
                node,
                module_name=module_name,
                source_id=source_id,
                entities=entities,
                relationships=relationships,
                extract_calls=extract_calls,
                extract_decorators=extract_decorators,
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _extract_function(
                node,
                parent_name=module_name,
                entity_type="FUNCTION",
                source_id=source_id,
                entities=entities,
                relationships=relationships,
                extract_calls=extract_calls,
                extract_decorators=extract_decorators,
            )
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            _extract_import(
                node,
                module_name=module_name,
                source_id=source_id,
                relationships=relationships,
            )


def _extract_class(
    node: ast.ClassDef,
    module_name: str,
    source_id: str,
    entities: list[dict],
    relationships: list[dict],
    extract_calls: bool,
    extract_decorators: bool,
) -> None:
    """Extract a class entity plus its methods and relationships."""
    class_fqn = f"{module_name}.{node.name}"
    class_doc = ast.get_docstring(node) or ""
    bases = [_name_from_node(base) for base in node.bases]
    bases_str = ", ".join(b for b in bases if b)

    description = class_doc or f"Class {node.name}"
    if bases_str:
        description += f" (extends: {bases_str})"

    entities.append({
        "title": class_fqn,
        "type": "CLASS",
        "description": _truncate(description, 500),
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
            # Try to resolve base within same module
            base_fqn = f"{module_name}.{base_name}" if "." not in base_name else base_name
            relationships.append({
                "source": class_fqn,
                "target": base_fqn,
                "description": f"inherits: {node.name} extends {base_name}",
                "weight": 1.0,
                "source_id": source_id,
            })

    # Decorators
    if extract_decorators:
        for decorator in node.decorator_list:
            dec_name = _name_from_node(decorator)
            if dec_name:
                relationships.append({
                    "source": dec_name,
                    "target": class_fqn,
                    "description": f"decorates: @{dec_name} decorates {node.name}",
                    "weight": 1.0,
                    "source_id": source_id,
                })

    # Methods
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _extract_function(
                item,
                parent_name=class_fqn,
                entity_type="METHOD",
                source_id=source_id,
                entities=entities,
                relationships=relationships,
                extract_calls=extract_calls,
                extract_decorators=extract_decorators,
            )


def _extract_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    parent_name: str,
    entity_type: str,
    source_id: str,
    entities: list[dict],
    relationships: list[dict],
    extract_calls: bool,
    extract_decorators: bool,
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

    # Decorators
    if extract_decorators:
        for decorator in node.decorator_list:
            dec_name = _name_from_node(decorator)
            if dec_name:
                relationships.append({
                    "source": dec_name,
                    "target": func_fqn,
                    "description": f"decorates: @{dec_name} decorates {node.name}",
                    "weight": 1.0,
                    "source_id": source_id,
                })

    # CALLS: best-effort static call extraction
    if extract_calls:
        seen_calls: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                callee = _name_from_node(child.func)
                if callee and callee not in seen_calls:
                    seen_calls.add(callee)
                    relationships.append({
                        "source": func_fqn,
                        "target": callee,
                        "description": f"calls: {node.name} calls {callee}",
                        "weight": 0.5,
                        "source_id": source_id,
                    })


def _extract_import(
    node: ast.Import | ast.ImportFrom,
    module_name: str,
    source_id: str,
    relationships: list[dict],
) -> None:
    """Extract IMPORTS relationships from import statements."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            relationships.append({
                "source": module_name,
                "target": alias.name,
                "description": f"imports: {module_name} imports {alias.name}",
                "weight": 1.0,
                "source_id": source_id,
            })
    elif isinstance(node, ast.ImportFrom) and node.module:
        relationships.append({
            "source": module_name,
            "target": node.module,
            "description": f"imports: {module_name} imports from {node.module}",
            "weight": 1.0,
            "source_id": source_id,
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

    # Positional args
    for arg in args.args:
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
