"""Tests for the code scanner module."""

from pathlib import Path

import pytest

from codeshift.scanner import CodeScanner, DependencyParser


class TestCodeScanner:
    """Tests for CodeScanner."""

    def test_scan_file_with_pydantic_imports(self, tmp_path: Path):
        """Test scanning a file with Pydantic imports."""
        test_file = tmp_path / "models.py"
        test_file.write_text(
            """
from pydantic import BaseModel, Field, validator

class User(BaseModel):
    name: str = Field(..., min_length=1)

    @validator("name")
    def validate_name(cls, v):
        return v.strip()
"""
        )

        scanner = CodeScanner("pydantic")
        imports, usages = scanner.scan_file(test_file)

        assert len(imports) == 1
        assert imports[0].module == "pydantic"
        assert "BaseModel" in imports[0].names
        assert "Field" in imports[0].names
        assert "validator" in imports[0].names
        assert imports[0].is_from_import is True

    def test_scan_file_with_method_calls(self, tmp_path: Path):
        """Test scanning for method calls like .dict()."""
        test_file = tmp_path / "utils.py"
        test_file.write_text(
            """
from pydantic import BaseModel

class User(BaseModel):
    name: str

def get_dict(user: User):
    return user.dict()

def get_schema():
    return User.schema()
"""
        )

        scanner = CodeScanner("pydantic")
        imports, usages = scanner.scan_file(test_file)

        assert len(imports) == 1

        # Check for method call usages
        method_usages = [u for u in usages if u.usage_type == "method_call"]
        assert any(u.symbol == ".dict()" for u in method_usages)
        assert any(u.symbol == ".schema()" for u in method_usages)

    def test_scan_file_with_decorators(self, tmp_path: Path):
        """Test scanning for decorator usages."""
        test_file = tmp_path / "models.py"
        test_file.write_text(
            """
from pydantic import BaseModel, validator, root_validator

class User(BaseModel):
    name: str
    email: str

    @validator("name")
    def validate_name(cls, v):
        return v

    @root_validator
    def validate_model(cls, values):
        return values
"""
        )

        scanner = CodeScanner("pydantic")
        imports, usages = scanner.scan_file(test_file)

        decorator_usages = [u for u in usages if u.usage_type == "decorator"]
        assert any(u.symbol == "validator" for u in decorator_usages)
        assert any(u.symbol == "root_validator" for u in decorator_usages)

    def test_scan_file_no_pydantic(self, tmp_path: Path):
        """Test scanning a file without Pydantic imports."""
        test_file = tmp_path / "other.py"
        test_file.write_text(
            """
import json

def parse_json(data):
    return json.loads(data)
"""
        )

        scanner = CodeScanner("pydantic")
        imports, usages = scanner.scan_file(test_file)

        assert len(imports) == 0
        assert len(usages) == 0

    def test_scan_directory(self, tmp_path: Path):
        """Test scanning a directory."""
        # Create test files
        (tmp_path / "models.py").write_text(
            """
from pydantic import BaseModel

class User(BaseModel):
    name: str
"""
        )
        (tmp_path / "utils.py").write_text(
            """
from pydantic import Field

x = Field(default=None)
"""
        )
        (tmp_path / "other.py").write_text(
            """
import json
"""
        )

        scanner = CodeScanner("pydantic")
        result = scanner.scan_directory(tmp_path)

        assert result.files_scanned == 3
        assert result.files_with_imports == 2
        assert len(result.imports) == 2

    def test_scan_directory_with_exclude(self, tmp_path: Path):
        """Test scanning with exclude patterns."""
        # Create test files
        (tmp_path / "models.py").write_text("from pydantic import BaseModel")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_models.py").write_text("from pydantic import BaseModel")

        scanner = CodeScanner("pydantic", exclude_patterns=["tests/*"])
        result = scanner.scan_directory(tmp_path)

        assert result.files_scanned == 1
        assert result.files_with_imports == 1

    def test_scan_file_syntax_error(self, tmp_path: Path):
        """Test handling of syntax errors."""
        test_file = tmp_path / "bad.py"
        test_file.write_text("def broken(:\n    pass")

        scanner = CodeScanner("pydantic")

        with pytest.raises(SyntaxError):
            scanner.scan_file(test_file)


class TestDependencyParser:
    """Tests for DependencyParser."""

    def test_parse_pyproject_toml(self, tmp_path: Path):
        """Test parsing pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test"
dependencies = [
    "pydantic>=1.10,<2.0",
    "fastapi>=0.100.0",
]
"""
        )

        parser = DependencyParser(tmp_path)
        deps = parser.parse_pyproject_toml()

        assert len(deps) == 2
        pydantic_dep = next(d for d in deps if d.name == "pydantic")
        # Version spec may be reordered by packaging library
        assert pydantic_dep.version_spec is not None
        assert ">=1.10" in pydantic_dep.version_spec
        assert "<2.0" in pydantic_dep.version_spec

    def test_parse_requirements_txt(self, tmp_path: Path):
        """Test parsing requirements.txt."""
        requirements = tmp_path / "requirements.txt"
        requirements.write_text(
            """
# Core dependencies
pydantic>=1.10
requests==2.28.0
# Dev dependencies
pytest>=7.0
"""
        )

        parser = DependencyParser(tmp_path)
        deps = parser.parse_requirements_txt()

        assert len(deps) == 3
        assert any(d.name == "pydantic" for d in deps)
        assert any(d.name == "requests" for d in deps)
        assert any(d.name == "pytest" for d in deps)

    def test_get_dependency(self, tmp_path: Path):
        """Test getting a specific dependency."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
dependencies = ["pydantic>=1.10,<2.0"]
"""
        )

        parser = DependencyParser(tmp_path)
        dep = parser.get_dependency("pydantic")

        assert dep is not None
        assert dep.name == "pydantic"
        # Version spec may be reordered by packaging library
        assert dep.version_spec is not None
        assert ">=1.10" in dep.version_spec
        assert "<2.0" in dep.version_spec

    def test_get_dependency_not_found(self, tmp_path: Path):
        """Test getting a dependency that doesn't exist."""
        parser = DependencyParser(tmp_path)
        dep = parser.get_dependency("nonexistent")

        assert dep is None

    def test_dependency_min_version(self, tmp_path: Path):
        """Test getting minimum version from dependency."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
dependencies = ["pydantic>=1.10.5,<2.0"]
"""
        )

        parser = DependencyParser(tmp_path)
        dep = parser.get_dependency("pydantic")

        assert dep.min_version is not None
        assert str(dep.min_version) == "1.10.5"

    def test_is_version_compatible(self, tmp_path: Path):
        """Test version compatibility checking."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
dependencies = ["pydantic>=1.10,<2.0"]
"""
        )

        parser = DependencyParser(tmp_path)
        dep = parser.get_dependency("pydantic")

        assert dep.is_version_compatible("1.10.5")
        assert dep.is_version_compatible("1.11.0")
        assert not dep.is_version_compatible("2.0.0")
        assert not dep.is_version_compatible("1.9.0")
