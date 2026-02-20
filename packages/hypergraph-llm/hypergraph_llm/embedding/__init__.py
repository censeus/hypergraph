# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""LLMEmbedding module for hypergraph_llm."""

from hypergraph_llm.embedding.embedding import LLMEmbedding
from hypergraph_llm.embedding.embedding_factory import (
    create_embedding,
    register_embedding,
)

__all__ = [
    "LLMEmbedding",
    "create_embedding",
    "register_embedding",
]
