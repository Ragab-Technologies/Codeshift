"""Tests for the knowledge base module."""

import pytest

from pyresolve.knowledge_base import (
    BreakingChange,
    ChangeType,
    KnowledgeBaseLoader,
    LibraryKnowledge,
    Severity,
)


class TestBreakingChange:
    """Tests for BreakingChange model."""

    def test_from_dict(self):
        """Test creating BreakingChange from dictionary."""
        data = {
            "symbol": "BaseModel.Config",
            "change_type": "renamed",
            "severity": "high",
            "from_version": "1.0",
            "to_version": "2.0",
            "description": "Config class replaced with ConfigDict",
            "replacement": "model_config = ConfigDict(...)",
            "has_deterministic_transform": True,
            "transform_name": "config_to_configdict",
        }

        change = BreakingChange.from_dict(data)

        assert change.symbol == "BaseModel.Config"
        assert change.change_type == ChangeType.RENAMED
        assert change.severity == Severity.HIGH
        assert change.from_version == "1.0"
        assert change.to_version == "2.0"
        assert change.has_deterministic_transform is True
        assert change.transform_name == "config_to_configdict"

    def test_from_dict_minimal(self):
        """Test creating BreakingChange with minimal data."""
        data = {
            "symbol": ".dict()",
            "change_type": "renamed",
            "severity": "medium",
            "from_version": "1.0",
            "to_version": "2.0",
            "description": "dict() renamed to model_dump()",
        }

        change = BreakingChange.from_dict(data)

        assert change.symbol == ".dict()"
        assert change.replacement is None
        assert change.has_deterministic_transform is False
        assert change.transform_name is None


class TestLibraryKnowledge:
    """Tests for LibraryKnowledge model."""

    def test_from_dict(self):
        """Test creating LibraryKnowledge from dictionary."""
        data = {
            "name": "pydantic",
            "display_name": "Pydantic",
            "description": "Data validation library",
            "migration_guide_url": "https://docs.pydantic.dev/migration/",
            "supported_migrations": [
                {"from": "1.0", "to": "2.0"},
            ],
            "breaking_changes": [
                {
                    "symbol": ".dict()",
                    "change_type": "renamed",
                    "severity": "high",
                    "from_version": "1.0",
                    "to_version": "2.0",
                    "description": "dict() renamed to model_dump()",
                    "has_deterministic_transform": True,
                },
            ],
        }

        knowledge = LibraryKnowledge.from_dict(data)

        assert knowledge.name == "pydantic"
        assert knowledge.display_name == "Pydantic"
        assert len(knowledge.supported_migrations) == 1
        assert knowledge.supported_migrations[0] == ("1.0", "2.0")
        assert len(knowledge.breaking_changes) == 1
        assert knowledge.breaking_changes[0].symbol == ".dict()"

    def test_get_deterministic_transforms(self):
        """Test filtering for deterministic transforms."""
        data = {
            "name": "test",
            "display_name": "Test",
            "supported_migrations": [{"from": "1.0", "to": "2.0"}],
            "breaking_changes": [
                {
                    "symbol": "a",
                    "change_type": "renamed",
                    "severity": "low",
                    "from_version": "1.0",
                    "to_version": "2.0",
                    "description": "a",
                    "has_deterministic_transform": True,
                },
                {
                    "symbol": "b",
                    "change_type": "removed",
                    "severity": "high",
                    "from_version": "1.0",
                    "to_version": "2.0",
                    "description": "b",
                    "has_deterministic_transform": False,
                },
            ],
        }

        knowledge = LibraryKnowledge.from_dict(data)
        deterministic = knowledge.get_deterministic_transforms("1.0", "2.0")

        assert len(deterministic) == 1
        assert deterministic[0].symbol == "a"


class TestKnowledgeBaseLoader:
    """Tests for KnowledgeBaseLoader."""

    def test_get_supported_libraries(self):
        """Test listing supported libraries."""
        loader = KnowledgeBaseLoader()
        libraries = loader.get_supported_libraries()

        assert "pydantic" in libraries

    def test_load_pydantic(self):
        """Test loading the pydantic knowledge base."""
        loader = KnowledgeBaseLoader()
        knowledge = loader.load("pydantic")

        assert knowledge.name == "pydantic"
        assert knowledge.display_name == "Pydantic"
        assert len(knowledge.breaking_changes) > 0

        # Check for specific known changes
        symbols = [c.symbol for c in knowledge.breaking_changes]
        assert "BaseModel.Config" in symbols
        assert "@validator" in symbols
        assert ".dict()" in symbols

    def test_load_nonexistent(self):
        """Test loading a non-existent library."""
        loader = KnowledgeBaseLoader()

        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent_library")

    def test_caching(self):
        """Test that knowledge bases are cached."""
        loader = KnowledgeBaseLoader()

        knowledge1 = loader.load("pydantic")
        knowledge2 = loader.load("pydantic")

        assert knowledge1 is knowledge2

    def test_clear_cache(self):
        """Test clearing the cache."""
        loader = KnowledgeBaseLoader()

        loader.load("pydantic")
        loader.clear_cache()
        assert "pydantic" not in loader._cache

    def test_is_migration_supported(self):
        """Test checking if a migration is supported."""
        loader = KnowledgeBaseLoader()

        assert loader.is_migration_supported("pydantic", "1.0", "2.0")
        assert not loader.is_migration_supported("nonexistent", "1.0", "2.0")
