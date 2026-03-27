# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Workflow: load_codebase — walk a codebase and produce documents + text units."""

import logging
from pathlib import Path

from hypergraph.config.models.hyper_graph_config import HyperGraphConfig
from hypergraph.index.typing.context import PipelineRunContext
from hypergraph.index.typing.workflow import WorkflowFunctionOutput
from hypergraph.index.utils.hashing import gen_sha512_hash

logger = logging.getLogger(__name__)


async def run_workflow(
    config: HyperGraphConfig,
    context: PipelineRunContext,
) -> WorkflowFunctionOutput:
    """Walk a codebase directory and produce document + text_unit rows."""
    logger.info("Workflow started: load_codebase")

    cb_config = config.extract_codebase_graph
    root = Path(cb_config.root_dir).resolve()

    if not root.is_dir():
        msg = f"Codebase root directory does not exist: {root}"
        raise FileNotFoundError(msg)

    import fnmatch

    extensions = cb_config.file_extensions
    excludes = cb_config.exclude_patterns
    max_depth = cb_config.max_depth
    root_depth = len(root.parts)

    async with (
        context.output_table_provider.open("documents") as documents_table,
        context.output_table_provider.open("text_units") as text_units_table,
    ):
        file_count = 0
        for filepath in sorted(root.rglob("*")):
            if not filepath.is_file():
                continue
            if filepath.suffix not in extensions:
                continue
            if max_depth is not None:
                depth = len(filepath.parts) - root_depth
                if depth > max_depth:
                    continue
            relative = str(filepath.relative_to(root))
            if any(fnmatch.fnmatch(relative, pat) for pat in excludes):
                continue

            try:
                text = filepath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                logger.warning("Could not read file: %s", filepath)
                continue

            # Compute a module-style title
            parts = list(filepath.relative_to(root).parts)
            if parts[-1].endswith(".py"):
                parts[-1] = parts[-1][:-3]
            if parts[-1] == "__init__":
                parts = parts[:-1]
            title = ".".join(parts) if parts else filepath.stem

            doc_row = {
                "id": "",
                "title": title,
                "text": text,
                "human_readable_id": file_count,
            }
            doc_row["id"] = gen_sha512_hash(doc_row, ["text"])
            await documents_table.write(doc_row)

            # One text unit per file
            tu_row = {
                "id": "",
                "document_id": doc_row["id"],
                "text": text,
                "n_tokens": len(text.split()),  # rough estimate
            }
            tu_row["id"] = gen_sha512_hash(tu_row, ["text"])
            await text_units_table.write(tu_row)

            file_count += 1

    if file_count == 0:
        msg = f"No source files found in {root}"
        raise ValueError(msg)

    logger.info("Loaded %d source files from %s", file_count, root)
    context.stats.num_documents = file_count

    logger.info("Workflow completed: load_codebase")
    return WorkflowFunctionOutput(result={"files_loaded": file_count})
