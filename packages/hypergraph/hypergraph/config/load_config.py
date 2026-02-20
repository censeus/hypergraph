# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Default method for loading config."""

from pathlib import Path
from typing import Any

from hypergraph_common.config import load_config as lc

from hypergraph.config.models.hyper_graph_config import HyperGraphConfig


def load_config(
    root_dir: str | Path,
    cli_overrides: dict[str, Any] | None = None,
) -> HyperGraphConfig:
    """Load configuration from a file.

    Parameters
    ----------
    root_dir : str | Path
        The root directory of the project.
        Searches for settings.[yaml|yml|json] config files.
    cli_overrides : dict[str, Any] | None
        A nested dictionary of cli overrides.
        Example: {'output': {'base_dir': 'override_value'}}

    Returns
    -------
    HyperGraphConfig
        The loaded configuration.

    Raises
    ------
    FileNotFoundError
        If the config file is not found.
    ConfigParsingError
        If there was an error parsing the config file or its environment variables.
    ValidationError
        If there are pydantic validation errors when instantiating the config.
    """
    return lc(
        config_initializer=HyperGraphConfig,
        config_path=root_dir,
        overrides=cli_overrides,
    )
