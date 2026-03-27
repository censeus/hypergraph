# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""CLI implementation of the codegraph subcommand."""

import logging
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message=".*NumbaDeprecationWarning.*")

logger = logging.getLogger(__name__)


def codegraph_cli(
    root_dir: Path,
    source_dir: Path,
    verbose: bool,
    cache: bool,
    skip_validation: bool,
    extensions: list[str] | None,
    exclude: list[str] | None,
    extract_calls: bool | None,
    extract_decorators: bool | None,
):
    """Run the codebase ontology extraction pipeline."""
    import asyncio

    from hypergraph_cache.cache_type import CacheType

    import hypergraph.api as api
    from hypergraph.callbacks.console_workflow_callbacks import ConsoleWorkflowCallbacks
    from hypergraph.config.enums import IndexingMethod
    from hypergraph.config.models.extract_codebase_graph_config import (
        ExtractCodebaseGraphConfig,
    )
    from hypergraph.config.models.hyper_graph_config import HyperGraphConfig
    from hypergraph.index.validate_config import validate_config_names
    from hypergraph.logger.standard_logging import init_loggers
    from hypergraph.utils.cli import redact

    # Build CLI overrides for the extract_codebase_graph config
    codebase_overrides: dict = {}
    codebase_overrides["root_dir"] = str(source_dir.resolve())
    if extensions is not None:
        codebase_overrides["file_extensions"] = extensions
    if exclude is not None:
        codebase_overrides["exclude_patterns"] = exclude
    if extract_calls is not None:
        codebase_overrides["extract_calls"] = extract_calls
    if extract_decorators is not None:
        codebase_overrides["extract_decorators"] = extract_decorators

    # Try to load config from settings file; fall back to defaults
    # (codegraph doesn't need LLM config for the AST-based extraction)
    try:
        from hypergraph.config.load_config import load_config
        config = load_config(
            root_dir=root_dir,
            cli_overrides={"extract_codebase_graph": codebase_overrides},
        )
    except FileNotFoundError:
        logger.info(
            "No settings file found in %s — using default configuration.", root_dir
        )
        config = HyperGraphConfig(
            extract_codebase_graph=ExtractCodebaseGraphConfig(**codebase_overrides),
        )

    init_loggers(config=config, verbose=verbose)

    if not cache:
        config.cache.type = CacheType.Noop

    if not skip_validation:
        validate_config_names(config)

    logger.info("Starting codebase ontology extraction pipeline.")
    logger.info("Source directory: %s", source_dir.resolve())
    logger.info("Using configuration: %s", redact(config.model_dump()))

    import signal

    def handle_signal(signum, _):
        logger.debug(f"Received signal {signum}, exiting...")  # noqa: G004
        for task in asyncio.all_tasks():
            task.cancel()

    signal.signal(signal.SIGINT, handle_signal)
    if sys.platform != "win32":
        signal.signal(signal.SIGHUP, handle_signal)

    outputs = asyncio.run(
        api.build_index(
            config=config,
            method=IndexingMethod.Codebase,
            is_update_run=False,
            callbacks=[ConsoleWorkflowCallbacks(verbose=verbose)],
            verbose=verbose,
        )
    )
    encountered_errors = any(output.error is not None for output in outputs)
    sys.exit(1 if encountered_errors else 0)
