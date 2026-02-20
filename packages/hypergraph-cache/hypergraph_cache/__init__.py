# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""The Hypergraph Cache package."""

from hypergraph_cache.cache import Cache
from hypergraph_cache.cache_config import CacheConfig
from hypergraph_cache.cache_factory import create_cache, register_cache
from hypergraph_cache.cache_key import CacheKeyCreator, create_cache_key
from hypergraph_cache.cache_type import CacheType

__all__ = [
    "Cache",
    "CacheConfig",
    "CacheKeyCreator",
    "CacheType",
    "create_cache",
    "create_cache_key",
    "register_cache",
]
