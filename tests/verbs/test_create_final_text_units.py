# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

from hypergraph.data_model.schemas import TEXT_UNITS_FINAL_COLUMNS
from hypergraph.index.workflows.create_final_text_units import (
    run_workflow,
)

from tests.unit.config.utils import get_default_hypergraph_config

from .util import (
    compare_outputs,
    create_test_context,
    load_test_table,
)


async def test_create_final_text_units():
    expected = load_test_table("text_units")

    context = await create_test_context(
        storage=[
            "text_units",
            "entities",
            "relationships",
            "covariates",
        ],
    )

    config = get_default_hypergraph_config()
    config.extract_claims.enabled = True

    await run_workflow(config, context)

    actual = await context.output_table_provider.read_dataframe("text_units")

    for column in TEXT_UNITS_FINAL_COLUMNS:
        assert column in actual.columns

    compare_outputs(actual, expected)
