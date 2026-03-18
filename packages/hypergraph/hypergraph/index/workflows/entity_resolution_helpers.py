# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Shared helpers for creating entity resolution models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypergraph_llm.completion import create_completion

from hypergraph.cache.cache_key_creator import cache_key_creator

if TYPE_CHECKING:
    from hypergraph_cache import Cache
    from hypergraph_llm.completion import LLMCompletion

    from hypergraph.config.models.hyper_graph_config import HyperGraphConfig


def create_entity_resolution_model(
    config: HyperGraphConfig,
    cache: Cache,
) -> tuple[LLMCompletion, str]:
    """Create the entity resolution model and return (model, prompt).

    Parameters
    ----------
    config : HyperGraphConfig
        The pipeline configuration.
    cache : Cache
        The cache instance (the caller's cache root; a child partition
        will be created automatically).

    Returns
    -------
    tuple[LLMCompletion, str]
        The configured LLM completion model and the resolution prompt text.
    """
    model_config = config.get_completion_model_config(
        config.entity_resolution.completion_model_id
    )
    prompts = config.entity_resolution.resolved_prompts()
    model = create_completion(
        model_config,
        cache=cache.child(config.entity_resolution.model_instance_name),
        cache_key_creator=cache_key_creator,
    )
    return model, prompts.resolution_prompt
