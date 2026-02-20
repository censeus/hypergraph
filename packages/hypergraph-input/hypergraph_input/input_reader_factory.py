# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""A module containing 'InputReaderFactory' model."""

import logging
from collections.abc import Callable

from hypergraph_common.factory import Factory
from hypergraph_common.factory.factory import ServiceScope
from hypergraph_storage.storage import Storage

from hypergraph_input.input_config import InputConfig
from hypergraph_input.input_reader import InputReader
from hypergraph_input.input_type import InputType

logger = logging.getLogger(__name__)


class InputReaderFactory(Factory[InputReader]):
    """Factory for creating Input Reader instances."""


input_reader_factory = InputReaderFactory()


def register_input_reader(
    input_reader_type: str,
    input_reader_initializer: Callable[..., InputReader],
    scope: ServiceScope = "transient",
) -> None:
    """Register a custom input reader implementation.

    Args
    ----
        - input_reader_type: str
            The input reader id to register.
        - input_reader_initializer: Callable[..., InputReader]
            The input reader initializer to register.
    """
    input_reader_factory.register(input_reader_type, input_reader_initializer, scope)


def create_input_reader(config: InputConfig, storage: Storage) -> InputReader:
    """Create an input reader implementation based on the given configuration.

    Args
    ----
        - config: InputConfig
            The input reader configuration to use.
        - storage: Storage | None
            The storage implementation to use for reading the files.

    Returns
    -------
        InputReader
            The created input reader implementation.
    """
    config_model = config.model_dump()
    input_strategy = config.type

    if input_strategy not in input_reader_factory:
        match input_strategy:
            case InputType.Csv:
                from hypergraph_input.csv import CSVFileReader

                register_input_reader(InputType.Csv, CSVFileReader)
            case InputType.Text:
                from hypergraph_input.text import TextFileReader

                register_input_reader(InputType.Text, TextFileReader)
            case InputType.Json:
                from hypergraph_input.json import JSONFileReader

                register_input_reader(InputType.Json, JSONFileReader)
            case InputType.JsonLines:
                from hypergraph_input.jsonl import JSONLinesFileReader

                register_input_reader(InputType.JsonLines, JSONLinesFileReader)
            case InputType.MarkItDown:
                from hypergraph_input.markitdown import MarkItDownFileReader

                register_input_reader(InputType.MarkItDown, MarkItDownFileReader)
            case _:
                msg = f"InputConfig.type '{input_strategy}' is not registered in the InputReaderFactory. Registered types: {', '.join(input_reader_factory.keys())}."
                raise ValueError(msg)

    config_model["storage"] = storage

    return input_reader_factory.create(input_strategy, init_args=config_model)
