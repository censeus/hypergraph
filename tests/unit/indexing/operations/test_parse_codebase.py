# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Tests for the codebase AST parser."""

from pathlib import Path

import pytest

from hypergraph.index.operations.parse_codebase.parser import parse_codebase

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_codebase"


@pytest.fixture()
def parsed():
    """Parse the sample_codebase fixture and return (entities, relationships)."""
    entities, relationships = parse_codebase(FIXTURES_DIR)
    return entities, relationships


class TestParseCodebase:
    """Test suite for parse_codebase on the sample_codebase fixture."""

    def test_entities_not_empty(self, parsed):
        entities, _ = parsed
        assert len(entities) > 0

    def test_relationships_not_empty(self, parsed):
        _, relationships = parsed
        assert len(relationships) > 0

    def test_module_entities(self, parsed):
        entities, _ = parsed
        modules = entities[entities["type"] == "MODULE"]
        module_titles = set(modules["title"].tolist())
        # Expect at least these modules
        assert "models" in module_titles
        assert "utils" in module_titles
        assert "services.api" in module_titles

    def test_class_entities(self, parsed):
        entities, _ = parsed
        classes = entities[entities["type"] == "CLASS"]
        class_titles = set(classes["title"].tolist())
        assert "models.BaseModel" in class_titles
        assert "models.User" in class_titles
        assert "models.AdminUser" in class_titles

    def test_function_entities(self, parsed):
        entities, _ = parsed
        functions = entities[entities["type"] == "FUNCTION"]
        function_titles = set(functions["title"].tolist())
        assert "utils.validate_email" in function_titles
        assert "utils.get_user_by_name" in function_titles
        assert "utils.create_admin" in function_titles
        assert "services.api.register_user" in function_titles

    def test_method_entities(self, parsed):
        entities, _ = parsed
        methods = entities[entities["type"] == "METHOD"]
        method_titles = set(methods["title"].tolist())
        assert "models.BaseModel.save" in method_titles
        assert "models.User.__init__" in method_titles
        assert "models.User.greet" in method_titles

    def test_contains_relationships(self, parsed):
        _, relationships = parsed
        contains = relationships[
            relationships["description"].str.startswith("contains:")
        ]
        # models module should contain BaseModel class
        mod_to_class = contains[
            (contains["source"] == "models")
            & (contains["target"] == "models.BaseModel")
        ]
        assert len(mod_to_class) > 0

    def test_inherits_relationships(self, parsed):
        _, relationships = parsed
        inherits = relationships[
            relationships["description"].str.startswith("inherits:")
        ]
        # User extends BaseModel
        user_inherits = inherits[
            (inherits["source"] == "models.User")
            & (inherits["target"] == "models.BaseModel")
        ]
        assert len(user_inherits) > 0

        # AdminUser extends User
        admin_inherits = inherits[
            (inherits["source"] == "models.AdminUser")
            & (inherits["target"] == "models.User")
        ]
        assert len(admin_inherits) > 0

    def test_imports_relationships(self, parsed):
        _, relationships = parsed
        imports = relationships[
            relationships["description"].str.startswith("imports:")
        ]
        # utils imports os
        utils_os = imports[
            (imports["source"] == "utils") & (imports["target"] == "os")
        ]
        assert len(utils_os) > 0

    def test_decorates_relationships(self, parsed):
        _, relationships = parsed
        decorates = relationships[
            relationships["description"].str.startswith("decorates:")
        ]
        # lru_cache decorates get_user_by_name
        assert len(decorates) > 0

    def test_calls_relationships(self, parsed):
        _, relationships = parsed
        calls = relationships[
            relationships["description"].str.startswith("calls:")
        ]
        # create_admin calls validate_email
        admin_calls = calls[
            (calls["source"] == "utils.create_admin")
        ]
        assert len(admin_calls) > 0

    def test_docstrings_captured(self, parsed):
        entities, _ = parsed
        user_class = entities[entities["title"] == "models.User"]
        assert len(user_class) == 1
        desc = user_class.iloc[0]["description"]
        assert "user in the system" in desc.lower()

    def test_no_calls_option(self):
        """Parser should skip CALLS relationships when extract_calls=False."""
        _, relationships = parse_codebase(FIXTURES_DIR, extract_calls=False)
        calls = relationships[
            relationships["description"].str.startswith("calls:")
        ]
        assert len(calls) == 0

    def test_no_decorators_option(self):
        """Parser should skip DECORATES relationships when extract_decorators=False."""
        _, relationships = parse_codebase(
            FIXTURES_DIR, extract_decorators=False
        )
        decorates = relationships[
            relationships["description"].str.startswith("decorates:")
        ]
        assert len(decorates) == 0

    def test_nonexistent_dir_raises(self):
        with pytest.raises(FileNotFoundError):
            parse_codebase("/nonexistent/path/to/code")
