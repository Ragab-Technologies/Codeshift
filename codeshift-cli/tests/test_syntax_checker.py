"""Tests for syntax checker."""

from codeshift.validator.syntax_checker import (
    SyntaxChecker,
    SyntaxCheckResult,
    quick_syntax_check,
)


class TestSyntaxChecker:
    """Tests for the SyntaxChecker class."""

    def test_valid_code(self):
        """Test checking valid Python code."""
        checker = SyntaxChecker()
        result = checker.check_code("x = 1 + 2")
        assert result.is_valid
        assert result.error_count == 0

    def test_invalid_code(self):
        """Test checking invalid Python code."""
        checker = SyntaxChecker()
        result = checker.check_code("def broken(")
        assert not result.is_valid
        assert result.error_count > 0

    def test_empty_code(self):
        """Test checking empty code."""
        checker = SyntaxChecker()
        result = checker.check_code("")
        assert result.is_valid

    def test_multiline_valid_code(self):
        """Test checking valid multiline code."""
        checker = SyntaxChecker()
        code = """
def hello():
    return "world"

class Foo:
    pass
"""
        result = checker.check_code(code)
        assert result.is_valid

    def test_multiline_invalid_code(self):
        """Test checking invalid multiline code."""
        checker = SyntaxChecker()
        code = """
def hello():
    return "world"

class Foo
    pass
"""
        result = checker.check_code(code)
        assert not result.is_valid

    def test_custom_python_version(self):
        """Test checker with custom Python version."""
        checker = SyntaxChecker(python_version=(3, 9))
        assert checker.python_version == (3, 9)


class TestSyntaxCheckerFile:
    """Tests for file-based syntax checking."""

    def test_check_valid_file(self, tmp_path):
        """Test checking a valid Python file."""
        file_path = tmp_path / "valid.py"
        file_path.write_text("x = 1 + 2\n")

        checker = SyntaxChecker()
        result = checker.check_file(file_path)
        assert result.is_valid
        assert result.file_path == file_path

    def test_check_invalid_file(self, tmp_path):
        """Test checking an invalid Python file."""
        file_path = tmp_path / "invalid.py"
        file_path.write_text("def broken(\n")

        checker = SyntaxChecker()
        result = checker.check_file(file_path)
        assert not result.is_valid
        assert result.file_path == file_path

    def test_check_nonexistent_file(self, tmp_path):
        """Test checking a file that doesn't exist."""
        file_path = tmp_path / "nonexistent.py"

        checker = SyntaxChecker()
        result = checker.check_file(file_path)
        assert not result.is_valid
        assert "Could not read file" in result.errors[0].message


class TestSyntaxCheckerDirectory:
    """Tests for directory-based syntax checking."""

    def test_check_directory_all_valid(self, tmp_path):
        """Test checking a directory with all valid files."""
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 2\n")

        checker = SyntaxChecker()
        results = checker.check_directory(tmp_path)
        assert len(results) == 0  # No errors

    def test_check_directory_with_invalid(self, tmp_path):
        """Test checking a directory with some invalid files."""
        (tmp_path / "valid.py").write_text("x = 1\n")
        (tmp_path / "invalid.py").write_text("def broken(\n")

        checker = SyntaxChecker()
        results = checker.check_directory(tmp_path)
        assert len(results) == 1
        assert not results[0].is_valid

    def test_check_directory_with_exclude(self, tmp_path):
        """Test checking a directory with exclusions."""
        (tmp_path / "valid.py").write_text("x = 1\n")
        (tmp_path / "excluded.py").write_text("def broken(\n")

        checker = SyntaxChecker()
        results = checker.check_directory(tmp_path, exclude_patterns=["excluded.py"])
        assert len(results) == 0

    def test_check_directory_nested(self, tmp_path):
        """Test checking a nested directory."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "a.py").write_text("x = 1\n")
        (subdir / "b.py").write_text("def broken(\n")

        checker = SyntaxChecker()
        results = checker.check_directory(tmp_path)
        assert len(results) == 1


class TestValidateTransform:
    """Tests for transform validation."""

    def test_valid_transform(self):
        """Test validating a valid transformation."""
        checker = SyntaxChecker()
        original = "x = old_func()"
        transformed = "x = new_func()"

        is_valid, issues = checker.validate_transform(original, transformed)
        assert is_valid
        assert len(issues) == 0

    def test_invalid_transform(self):
        """Test validating a transformation that breaks syntax."""
        checker = SyntaxChecker()
        original = "x = old_func()"
        transformed = "x = new_func("

        is_valid, issues = checker.validate_transform(original, transformed)
        assert not is_valid
        assert len(issues) > 0

    def test_invalid_original(self):
        """Test validating when original code is invalid."""
        checker = SyntaxChecker()
        original = "def broken("
        transformed = "def fixed(): pass"

        is_valid, issues = checker.validate_transform(original, transformed)
        assert is_valid  # Transformed is valid
        assert any("Original code has syntax errors" in issue for issue in issues)


class TestQuickSyntaxCheck:
    """Tests for quick_syntax_check function."""

    def test_quick_check_valid(self):
        """Test quick check with valid code."""
        assert quick_syntax_check("x = 1") is True

    def test_quick_check_invalid(self):
        """Test quick check with invalid code."""
        assert quick_syntax_check("def (") is False

    def test_quick_check_empty(self):
        """Test quick check with empty code."""
        assert quick_syntax_check("") is True


class TestSyntaxCheckResult:
    """Tests for SyntaxCheckResult class."""

    def test_error_count_property(self):
        """Test error_count property."""
        result = SyntaxCheckResult(is_valid=False, errors=[])
        assert result.error_count == 0

    def test_valid_result(self):
        """Test a valid result."""
        result = SyntaxCheckResult(is_valid=True)
        assert result.is_valid
        assert result.error_count == 0
