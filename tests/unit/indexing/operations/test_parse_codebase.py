# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Tests for the hierarchical codebase AST parser."""

from pathlib import Path

import pytest

from hypergraph.index.operations.parse_codebase.parser import parse_codebase

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_codebase"


@pytest.fixture()
def parsed():
    """Parse the sample_codebase fixture and return (entities, relationships)."""
    entities, relationships = parse_codebase(FIXTURES_DIR, skip_tests=False)
    return entities, relationships


class TestParseCodebase:
    """Test suite for parse_codebase on the sample_codebase fixture."""

    def test_entities_not_empty(self, parsed):
        entities, _ = parsed
        assert len(entities) > 0

    def test_relationships_not_empty(self, parsed):
        _, relationships = parsed
        assert len(relationships) > 0

    # ── Package entities ──

    def test_package_entities(self, parsed):
        entities, _ = parsed
        packages = entities[entities["type"] == "PACKAGE"]
        pkg_titles = set(packages["title"].tolist())
        assert "services" in pkg_titles

    # ── Module entities ──

    def test_module_entities(self, parsed):
        entities, _ = parsed
        modules = entities[entities["type"] == "MODULE"]
        module_titles = set(modules["title"].tolist())
        assert "models" in module_titles
        assert "utils" in module_titles
        assert "services.api" in module_titles

    def test_module_description_includes_classes(self, parsed):
        """Module description should list its classes."""
        entities, _ = parsed
        models_mod = entities[entities["title"] == "models"]
        assert len(models_mod) == 1
        desc = models_mod.iloc[0]["description"]
        assert "BaseModel" in desc

    # ── Class entities ──

    def test_class_entities(self, parsed):
        entities, _ = parsed
        classes = entities[entities["type"] == "CLASS"]
        class_titles = set(classes["title"].tolist())
        assert "models.BaseModel" in class_titles
        assert "models.User" in class_titles
        assert "models.AdminUser" in class_titles

    def test_class_description_includes_methods(self, parsed):
        """Class description should list its public method signatures."""
        entities, _ = parsed
        user_class = entities[entities["title"] == "models.User"]
        assert len(user_class) == 1
        desc = user_class.iloc[0]["description"]
        assert "greet" in desc

    # ── Function entities ──

    def test_function_entities(self, parsed):
        entities, _ = parsed
        functions = entities[entities["type"] == "FUNCTION"]
        function_titles = set(functions["title"].tolist())
        assert "utils.validate_email" in function_titles
        assert "utils.get_user_by_name" in function_titles
        assert "utils.create_admin" in function_titles
        assert "services.api.register_user" in function_titles

    # ── Method entities ──

    def test_method_entities(self, parsed):
        entities, _ = parsed
        methods = entities[entities["type"] == "METHOD"]
        method_titles = set(methods["title"].tolist())
        assert "models.BaseModel.save" in method_titles
        assert "models.User.__init__" in method_titles
        assert "models.User.greet" in method_titles

    # ── CONTAINS relationships ──

    def test_contains_package_to_module(self, parsed):
        _, relationships = parsed
        contains = relationships[
            relationships["description"].str.startswith("contains:")
        ]
        pkg_to_mod = contains[
            (contains["source"] == "services")
            & (contains["target"] == "services.api")
        ]
        assert len(pkg_to_mod) > 0

    def test_contains_module_to_class(self, parsed):
        _, relationships = parsed
        contains = relationships[
            relationships["description"].str.startswith("contains:")
        ]
        mod_to_class = contains[
            (contains["source"] == "models")
            & (contains["target"] == "models.BaseModel")
        ]
        assert len(mod_to_class) > 0

    def test_contains_class_to_method(self, parsed):
        _, relationships = parsed
        contains = relationships[
            relationships["description"].str.startswith("contains:")
        ]
        class_to_method = contains[
            (contains["source"] == "models.User")
            & (contains["target"] == "models.User.greet")
        ]
        assert len(class_to_method) > 0

    # ── INHERITS relationships ──

    def test_inherits_relationships(self, parsed):
        _, relationships = parsed
        inherits = relationships[
            relationships["description"].str.startswith("inherits:")
        ]
        user_inherits = inherits[
            (inherits["source"] == "models.User")
            & (inherits["target"] == "models.BaseModel")
        ]
        assert len(user_inherits) > 0

        admin_inherits = inherits[
            (inherits["source"] == "models.AdminUser")
            & (inherits["target"] == "models.User")
        ]
        assert len(admin_inherits) > 0

    # ── IMPORTS relationships ──

    def test_imports_relationships(self, parsed):
        _, relationships = parsed
        imports = relationships[
            relationships["description"].str.startswith("imports:")
        ]
        utils_os = imports[
            (imports["source"] == "utils") & (imports["target"] == "os")
        ]
        assert len(utils_os) > 0

    # ── No CALLS or DECORATES ──

    def test_no_calls_relationships(self, parsed):
        """Hierarchical parser does not extract CALLS."""
        _, relationships = parsed
        calls = relationships[
            relationships["description"].str.startswith("calls:")
        ]
        assert len(calls) == 0

    def test_no_decorates_relationships(self, parsed):
        """Hierarchical parser does not extract DECORATES."""
        _, relationships = parsed
        decorates = relationships[
            relationships["description"].str.startswith("decorates:")
        ]
        assert len(decorates) == 0

    # ── Docstrings ──

    def test_docstrings_captured(self, parsed):
        entities, _ = parsed
        user_class = entities[entities["title"] == "models.User"]
        assert len(user_class) == 1
        desc = user_class.iloc[0]["description"]
        assert "user in the system" in desc.lower()

    # ── Error handling ──

    def test_nonexistent_dir_raises(self):
        with pytest.raises(FileNotFoundError):
            parse_codebase("/nonexistent/path/to/code")

    # ── Skip tests option ──

    def test_skip_tests_filters_test_files(self):
        """When skip_tests=True, test files should be excluded."""
        entities, _ = parse_codebase(FIXTURES_DIR, skip_tests=True)
        # Should still have core modules
        module_titles = set(entities[entities["type"] == "MODULE"]["title"].tolist())
        assert "models" in module_titles
