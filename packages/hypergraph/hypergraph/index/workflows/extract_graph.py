# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""A module containing run_workflow method definition."""

import logging
import re
from typing import TYPE_CHECKING

import pandas as pd
from hypergraph_llm.completion import create_completion

from hypergraph.cache.cache_key_creator import cache_key_creator
from hypergraph.callbacks.workflow_callbacks import WorkflowCallbacks
from hypergraph.config.enums import AsyncType
from hypergraph.config.models.hyper_graph_config import HyperGraphConfig
from hypergraph.data_model.data_reader import DataReader
from hypergraph.index.operations.extract_graph.extract_graph import (
    extract_graph as extractor,
)
from hypergraph.index.operations.resolve_entities.resolve_entities import (
    resolve_entities,
)
from hypergraph.index.operations.summarize_descriptions.summarize_descriptions import (
    summarize_descriptions,
)
from hypergraph.index.typing.context import PipelineRunContext
from hypergraph.index.typing.workflow import WorkflowFunctionOutput
from hypergraph.index.utils.string import clean_str

if TYPE_CHECKING:
    from hypergraph_llm.completion import LLMCompletion

logger = logging.getLogger(__name__)
TYPE_PROPOSALS_COLUMNS = [
    "proposal_kind",
    "canonical_label",
    "occurrences",
    "raw_labels",
    "sample_descriptions",
]


async def run_workflow(
    config: HyperGraphConfig,
    context: PipelineRunContext,
) -> WorkflowFunctionOutput:
    """All the steps to create the base entity graph."""
    logger.info("Workflow started: extract_graph")
    reader = DataReader(context.output_table_provider)
    text_units = await reader.text_units()

    extraction_model_config = config.get_completion_model_config(
        config.extract_graph.completion_model_id
    )
    extraction_prompts = config.extract_graph.resolved_prompts()
    extraction_model = create_completion(
        extraction_model_config,
        cache=context.cache.child(config.extract_graph.model_instance_name),
        cache_key_creator=cache_key_creator,
    )

    summarization_model_config = config.get_completion_model_config(
        config.summarize_descriptions.completion_model_id
    )
    summarization_prompts = config.summarize_descriptions.resolved_prompts()
    summarization_model = create_completion(
        summarization_model_config,
        cache=context.cache.child(config.summarize_descriptions.model_instance_name),
        cache_key_creator=cache_key_creator,
    )

    # Entity resolution model (optional)
    resolution_enabled = config.entity_resolution.enabled
    resolution_model = None
    resolution_prompt = ""
    if resolution_enabled:
        resolution_model_config = config.get_completion_model_config(
            config.entity_resolution.completion_model_id
        )
        resolution_prompts = config.entity_resolution.resolved_prompts()
        resolution_prompt = resolution_prompts.resolution_prompt
        resolution_model = create_completion(
            resolution_model_config,
            cache=context.cache.child(
                config.entity_resolution.model_instance_name
            ),
            cache_key_creator=cache_key_creator,
        )

    entities, relationships, raw_entities, raw_relationships = await extract_graph(
        text_units=text_units,
        callbacks=context.callbacks,
        extraction_model=extraction_model,
        extraction_prompt=extraction_prompts.extraction_prompt,
        entity_types=config.extract_graph.entity_types,
        relationship_types=config.extract_graph.relationship_types,
        strict_entity_types=config.extract_graph.strict_entity_types,
        strict_relationship_types=config.extract_graph.strict_relationship_types,
        ontology=config.extract_graph.ontology,
        max_gleanings=config.extract_graph.max_gleanings,
        extraction_num_threads=config.concurrent_requests,
        extraction_async_type=config.async_mode,
        summarization_model=summarization_model,
        max_summary_length=config.summarize_descriptions.max_length,
        max_input_tokens=config.summarize_descriptions.max_input_tokens,
        summarization_prompt=summarization_prompts.summarize_prompt,
        summarization_num_threads=config.concurrent_requests,
        resolution_enabled=resolution_enabled,
        resolution_model=resolution_model,
        resolution_prompt=resolution_prompt,
        resolution_num_threads=config.concurrent_requests,
    )

    await context.output_table_provider.write_dataframe("entities", entities)
    await context.output_table_provider.write_dataframe("relationships", relationships)

    if config.snapshots.raw_graph:
        await context.output_table_provider.write_dataframe(
            "raw_entities", raw_entities
        )
        await context.output_table_provider.write_dataframe(
            "raw_relationships", raw_relationships
        )

    type_proposals = _build_type_proposals(
        raw_entities=raw_entities,
        raw_relationships=raw_relationships,
        allowed_entity_types=config.extract_graph.entity_types,
        allowed_relationship_types=config.extract_graph.relationship_types,
        strict_entity_types=config.extract_graph.strict_entity_types,
        strict_relationship_types=config.extract_graph.strict_relationship_types,
    )
    await context.output_table_provider.write_dataframe("type_proposals", type_proposals)

    logger.info("Workflow completed: extract_graph")
    return WorkflowFunctionOutput(
        result={
            "entities": entities,
            "relationships": relationships,
            "type_proposals": type_proposals,
        }
    )


