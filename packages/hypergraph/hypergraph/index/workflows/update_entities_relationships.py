# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""A module containing run_workflow method definition."""

import logging

import pandas as pd
from hypergraph_cache import Cache
from hypergraph_llm.completion import create_completion
from hypergraph_storage.tables.table_provider import TableProvider

from hypergraph.cache.cache_key_creator import cache_key_creator
from hypergraph.callbacks.workflow_callbacks import WorkflowCallbacks
from hypergraph.config.models.hyper_graph_config import HyperGraphConfig
from hypergraph.data_model.data_reader import DataReader
from hypergraph.index.operations.resolve_entities.resolve_entities import (
    resolve_entities,
)
from hypergraph.index.run.utils import get_update_table_providers
from hypergraph.index.typing.context import PipelineRunContext
from hypergraph.index.typing.workflow import WorkflowFunctionOutput
from hypergraph.index.update.entities import _group_and_resolve_entities
from hypergraph.index.update.relationships import _update_and_merge_relationships
from hypergraph.index.workflows.extract_graph import get_summarized_entities_relationships

logger = logging.getLogger(__name__)


async def run_workflow(
    config: HyperGraphConfig,
    context: PipelineRunContext,
) -> WorkflowFunctionOutput:
    """Update the entities and relationships from a incremental index run."""
    logger.info("Workflow started: update_entities_relationships")
    output_table_provider, previous_table_provider, delta_table_provider = (
        get_update_table_providers(config, context.state["update_timestamp"])
    )

    (
        merged_entities_df,
        merged_relationships_df,
        entity_id_mapping,
    ) = await _update_entities_and_relationships(
        previous_table_provider,
        delta_table_provider,
        output_table_provider,
        config,
        context.cache,
        context.callbacks,
    )

    context.state["incremental_update_merged_entities"] = merged_entities_df
    context.state["incremental_update_merged_relationships"] = merged_relationships_df
    context.state["incremental_update_entity_id_mapping"] = entity_id_mapping

    logger.info("Workflow completed: update_entities_relationships")
    return WorkflowFunctionOutput(result=None)


async def _update_entities_and_relationships(
    previous_table_provider: TableProvider,
    delta_table_provider: TableProvider,
    output_table_provider: TableProvider,
    config: HyperGraphConfig,
    cache: Cache,
    callbacks: WorkflowCallbacks,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Update Final Entities and Relationships output."""
    old_entities = await DataReader(previous_table_provider).entities()
    delta_entities = await DataReader(delta_table_provider).entities()

    # Read relationships early — needed for cross-index entity resolution
    old_relationships = await DataReader(previous_table_provider).relationships()
    delta_relationships = await DataReader(delta_table_provider).relationships()

    # LLM-based entity resolution across old + new entities
    # This catches aliases (e.g. "Microsoft Corp" vs "Microsoft Corporation")
    # that exact-title grouping would miss.
    if config.entity_resolution.enabled:
        logger.info("Running cross-index entity resolution on merged entities...")
        from hypergraph.index.workflows.entity_resolution_helpers import (
            create_entity_resolution_model,
        )

        resolution_model, resolution_prompt = create_entity_resolution_model(
            config, cache
        )

        n_old_ent = len(old_entities)
        n_old_rel = len(old_relationships)

        combined_entities = pd.concat(
            [old_entities, delta_entities], ignore_index=True, copy=False
        )
        combined_relationships = pd.concat(
            [old_relationships, delta_relationships], ignore_index=True, copy=False
        )

        combined_entities, combined_relationships = await resolve_entities(
            entities=combined_entities,
            relationships=combined_relationships,
            callbacks=callbacks,
            model=resolution_model,
            prompt=resolution_prompt,
            num_threads=config.concurrent_requests,
        )

        # resolve_entities only renames titles in-place; it never drops,
        # reorders, or merges rows, so the positional split is safe.
        # We still need old/delta separated because _group_and_resolve_entities
        # builds an id_mapping {delta_id → old_id} used downstream.
        old_entities = combined_entities.iloc[:n_old_ent].reset_index(drop=True)
        delta_entities = combined_entities.iloc[n_old_ent:].reset_index(drop=True)
        old_relationships = combined_relationships.iloc[:n_old_rel].reset_index(drop=True)
        delta_relationships = combined_relationships.iloc[n_old_rel:].reset_index(drop=True)

    merged_entities_df, entity_id_mapping = _group_and_resolve_entities(
        old_entities, delta_entities
    )

    merged_relationships_df = _update_and_merge_relationships(
        old_relationships, delta_relationships,
    )

    summarization_model_config = config.get_completion_model_config(
        config.summarize_descriptions.completion_model_id
    )
    prompts = config.summarize_descriptions.resolved_prompts()
    model = create_completion(
        summarization_model_config,
        cache=cache.child("summarize_descriptions"),
        cache_key_creator=cache_key_creator,
    )

    (
        merged_entities_df,
        merged_relationships_df,
    ) = await get_summarized_entities_relationships(
        extracted_entities=merged_entities_df,
        extracted_relationships=merged_relationships_df,
        callbacks=callbacks,
        model=model,
        max_summary_length=config.summarize_descriptions.max_length,
        max_input_tokens=config.summarize_descriptions.max_input_tokens,
        summarization_prompt=prompts.summarize_prompt,
        num_threads=config.concurrent_requests,
    )

    # Save the updated entities back to storage
    await output_table_provider.write_dataframe("entities", merged_entities_df)
    await output_table_provider.write_dataframe(
        "relationships", merged_relationships_df
    )

    return merged_entities_df, merged_relationships_df, entity_id_mapping
