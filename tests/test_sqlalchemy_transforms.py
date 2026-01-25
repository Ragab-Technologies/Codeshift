"""Tests for SQLAlchemy transformation."""

from codeshift.migrator.transforms.sqlalchemy_transformer import (
    transform_sqlalchemy,
)


class TestImportTransforms:
    """Tests for SQLAlchemy import transformations."""

    def test_declarative_base_import_transform(self):
        """Test declarative_base import transform to DeclarativeBase."""
        code = """from sqlalchemy.ext.declarative import declarative_base"""
        result, changes = transform_sqlalchemy(code)
        assert "from sqlalchemy.orm import DeclarativeBase" in result
        assert "declarative_base" not in result
        assert any(c.transform_name == "import_declarative_base" for c in changes)

    def test_backref_import_removed(self):
        """Test backref import is removed with warning."""
        code = """from sqlalchemy.orm import relationship, backref"""
        result, changes = transform_sqlalchemy(code)
        assert "backref" not in result
        assert "relationship" in result
        assert any(c.transform_name == "remove_backref_import" for c in changes)

    def test_backref_only_import_removed(self):
        """Test that import is removed when backref is the only import."""
        code = """from sqlalchemy.orm import backref"""
        result, changes = transform_sqlalchemy(code)
        assert "backref" not in result or result.strip() == ""
        assert any(c.transform_name == "remove_backref_import" for c in changes)

    def test_non_sqlalchemy_import_unchanged(self):
        """Test that non-SQLAlchemy imports are unchanged."""
        code = """from datetime import datetime"""
        result, changes = transform_sqlalchemy(code)
        assert result == code
        assert len(changes) == 0


class TestDeclarativeBaseTransforms:
    """Tests for declarative_base() call transforms."""

    def test_declarative_base_call_warning(self):
        """Test declarative_base() call generates warning."""
        code = """Base = declarative_base()"""
        result, changes = transform_sqlalchemy(code)
        assert any(c.transform_name == "declarative_base_to_class" for c in changes)
        assert any(c.confidence < 1.0 for c in changes)


class TestCreateEngineTransforms:
    """Tests for create_engine parameter transforms."""

    def test_create_engine_future_flag_removed(self):
        """Test future=True is removed from create_engine."""
        code = """engine = create_engine("sqlite:///db.sqlite", future=True)"""
        result, changes = transform_sqlalchemy(code)
        assert "future=" not in result
        assert any(c.transform_name == "remove_future_flag" for c in changes)

    def test_create_engine_without_future_unchanged(self):
        """Test create_engine without future flag is unchanged."""
        code = """engine = create_engine("sqlite:///db.sqlite", echo=True)"""
        result, changes = transform_sqlalchemy(code)
        assert "echo=True" in result
        assert not any(c.transform_name == "remove_future_flag" for c in changes)


class TestSyntaxErrorHandling:
    """Tests for syntax error handling."""

    def test_syntax_error_returns_original(self):
        """Test that syntax errors return original code."""
        code = """from sqlalchemy import"""
        result, changes = transform_sqlalchemy(code)
        assert result == code
        assert len(changes) == 0


class TestComplexTransforms:
    """Tests for complex multi-transform scenarios."""

    def test_multiple_transforms_in_one_file(self):
        """Test multiple transforms applied to one file."""
        code = """from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy import create_engine

engine = create_engine("sqlite:///test.db", future=True)
Base = declarative_base()
"""
        result, changes = transform_sqlalchemy(code)
        assert "DeclarativeBase" in result
        assert "future=" not in result
        assert len(changes) >= 3
