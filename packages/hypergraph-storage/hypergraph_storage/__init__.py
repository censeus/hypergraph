# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""The Hypergraph Storage package."""

from hypergraph_storage.storage import Storage
from hypergraph_storage.storage_config import StorageConfig
from hypergraph_storage.storage_factory import (
    create_storage,
    register_storage,
)
from hypergraph_storage.storage_type import StorageType
from hypergraph_storage.tables import TableProvider

__all__ = [
    "Storage",
    "StorageConfig",
    "StorageType",
    "TableProvider",
    "create_storage",
    "register_storage",
]
