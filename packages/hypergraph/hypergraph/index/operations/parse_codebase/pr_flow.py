# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""PR/Branch review flow analyzer.

Parses a git diff between two refs, builds a dependency-ordered review guide
showing which files to read first and what leads to what.
"""

import ast
import logging
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FileReview:
    """A single file in the review flow."""

    path: str
    layer: int = 0
    entity_summary: str = ""
    depends_on: list[str] = field(default_factory=list)
    depended_by: list[str] = field(default_factory=list)
    diff_stat: str = ""
    change_type: str = "modified"  # added, modified, deleted, renamed


@dataclass
class PRFlowResult:
    """Complete PR review flow result."""

    base_ref: str
    head_ref: str
    files: list[FileReview] = field(default_factory=list)
    layers: dict[int, list[str]] = field(default_factory=dict)
    total_files: int = 0


def parse_pr_flow(
    repo_dir: str | Path,
    base_ref: str = "main",
    head_ref: str = "HEAD",
    extensions: list[str] | None = None,
) -> PRFlowResult:
    """Analyze a PR/branch and produce a dependency-ordered review flow.

    Parameters
    ----------
    repo_dir:
        Path to the git repository root.
    base_ref:
        Base reference (e.g., 'main', 'origin/main').
    head_ref:
        Head reference (e.g., 'HEAD', 'feature-branch').
    extensions:
        File extensions to analyze (default: ['.py']).

    Returns
    -------
    PRFlowResult with files ordered by review priority.
    """
    repo = Path(repo_dir).resolve()
    exts = extensions or [".py"]

    # Step 1: Get changed files
    changed_files = _get_changed_files(repo, base_ref, head_ref)
    if not changed_files:
        return PRFlowResult(base_ref=base_ref, head_ref=head_ref)

    # Filter to relevant extensions
    relevant_files = {
        path: status
        for path, status in changed_files.items()
        if any(path.endswith(ext) for ext in exts)
    }

    # Step 2: Get diff stats per file
    diff_stats = _get_diff_stats(repo, base_ref, head_ref)

    # Step 3: Parse imports from the HEAD version of each file
    file_imports: dict[str, set[str]] = {}
    file_summaries: dict[str, str] = {}

    for filepath, status in relevant_files.items():
        if status == "D":
            file_summaries[filepath] = "DELETED"
            file_imports[filepath] = set()
            continue

        full_path = repo / filepath
        if not full_path.exists():
            continue

        try:
            source = full_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=filepath)
            file_imports[filepath] = _extract_import_targets(tree)
            file_summaries[filepath] = _summarize_file(tree, filepath)
        except SyntaxError:
            logger.warning("Skipping file with syntax error: %s", filepath)
            file_imports[filepath] = set()
            file_summaries[filepath] = "(syntax error)"

    # Step 4: Build dependency DAG between changed files
    # Map module paths to file paths for matching
    file_to_module = {}
    module_to_file = {}
    for filepath in relevant_files:
        module = _filepath_to_module(filepath)
        file_to_module[filepath] = module

        # Map all possible module name candidates to this file
        for candidate in _filepath_module_candidates(filepath):
            if candidate not in module_to_file:
                module_to_file[candidate] = filepath

    # edges: dependency → dependent (read dependency first)
    edges: dict[str, set[str]] = defaultdict(set)
    reverse_edges: dict[str, set[str]] = defaultdict(set)

    for filepath, imports in file_imports.items():
        for imp in imports:
            # Check if the import refers to another changed file
            target_file = _resolve_import_to_file(imp, module_to_file)
            if target_file and target_file != filepath and target_file in relevant_files:
                edges[target_file].add(filepath)
                reverse_edges[filepath].add(target_file)

    # Step 5: Topological sort → layer assignment
    layers = _topological_layers(set(relevant_files.keys()), edges)

    # Step 6: Build result
    file_reviews: list[FileReview] = []
    layer_map: dict[int, list[str]] = defaultdict(list)

    for filepath, status in relevant_files.items():
        layer = layers.get(filepath, 0)
        review = FileReview(
            path=filepath,
            layer=layer,
            entity_summary=file_summaries.get(filepath, ""),
            depends_on=sorted(reverse_edges.get(filepath, set())),
            depended_by=sorted(edges.get(filepath, set())),
            diff_stat=diff_stats.get(filepath, ""),
            change_type=_status_to_change_type(status),
        )
        file_reviews.append(review)
        layer_map[layer].append(filepath)

    # Sort by layer, then by path within layer
    file_reviews.sort(key=lambda f: (f.layer, f.path))

    return PRFlowResult(
        base_ref=base_ref,
        head_ref=head_ref,
        files=file_reviews,
        layers=dict(layer_map),
        total_files=len(file_reviews),
    )


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_changed_files(repo: Path, base: str, head: str) -> dict[str, str]:
    """Get changed files between two refs: {filepath: status}."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-status", f"{base}...{head}"],
            capture_output=True,
            text=True,
            cwd=repo,
            check=True,
        )
    except subprocess.CalledProcessError:
        # Try without three-dot merge-base syntax
        try:
            result = subprocess.run(
                ["git", "diff", "--name-status", f"{base}..{head}"],
                capture_output=True,
                text=True,
                cwd=repo,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error("git diff failed: %s", e.stderr)
            return {}

    files = {}
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0][0]  # First char: A, M, D, R
            filepath = parts[-1]  # Last part (handles renames)
            files[filepath] = status
    return files