async def extract_graph(
    text_units: pd.DataFrame,
    callbacks: WorkflowCallbacks,
    extraction_model: "LLMCompletion",
    extraction_prompt: str,
    entity_types: list[str],
    relationship_types: list[str],
    strict_entity_types: bool,
    strict_relationship_types: bool,
    ontology: str | None,
    max_gleanings: int,
    extraction_num_threads: int,
    extraction_async_type: AsyncType,
    summarization_model: "LLMCompletion",
    max_summary_length: int,
    max_input_tokens: int,
    summarization_prompt: str,
    summarization_num_threads: int,
    resolution_enabled: bool = False,
    resolution_model: "LLMCompletion | None" = None,
    resolution_prompt: str = "",
    resolution_num_threads: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """All the steps to create the base entity graph."""
    # this returns a graph for each text unit, to be merged later
    extracted_entities, extracted_relationships = await extractor(
        text_units=text_units,
        callbacks=callbacks,
        text_column="text",
        id_column="id",
        model=extraction_model,
        prompt=extraction_prompt,
        entity_types=entity_types,
        relationship_types=relationship_types,
        strict_entity_types=strict_entity_types,
        strict_relationship_types=strict_relationship_types,
        ontology=ontology,
        max_gleanings=max_gleanings,
        num_threads=extraction_num_threads,
        async_type=extraction_async_type,
    )

    if len(extracted_entities) == 0:
        error_msg = "Graph Extraction failed. No entities detected during extraction."
        logger.error(error_msg)
        raise ValueError(error_msg)

    if len(extracted_relationships) == 0:
        error_msg = (
            "Graph Extraction failed. No relationships detected during extraction."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # copy these as is before any resolution or summarization
    raw_entities = extracted_entities.copy()
    raw_relationships = extracted_relationships.copy()

    # Resolve duplicate entity names before grouping by title
    if resolution_enabled and resolution_model is not None:
        extracted_entities, extracted_relationships = await resolve_entities(
            entities=extracted_entities,
            relationships=extracted_relationships,
            callbacks=callbacks,
            model=resolution_model,
            prompt=resolution_prompt,
            num_threads=resolution_num_threads,
        )

    entities, relationships = await get_summarized_entities_relationships(
        extracted_entities=extracted_entities,
        extracted_relationships=extracted_relationships,
        callbacks=callbacks,
        model=summarization_model,
        max_summary_length=max_summary_length,
        max_input_tokens=max_input_tokens,
        summarization_prompt=summarization_prompt,
        num_threads=summarization_num_threads,
    )

    return (entities, relationships, raw_entities, raw_relationships)


async def get_summarized_entities_relationships(
    extracted_entities: pd.DataFrame,
    extracted_relationships: pd.DataFrame,
    callbacks: WorkflowCallbacks,
    model: "LLMCompletion",
    max_summary_length: int,
    max_input_tokens: int,
    summarization_prompt: str,
    num_threads: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summarize the entities and relationships."""
    entity_summaries, relationship_summaries = await summarize_descriptions(
        entities_df=extracted_entities,
        relationships_df=extracted_relationships,
        callbacks=callbacks,
        model=model,
        max_summary_length=max_summary_length,
        max_input_tokens=max_input_tokens,
        prompt=summarization_prompt,
        num_threads=num_threads,
    )

    relationships = extracted_relationships.drop(columns=["description"]).merge(
        relationship_summaries, on=["source", "target"], how="left"
    )

    extracted_entities.drop(columns=["description"], inplace=True)
    entities = extracted_entities.merge(entity_summaries, on="title", how="left")
    return entities, relationships


def _build_type_proposals(
    raw_entities: pd.DataFrame,
    raw_relationships: pd.DataFrame,
    allowed_entity_types: list[str],
    allowed_relationship_types: list[str],
    strict_entity_types: bool,
    strict_relationship_types: bool,
) -> pd.DataFrame:
    """Build consolidated type proposals for non-strict extraction."""
    proposal_records: list[dict] = []

    if not strict_entity_types and len(raw_entities) > 0:
        allowed_entity_keys = _build_allowed_keys(allowed_entity_types)
        proposal_records.extend(
            _collect_entity_proposals(raw_entities, allowed_entity_keys)
        )

    if not strict_relationship_types and len(raw_relationships) > 0:
        allowed_relationship_keys = _build_allowed_keys(allowed_relationship_types)
        proposal_records.extend(
            _collect_relationship_proposals(
                raw_relationships,
                allowed_relationship_keys,
            )
        )

    if not proposal_records:
        return pd.DataFrame(columns=TYPE_PROPOSALS_COLUMNS)

    proposals = pd.DataFrame(proposal_records)
    consolidated = (
        proposals
        .groupby(["proposal_kind", "canonical_label"], as_index=False)
        .agg(
            occurrences=("occurrences", "sum"),
            raw_labels=("raw_label", lambda values: sorted(set(values))),
            sample_descriptions=(
                "sample_description",
                lambda values: _unique_non_empty(values, limit=3),
            ),
        )
        .sort_values(by=["occurrences", "canonical_label"], ascending=[False, True])
        .reset_index(drop=True)
    )
    return consolidated


def _collect_entity_proposals(
    raw_entities: pd.DataFrame,
    allowed_entity_keys: set[str],
) -> list[dict]:
    records: list[dict] = []
    for _, row in raw_entities.iterrows():
        raw_label = clean_str(row.get("type", ""))
        if not isinstance(raw_label, str):
            continue
        raw_label = raw_label.strip()
        if not raw_label:
            continue

        canonical_label = _canonicalize_type_label(raw_label)
        if canonical_label in allowed_entity_keys:
            continue

        sample_descriptions = _prep_descriptions(row.get("description"))
        records.append({
            "proposal_kind": "entity",
            "raw_label": raw_label,
            "canonical_label": canonical_label,
            "occurrences": int(row.get("frequency", 1)),
            "sample_description": sample_descriptions[0] if sample_descriptions else "",
        })
    return records


def _collect_relationship_proposals(
    raw_relationships: pd.DataFrame,
    allowed_relationship_keys: set[str],
) -> list[dict]:
    records: list[dict] = []
    for _, row in raw_relationships.iterrows():
        descriptions = _prep_descriptions(row.get("description"))
        for description in descriptions:
            raw_label = _extract_relationship_label(description)
            if raw_label is None:
                continue

            canonical_label = _canonicalize_type_label(raw_label)
            if canonical_label in allowed_relationship_keys:
                continue

            records.append({
                "proposal_kind": "relationship",
                "raw_label": raw_label,
                "canonical_label": canonical_label,
                "occurrences": 1,
                "sample_description": description,
            })

    return records


def _prep_descriptions(value: object) -> list[str]:
    """Normalize a single description or list of descriptions."""
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, str):
        return [value]
    return []


def _extract_relationship_label(description: str) -> str | None:
    """Extract the relationship label from `<label>: description`."""
    if ":" not in description:
        return None

    candidate, _ = description.split(":", 1)
    normalized = clean_str(candidate).strip()
    return normalized if normalized else None


def _build_allowed_keys(labels: list[str]) -> set[str]:
    return {
        _canonicalize_type_label(label)
        for label in labels
        if isinstance(label, str) and _canonicalize_type_label(label)
    }


def _canonicalize_type_label(label: str) -> str:
    """Canonical label used to collapse similar proposals from chunked extraction."""
    normalized = _normalize_type_key(label)
    if not normalized:
        return normalized

    aliases = {
        "org": "organization",
        "orgs": "organization",
        "organisations": "organization",
        "companies": "company",
        "people": "person",
        "persons": "person",
    }
    if normalized in aliases:
        return aliases[normalized]

    parts = normalized.split(" ")
    singular_parts: list[str] = []
    for part in parts:
        if part.endswith("ies") and len(part) > 3:
            singular_parts.append(part[:-3] + "y")
        elif part.endswith("s") and len(part) > 3 and not part.endswith(("ss", "us")):
            singular_parts.append(part[:-1])
        else:
            singular_parts.append(part)

    collapsed = " ".join(singular_parts)
    return aliases.get(collapsed, collapsed)


def _normalize_type_key(label: str) -> str:
    normalized = clean_str(label).strip().lower()
    normalized = re.sub(r"[_\-/]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _unique_non_empty(values: object, limit: int) -> list[str]:
    unique: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        value = value.strip()
        if not value or value in unique:
            continue
        unique.append(value)
        if len(unique) >= limit:
            break
    return unique
