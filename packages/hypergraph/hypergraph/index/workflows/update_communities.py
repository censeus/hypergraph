# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""A module containing run_workflow method definition."""

import logging

from hypergraph_storage.tables.table_provider import TableProvider

from hypergraph.config.models.hyper_graph_config import HyperGraphConfig
from hypergraph.data_model.data_reader import DataReader
from hypergraph.index.run.utils import get_update_table_providers
from hypergraph.index.typing.context import PipelineRunContext
from hypergraph.index.typing.workflow import WorkflowFunctionOutput
from hypergraph.index.update.communities import _update_and_merge_communities

logger = logging.getLogger(__name__)


async def run_workflow(
    config: HyperGraphConfig,
    context: PipelineRunContext,
) -> WorkflowFunctionOutput:
    """Update the communities from a incremental index run."""
    logger.info("Workflow started: update_communities")
    output_table_provider, previous_table_provider, delta_table_provider = (
        get_update_table_providers(config, context.state["update_timestamp"])
    )

    community_id_mapping = await _update_communities(
        previous_table_provider, delta_table_provider, output_table_provider
    )

    context.state["incremental_update_community_id_mapping"] = community_id_mapping

    logger.info("Workflow completed: update_communities")
    return WorkflowFunctionOutput(result=None)


async def _update_communities(
    previous_table_provider: TableProvider,
    delta_table_provider: TableProvider,
    output_table_provider: TableProvider,
) -> dict:
    """Update the communities output."""
    old_communities = await DataReader(previous_table_provider).communities()
    delta_communities = await DataReader(delta_table_provider).communities()
    merged_communities, community_id_mapping = _update_and_merge_communities(
        old_communities, delta_communities
    )

    await output_table_provider.write_dataframe("communities", merged_communities)

    return community_id_mapping
