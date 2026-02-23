# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Parameterization settings for the default configuration."""

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from hypergraph.config.defaults import hypergraph_config_defaults
from hypergraph.prompts.index.extract_graph import GRAPH_EXTRACTION_PROMPT


@dataclass
class ExtractGraphPrompts:
    """Graph extraction prompt templates."""

    extraction_prompt: str


class ExtractGraphConfig(BaseModel):
    """Configuration section for entity extraction."""

    completion_model_id: str = Field(
        description="The model ID to use for text embeddings.",
        default=hypergraph_config_defaults.extract_graph.completion_model_id,
    )
    model_instance_name: str = Field(
        description="The model singleton instance name. This primarily affects the cache storage partitioning.",
        default=hypergraph_config_defaults.extract_graph.model_instance_name,
    )
    prompt: str | None = Field(
        description="The entity extraction prompt to use.",
        default=hypergraph_config_defaults.extract_graph.prompt,
    )
    entity_types: list[str] = Field(
        description="The entity extraction entity types to use.",
        default=hypergraph_config_defaults.extract_graph.entity_types,
    )
    relationship_types: list[str] = Field(
        description="Optional relationship types to constrain extraction.",
        default=hypergraph_config_defaults.extract_graph.relationship_types,
    )
    strict_entity_types: bool = Field(
        description=(
            "If true, enforce that extracted entity types must come from entity_types. "
            "If false, the model may propose new entity types."
        ),
        default=hypergraph_config_defaults.extract_graph.strict_entity_types,
    )
    strict_relationship_types: bool = Field(
        description=(
            "If true, enforce that extracted relationship labels must come from relationship_types. "
            "If false, the model may propose new relationship labels."
        ),
        default=hypergraph_config_defaults.extract_graph.strict_relationship_types,
    )
    ontology: str | None = Field(
        description="Optional raw ontology text to inject into the extraction prompt.",
        default=hypergraph_config_defaults.extract_graph.ontology,
    )
    max_gleanings: int = Field(
        description="The maximum number of entity gleanings to use.",
        default=hypergraph_config_defaults.extract_graph.max_gleanings,
    )

    @model_validator(mode="after")
    def _validate_strict_type_settings(self) -> "ExtractGraphConfig":
        """Validate strict mode settings."""
        if self.strict_entity_types and not any(
            item.strip() for item in self.entity_types
        ):
            msg = (
                "extract_graph.strict_entity_types requires "
                "extract_graph.entity_types to include at least one type."
            )
            raise ValueError(msg)

        if self.strict_relationship_types and not any(
            item.strip() for item in self.relationship_types
        ):
            msg = (
                "extract_graph.strict_relationship_types requires "
                "extract_graph.relationship_types to include at least one type."
            )
            raise ValueError(msg)

        return self

    def resolved_prompts(self) -> ExtractGraphPrompts:
        """Get the resolved graph extraction prompts."""
        return ExtractGraphPrompts(
            extraction_prompt=Path(self.prompt).read_text(encoding="utf-8")
            if self.prompt
            else GRAPH_EXTRACTION_PROMPT,
        )
