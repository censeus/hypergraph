# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

import pandas as pd

from hypergraph.index.workflows.extract_graph import (
    TypeProposalCanonizationGroup,
    _apply_type_alias_mapping,
    _build_type_alias_mapping,
)


def test_apply_type_alias_mapping_merges_alias_rows() -> None:
    proposals = pd.DataFrame([
        {
            "proposal_kind": "entity",
            "canonical_label": "company",
            "occurrences": 2,
            "raw_labels": ["company"],
            "sample_descriptions": ["Company entity"],
        },
        {
            "proposal_kind": "entity",
            "canonical_label": "companies",
            "occurrences": 3,
            "raw_labels": ["companies", "org"],
            "sample_descriptions": ["Companies entity"],
        },
    ])

    alias_mapping = _build_type_alias_mapping([
        TypeProposalCanonizationGroup(
            proposal_kind="entity",
            canonical_label="company",
            aliases=["companies"],
        )
    ])
    merged = _apply_type_alias_mapping(proposals, alias_mapping)

    assert len(merged) == 1
    assert merged["canonical_label"].tolist() == ["company"]
    assert merged["occurrences"].tolist() == [5]
    assert sorted(merged["raw_labels"].iloc[0]) == ["companies", "company", "org"]


def test_alias_mapping_keeps_entity_and_relationship_kinds_separate() -> None:
    proposals = pd.DataFrame([
        {
            "proposal_kind": "entity",
            "canonical_label": "acquisition",
            "occurrences": 1,
            "raw_labels": ["acquisition"],
            "sample_descriptions": ["Entity acquisition"],
        },
        {
            "proposal_kind": "relationship",
            "canonical_label": "acquisition",
            "occurrences": 4,
            "raw_labels": ["acquisition"],
            "sample_descriptions": ["acquisition: A acquired B"],
        },
    ])

    alias_mapping = _build_type_alias_mapping([
        TypeProposalCanonizationGroup(
            proposal_kind="relationship",
            canonical_label="acquires",
            aliases=["acquisition"],
        )
    ])
    merged = _apply_type_alias_mapping(proposals, alias_mapping)

    assert len(merged) == 2
    entity_row = merged[merged["proposal_kind"] == "entity"].iloc[0]
    relationship_row = merged[merged["proposal_kind"] == "relationship"].iloc[0]

    assert entity_row["canonical_label"] == "acquisition"
    assert relationship_row["canonical_label"] == "acquires"
