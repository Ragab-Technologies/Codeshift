"""Syntax checker for validating transformed code."""

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SyntaxIssue:
    """Represents a syntax error in code."""

    message: str
    line_number: int
    column: int
    line_text: str | None = None


@dataclass
class SyntaxCheckResult:
    """Result of a syntax check."""

    is_valid: bool
    file_path: Path | None = None
    errors: list[SyntaxIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        """Get the number of errors."""
        return len(self.errors)


class SyntaxChecker:
    """Validates Python code syntax."""

    def __init__(self, python_version: tuple[int, int] | None = None):
        """Initialize the syntax checker.

        Args:
            python_version: Target Python version as (major, minor).
                          Defaults to current Python version.
        """
        if python_version is None:
            python_version = (sys.version_info.major, sys.version_info.minor)
        self.python_version = python_version

    def check_code(self, source_code: str, filename: str = "<string>") -> SyntaxCheckResult:
        """Check if source code has valid Python syntax.

        Args:
            source_code: The Python source code to check
            filename: Optional filename for error messages

        Returns:
            SyntaxCheckResult with validation status
        """
        try:
            # First, try to compile the code
            compile(source_code, filename, "exec")

            # Then parse with AST for more detailed checking
            ast.parse(source_code, filename=filename)

            return SyntaxCheckResult(is_valid=True)

        except SyntaxError as e:
            error = SyntaxIssue(
                message=str(e.msg) if hasattr(e, "msg") else str(e),
                line_number=e.lineno or 0,
                column=e.offset or 0,
                line_text=e.text,
            )
            return SyntaxCheckResult(
                is_valid=False,
                errors=[error],
            )

    def check_file(self, file_path: Path) -> SyntaxCheckResult:
        """Check if a Python file has valid syntax.

        Args:
            file_path: Path to the Python file

        Returns:
            SyntaxCheckResult with validation status
        """
        try:
            source_code = file_path.read_text()
        except Exception as e:
            return SyntaxCheckResult(
                is_valid=False,
                file_path=file_path,
                errors=[
                    SyntaxIssue(
                        message=f"Could not read file: {e}",
                        line_number=0,
                        column=0,
                    )
                ],
            )

        result = self.check_code(source_code, str(file_path))
        result.file_path = file_path
        return result

    def check_directory(
        self, directory: Path, exclude_patterns: list[str] | None = None
    ) -> list[SyntaxCheckResult]:
        """Check all Python files in a directory.

        Args:
            directory: Path to the directory
            exclude_patterns: Glob patterns to exclude

        Returns:
            List of SyntaxCheckResult for each file with errors
        """
        import fnmatch

        exclude_patterns = exclude_patterns or []
        results = []

        for file_path in directory.rglob("*.py"):
            relative_path = str(file_path.relative_to(directory))

            # Check exclude patterns
            excluded = False
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(relative_path, pattern):
                    excluded = True
                    break

            if excluded:
                continue

            result = self.check_file(file_path)
            if not result.is_valid:
                results.append(result)

        return results

    def validate_transform(self, original: str, transformed: str) -> tuple[bool, list[str]]:
        """Validate that a transformation didn't break syntax.

        Args:
            original: Original source code
            transformed: Transformed source code

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        # Check original syntax (should be valid)
        original_result = self.check_code(original, "<original>")
        if not original_result.is_valid:
            issues.append("Original code has syntax errors")

        # Check transformed syntax
        transformed_result = self.check_code(transformed, "<transformed>")
        if not transformed_result.is_valid:
            for error in transformed_result.errors:
                issues.append(f"Line {error.line_number}: {error.message}")
            return False, issues

        return True, issues


def quick_syntax_check(source_code: str) -> bool:
    """Quick check if code has valid Python syntax.

    Args:
        source_code: The Python source code to check

    Returns:
        True if syntax is valid, False otherwise
    """
    try:
        compile(source_code, "<string>", "exec")
        return True
    except SyntaxError:
        return False
