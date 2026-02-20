# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Tests for pipeline state passthrough."""

from hypergraph.config.models.hyper_graph_config import HyperGraphConfig
from hypergraph.index.run.utils import create_run_context
from hypergraph.index.typing.context import PipelineRunContext
from hypergraph.index.typing.workflow import WorkflowFunctionOutput
from hypergraph.index.workflows.factory import PipelineFactory

from tests.unit.config.utils import get_default_hypergraph_config


async def run_workflow_1(  # noqa: RUF029
    _config: HyperGraphConfig, context: PipelineRunContext
):
    context.state["count"] = 1
    return WorkflowFunctionOutput(result=None)


async def run_workflow_2(  # noqa: RUF029
    _config: HyperGraphConfig, context: PipelineRunContext
):
    context.state["count"] += 1
    return WorkflowFunctionOutput(result=None)


async def test_pipeline_state():
    # checks that we can update the arbitrary state block within the pipeline run context
    PipelineFactory.register("workflow_1", run_workflow_1)
    PipelineFactory.register("workflow_2", run_workflow_2)

    config = get_default_hypergraph_config()
    config.workflows = ["workflow_1", "workflow_2"]
    context = create_run_context()

    for _, fn in PipelineFactory.create_pipeline(config).run():
        await fn(config, context)

    assert context.state["count"] == 2


async def test_pipeline_existing_state():
    PipelineFactory.register("workflow_2", run_workflow_2)

    config = get_default_hypergraph_config()
    config.workflows = ["workflow_2"]
    context = create_run_context(state={"count": 4})

    for _, fn in PipelineFactory.create_pipeline(config).run():
        await fn(config, context)

    assert context.state["count"] == 5
