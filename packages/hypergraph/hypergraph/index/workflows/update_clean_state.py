# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""A module containing run_workflow method definition."""

import logging

from hypergraph.config.models.hyper_graph_config import HyperGraphConfig
from hypergraph.index.typing.context import PipelineRunContext
from hypergraph.index.typing.workflow import WorkflowFunctionOutput

logger = logging.getLogger(__name__)


async def run_workflow(  # noqa: RUF029
    _config: HyperGraphConfig,
    context: PipelineRunContext,
) -> WorkflowFunctionOutput:
    """Clean the state after the update."""
    logger.info("Workflow started: update_clean_state")
    keys_to_delete = [
        key_name
        for key_name in context.state
        if key_name.startswith("incremental_update_")
    ]

    for key_name in keys_to_delete:
        del context.state[key_name]

    logger.info("Workflow completed: update_clean_state")
    return WorkflowFunctionOutput(result=None)
