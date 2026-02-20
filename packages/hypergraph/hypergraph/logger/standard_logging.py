# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Standard logging configuration for the hypergraph package.

This module provides a standardized way to configure Python's built-in
logging system for use within the hypergraph package.

Usage:
    # Configuration should be done once at the start of your application:
    from hypergraph.logger.standard_logging import init_loggers
    init_loggers(config)

    # Then throughout your code:
    import logging
    logger = logging.getLogger(__name__)  # Use standard logging

    # Use standard logging methods:
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical error message")

Notes
-----
    The logging system is hierarchical. Loggers are organized in a tree structure,
    with the root logger named 'hypergraph'. All loggers created with names starting
    with 'hypergraph.' will be children of this root logger. This allows for consistent
    configuration of all hypergraph-related logs throughout the application.

    All progress logging now uses this standard logging system for consistency.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from hypergraph.logger.factory import (
    LoggerFactory,
)

if TYPE_CHECKING:
    from hypergraph.config.models.hyper_graph_config import HyperGraphConfig

DEFAULT_LOG_FILENAME = "indexing-engine.log"


def init_loggers(
    config: HyperGraphConfig,
    verbose: bool = False,
    filename: str = DEFAULT_LOG_FILENAME,
) -> None:
    """Initialize logging handlers for hypergraph based on configuration.

    Parameters
    ----------
    config : HyperGraphConfig | None, default=None
        The Hypergraph configuration. If None, defaults to file-based reporting.
    verbose : bool, default=False
        Whether to enable verbose (DEBUG) logging.
    filename : Optional[str]
        Log filename on disk. If unset, will use a default name.
    """
    logger = logging.getLogger("hypergraph")
    log_level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(log_level)

    llm_logger = logging.getLogger("hypergraph_llm")
    llm_logger.setLevel(log_level)

    def _clear_handlers(logger: logging.Logger) -> None:
        # clear any existing handlers to avoid duplicate logs
        if logger.hasHandlers():
            # Close file handlers properly before removing them
            for handler in logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    handler.close()
            logger.handlers.clear()

    _clear_handlers(logger)
    _clear_handlers(llm_logger)

    reporting_config = config.reporting
    config_dict = reporting_config.model_dump()
    args = {**config_dict, "filename": filename}

    handler = LoggerFactory().create(reporting_config.type, args)
    logger.addHandler(handler)
    llm_logger.addHandler(handler)
