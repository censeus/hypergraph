# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Workflow: extract_codebase_graph — AST-based structural graph extraction."""

import logging
from pathlib import Path

import pandas as pd

from hypergraph.config.models.hyper_graph_config import HyperGraphConfig
from hypergraph.index.operations.parse_codebase.parser import parse_codebase
from hypergraph.index.typing.context import PipelineRunContext
from hypergraph.index.typing.workflow import WorkflowFunctionOutput

logger = logging.getLogger(__name__)


async def run_workflow(
    config: HyperGraphConfig,
    context: PipelineRunContext,
) -> WorkflowFunctionOutput:
    """Extract a structural knowledge graph from a codebase using static AST analysis."""
    logger.info("Workflow started: extract_codebase_graph")

    cb_config = config.extract_codebase_graph
    root_dir = Path(cb_config.root_dir).resolve()

    entities, relationships = parse_codebase(
        root_dir=root_dir,
        file_extensions=cb_config.file_extensions,
        exclude_patterns=cb_config.exclude_patterns,
        extract_calls=cb_config.extract_calls,
        extract_decorators=cb_config.extract_decorators,
        max_depth=cb_config.max_depth,
    )

    if len(entities) == 0:
        msg = "Codebase graph extraction failed. No entities detected."
        logger.error(msg)
        raise ValueError(msg)

    # Aggregate entities: group by (title, type) to match downstream expectations
    entities = (
        entities.groupby(["title", "type"], sort=False)
        .agg(
            description=("description", "first"),
            text_unit_ids=("source_id", list),
            frequency=("source_id", "count"),
        )
        .reset_index()
    )

    # Aggregate relationships: group by (source, target) to deduplicate
    if len(relationships) > 0:
        relationships = (
            relationships.groupby(["source", "target"], sort=False)
            .agg(
                description=("description", "first"),
                text_unit_ids=("source_id", list),
                weight=("weight", "sum"),
            )
            .reset_index()
        )
    else:
        relationships = pd.DataFrame(
            columns=["source", "target", "description", "text_unit_ids", "weight"]
        )

    await context.output_table_provider.write_dataframe("entities", entities)
    await context.output_table_provider.write_dataframe("relationships", relationships)

    logger.info(
        "Codebase graph: %d entities, %d relationships",
        len(entities),
        len(relationships),
    )
    logger.info("Workflow completed: extract_codebase_graph")

    return WorkflowFunctionOutput(
        result={
            "entities": entities,
            "relationships": relationships,
        }
    )