def _get_diff_stats(repo: Path, base: str, head: str) -> dict[str, str]:
    """Get per-file diff stats: {filepath: '+N -M'}."""
    try:
        result = subprocess.run(
            ["git", "diff", "--numstat", f"{base}...{head}"],
            capture_output=True,
            text=True,
            cwd=repo,
            check=True,
        )
    except subprocess.CalledProcessError:
        try:
            result = subprocess.run(
                ["git", "diff", "--numstat", f"{base}..{head}"],
                capture_output=True,
                text=True,
                cwd=repo,
                check=True,
            )
        except subprocess.CalledProcessError:
            return {}

    stats = {}
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            added, removed, filepath = parts[0], parts[1], parts[2]
            stats[filepath] = f"+{added} -{removed}"
    return stats


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _extract_import_targets(tree: ast.Module) -> set[str]:
    """Extract import module names from an AST."""
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _summarize_file(tree: ast.Module, filepath: str) -> str:
    """Build a concise summary of a file's contents."""
    parts = []
    module_doc = ast.get_docstring(tree)
    if module_doc:
        # First line of docstring
        parts.append(module_doc.split("\n")[0].strip())

    classes = []
    functions = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            methods = [
                n.name
                for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not n.name.startswith("_")
            ]
            method_str = f" ({', '.join(methods[:3])}{'...' if len(methods) > 3 else ''})" if methods else ""
            classes.append(f"{node.name}{method_str}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                functions.append(node.name)

    if classes:
        parts.append(f"Classes: {', '.join(classes)}")
    if functions:
        funcs_str = ", ".join(functions[:5])
        if len(functions) > 5:
            funcs_str += f" +{len(functions) - 5} more"
        parts.append(f"Functions: {funcs_str}")

    return " | ".join(parts) if parts else Path(filepath).stem


def _filepath_to_module(filepath: str) -> str:
    """Convert a file path to a dotted module name."""
    p = filepath.replace("/", ".").replace("\\", ".")
    if p.endswith(".py"):
        p = p[:-3]
    if p.endswith(".__init__"):
        p = p[:-9]
    return p


def _filepath_module_candidates(filepath: str) -> list[str]:
    """Generate all possible module names for a filepath.

    For 'packages/hypergraph/hypergraph/config/enums.py', generates:
      - packages.hypergraph.hypergraph.config.enums
      - hypergraph.hypergraph.config.enums
      - hypergraph.config.enums
      - config.enums
      - enums
    """
    base = _filepath_to_module(filepath)
    parts = base.split(".")
    candidates = []
    for i in range(len(parts)):
        candidates.append(".".join(parts[i:]))
    return candidates


def _resolve_import_to_file(
    import_name: str, module_to_file: dict[str, str]
) -> str | None:
    """Try to resolve an import name to a changed file path."""
    # Direct match
    if import_name in module_to_file:
        return module_to_file[import_name]
    # Try progressively shorter prefixes
    parts = import_name.split(".")
    for i in range(len(parts), 0, -1):
        prefix = ".".join(parts[:i])
        if prefix in module_to_file:
            return module_to_file[prefix]
    return None


# ---------------------------------------------------------------------------
# Graph algorithms
# ---------------------------------------------------------------------------


def _topological_layers(
    nodes: set[str], edges: dict[str, set[str]]
) -> dict[str, int]:
    """Assign layer numbers via topological sort (Kahn's algorithm).

    Layer 0 = no dependencies (read first).
    """
    in_degree: dict[str, int] = {n: 0 for n in nodes}
    for src, targets in edges.items():
        for tgt in targets:
            if tgt in in_degree:
                in_degree[tgt] += 1

    layers: dict[str, int] = {}
    current_layer = 0
    remaining = set(nodes)

    while remaining:
        # Find all nodes with in_degree == 0
        ready = {n for n in remaining if in_degree.get(n, 0) == 0}
        if not ready:
            # Cycle detected — assign remaining to current layer
            for n in remaining:
                layers[n] = current_layer
            break

        for n in ready:
            layers[n] = current_layer
            remaining.remove(n)
            # Decrease in_degree of dependents
            for tgt in edges.get(n, set()):
                if tgt in in_degree:
                    in_degree[tgt] -= 1

        current_layer += 1

    return layers


def _status_to_change_type(status: str) -> str:
    """Convert git status letter to human-readable change type."""
    return {
        "A": "added",
        "M": "modified",
        "D": "deleted",
        "R": "renamed",
    }.get(status, "modified")


# ---------------------------------------------------------------------------
# CLI-friendly output
# ---------------------------------------------------------------------------


def format_review_flow(result: PRFlowResult) -> str:
    """Format the PR flow result as a human-readable review guide."""
    lines = []
    lines.append(f"╔══ PR Review Flow: {result.base_ref} → {result.head_ref}")
    lines.append(f"║  {result.total_files} files changed")
    lines.append(f"║  {len(result.layers)} review layers")
    lines.append("╚══════════════════════════════════════════")
    lines.append("")

    max_layer = max(result.layers.keys()) if result.layers else 0

    for layer in range(max_layer + 1):
        layer_files = [f for f in result.files if f.layer == layer]
        if not layer_files:
            continue

        if layer == 0:
            label = "START HERE"
        elif layer == max_layer:
            label = "READ LAST"
        else:
            label = f"LAYER {layer}"

        lines.append(f"  ┌─ {label} {'─' * (40 - len(label))}")

        for f in layer_files:
            icon = {"added": "✚", "deleted": "✖", "renamed": "↪", "modified": "✎"}.get(
                f.change_type, "•"
            )
            lines.append(f"  │ {icon} {f.path}  {f.diff_stat}")
            if f.entity_summary:
                lines.append(f"  │   {f.entity_summary}")
            if f.depends_on:
                deps = ", ".join(Path(d).name for d in f.depends_on)
                lines.append(f"  │   ← depends on: {deps}")
            lines.append("  │")

        lines.append(f"  └{'─' * 48}")
        if layer < max_layer:
            lines.append("      │")
            lines.append("      ▼")
        lines.append("")

    return "\n".join(lines)
