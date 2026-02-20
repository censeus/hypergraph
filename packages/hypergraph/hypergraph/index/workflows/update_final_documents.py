# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""A module containing run_workflow method definition."""

import logging

from hypergraph.config.models.hyper_graph_config import HyperGraphConfig
from hypergraph.index.run.utils import get_update_table_providers
from hypergraph.index.typing.context import PipelineRunContext
from hypergraph.index.typing.workflow import WorkflowFunctionOutput
from hypergraph.index.update.incremental_index import concat_dataframes

logger = logging.getLogger(__name__)


async def run_workflow(
    config: HyperGraphConfig,
    context: PipelineRunContext,
) -> WorkflowFunctionOutput:
    """Update the documents from a incremental index run."""
    logger.info("Workflow started: update_final_documents")
    output_table_provider, previous_table_provider, delta_table_provider = (
        get_update_table_providers(config, context.state["update_timestamp"])
    )

    final_documents = await concat_dataframes(
        "documents",
        previous_table_provider,
        delta_table_provider,
        output_table_provider,
    )

    context.state["incremental_update_final_documents"] = final_documents

    logger.info("Workflow completed: update_final_documents")
    return WorkflowFunctionOutput(result=None)
