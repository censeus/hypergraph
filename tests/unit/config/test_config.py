# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

import os
from pathlib import Path
from unittest import mock

import pytest

from hypergraph.config.load_config import load_config
from hypergraph.config.models.hyper_graph_config import HyperGraphConfig

from tests.unit.config.utils import (
    DEFAULT_COMPLETION_MODELS,
    DEFAULT_EMBEDDING_MODELS,
    FAKE_API_KEY,
    assert_hypergraph_configs,
    get_default_hypergraph_config,
)


def test_default_config() -> None:
    expected = get_default_hypergraph_config()
    actual = HyperGraphConfig(
        completion_models=DEFAULT_COMPLETION_MODELS,  # type: ignore
        embedding_models=DEFAULT_EMBEDDING_MODELS,  # type: ignore
    )
    assert_hypergraph_configs(actual, expected)


@mock.patch.dict(os.environ, {"CUSTOM_API_KEY": FAKE_API_KEY}, clear=True)
def test_load_minimal_config() -> None:
    cwd = Path.cwd()
    root_dir = (Path(__file__).parent / "fixtures" / "minimal_config").resolve()
    os.chdir(root_dir)
    expected = get_default_hypergraph_config()

    actual = load_config(
        root_dir=root_dir,
    )
    assert_hypergraph_configs(actual, expected)
    # Need to reset cwd after test
    os.chdir(cwd)


@mock.patch.dict(os.environ, {"CUSTOM_API_KEY": FAKE_API_KEY}, clear=True)
def test_load_config_with_cli_overrides() -> None:
    cwd = Path.cwd()
    root_dir = (Path(__file__).parent / "fixtures" / "minimal_config").resolve()
    os.chdir(root_dir)
    output_dir = "some_output_dir"
    expected_output_base_dir = root_dir / output_dir
    expected = get_default_hypergraph_config()
    expected.output_storage.base_dir = str(expected_output_base_dir)

    actual = load_config(
        root_dir=root_dir,
        cli_overrides={"output_storage": {"base_dir": output_dir}},
    )
    assert_hypergraph_configs(actual, expected)
    # Need to reset cwd after test
    os.chdir(cwd)


def test_extract_graph_ontology_is_preserved_as_raw_text() -> None:
    ontology = (
        "entity_types: [company, product]\n"
        "relationship_types: [acquires, partners_with]"
    )
    config = HyperGraphConfig(
        completion_models=DEFAULT_COMPLETION_MODELS,  # type: ignore
        embedding_models=DEFAULT_EMBEDDING_MODELS,  # type: ignore
        extract_graph={
            "entity_types": ["ignored_default"],
            "ontology": ontology,
        },
    )

    assert config.extract_graph.ontology == ontology
    assert config.extract_graph.entity_types == ["ignored_default"]


def test_extract_graph_strict_entity_types_requires_allowed_types() -> None:
    with pytest.raises(ValueError, match="strict_entity_types"):
        HyperGraphConfig(
            completion_models=DEFAULT_COMPLETION_MODELS,  # type: ignore
            embedding_models=DEFAULT_EMBEDDING_MODELS,  # type: ignore
            extract_graph={
                "entity_types": [" "],
                "strict_entity_types": True,
            },
        )


def test_extract_graph_strict_relationship_types_requires_allowed_types() -> None:
    with pytest.raises(ValueError, match="strict_relationship_types"):
        HyperGraphConfig(
            completion_models=DEFAULT_COMPLETION_MODELS,  # type: ignore
            embedding_models=DEFAULT_EMBEDDING_MODELS,  # type: ignore
            extract_graph={
                "relationship_types": [],
                "strict_relationship_types": True,
            },
        )


def test_extract_graph_strict_flags_can_be_enabled() -> None:
    config = HyperGraphConfig(
        completion_models=DEFAULT_COMPLETION_MODELS,  # type: ignore
        embedding_models=DEFAULT_EMBEDDING_MODELS,  # type: ignore
        extract_graph={
            "entity_types": ["person"],
            "relationship_types": ["works_with"],
            "strict_entity_types": True,
            "strict_relationship_types": True,
        },
    )

    assert config.extract_graph.strict_entity_types is True
    assert config.extract_graph.strict_relationship_types is True
