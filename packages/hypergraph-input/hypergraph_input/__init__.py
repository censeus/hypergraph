# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Hypergraph input document loading package."""

from hypergraph_input.get_property import get_property
from hypergraph_input.input_config import InputConfig
from hypergraph_input.input_reader import InputReader
from hypergraph_input.input_reader_factory import create_input_reader
from hypergraph_input.input_type import InputType
from hypergraph_input.text_document import TextDocument

__all__ = [
    "InputConfig",
    "InputReader",
    "InputType",
    "TextDocument",
    "create_input_reader",
    "get_property",
]
