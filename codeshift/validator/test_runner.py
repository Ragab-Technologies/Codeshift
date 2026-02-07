"""Test runner for validating migrations."""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestResult:
    """Result of running tests."""

    success: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    duration: float = 0.0
    error_message: str | None = None

    @property
    def summary(self) -> str:
        """Get a summary string of the test results."""
        if self.success:
            return f"✓ {self.tests_passed}/{self.tests_run} tests passed"
        return f"✗ {self.tests_failed}/{self.tests_run} tests failed"


class TestRunner:
    """Runs project tests to validate migrations."""

    # Allowed argument patterns for test runner extra_args
    _SAFE_ARG_PATTERNS = [
        re.compile(r"^-[vqsx]$"),  # Single-char flags
        re.compile(r"^--tb=(short|long|line|no|auto)$"),  # Traceback style
        re.compile(r"^--maxfail=\d+$"),  # Max failures
        re.compile(r"^--(collect-only|co)$"),  # Collection only
        re.compile(r"^--import-mode=(prepend|append|importlib)$"),  # Import mode
        re.compile(r"^-k\s?.+$"),  # Test selection expression
        re.compile(r"^-m\s?.+$"),  # Marker expression
        re.compile(r"^--no-header$"),  # Suppress header
        re.compile(r"^--timeout=\d+$"),  # Timeout
    ]

    def __init__(
        self,
        project_path: Path,
        test_command: list[str] | None = None,
        timeout: int = 300,
    ):
        """Initialize the test runner.

        Args:
            project_path: Path to the project root
            test_command: Custom test command. Defaults to pytest detection.
            timeout: Maximum time in seconds to run tests
        """
        self.project_path = project_path
        self.test_command = test_command or self._detect_test_command()
        self.timeout = timeout

    def _detect_test_command(self) -> list[str]:
        """Detect the appropriate test command for the project."""
        # Check for pytest
        if (
            (self.project_path / "pytest.ini").exists()
            or (self.project_path / "pyproject.toml").exists()
            or (self.project_path / "tests").exists()
        ):
            return [sys.executable, "-m", "pytest", "-v", "--tb=short"]

        # Check for unittest
        if (self.project_path / "tests").exists():
            return [sys.executable, "-m", "unittest", "discover", "-v"]

        # Default to pytest
        return [sys.executable, "-m", "pytest", "-v", "--tb=short"]

    @classmethod
    def _validate_extra_args(cls, extra_args: list[str]) -> list[str]:
        """Validate that extra args match safe patterns.

        Args:
            extra_args: Arguments to validate.

        Returns:
            List of validated, safe arguments.
        """
        validated = []
        for arg in extra_args:
            # Reject args containing shell metacharacters
            if any(c in arg for c in ";|&$`\\'\"\n\r"):
                continue
            # Check against safe patterns
            if any(pattern.match(arg) for pattern in cls._SAFE_ARG_PATTERNS):
                validated.append(arg)
        return validated

    @staticmethod
    def _validate_specific_tests(specific_tests: list[str], project_path: Path) -> list[str]:
        """Validate that specific test paths are within the project.

        Args:
            specific_tests: Test file paths or patterns to validate.
            project_path: The project root directory.

        Returns:
            List of validated test paths.
        """
        validated = []
        for test in specific_tests:
            # Reject anything with shell metacharacters
            if any(c in test for c in ";|&$`\\'\"\n\r"):
                continue
            # Resolve and check it's within the project
            resolved = (project_path / test).resolve()
            if resolved.is_relative_to(project_path.resolve()):
                validated.append(test)
        return validated

    def run(
        self,
        specific_tests: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> TestResult:
        """Run the project tests.

        Args:
            specific_tests: List of specific test files or patterns to run
            extra_args: Additional arguments to pass to the test runner

        Returns:
            TestResult with the outcome
        """
        command = self.test_command.copy()

        if extra_args:
            command.extend(self._validate_extra_args(extra_args))

        if specific_tests:
            command.extend(self._validate_specific_tests(specific_tests, self.project_path))

        try:
            result = subprocess.run(
                command,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            # Parse pytest output
            tests_run, tests_passed, tests_failed, tests_skipped = self._parse_pytest_output(
                result.stdout + result.stderr
            )

            return TestResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                tests_run=tests_run,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                tests_skipped=tests_skipped,
            )

        except subprocess.TimeoutExpired:
            return TestResult(
                success=False,
                exit_code=-1,
                error_message=f"Tests timed out after {self.timeout} seconds",
            )
        except FileNotFoundError as e:
            return TestResult(
                success=False,
                exit_code=-1,
                error_message=f"Test command not found: {e}",
            )
        except Exception as e:
            return TestResult(
                success=False,
                exit_code=-1,
                error_message=f"Error running tests: {e}",
            )

    def _parse_pytest_output(self, output: str) -> tuple[int, int, int, int]:
        """Parse pytest output to extract test counts.

        Args:
            output: Combined stdout and stderr from pytest

        Returns:
            Tuple of (total, passed, failed, skipped)
        """
        # Look for pytest summary line like "5 passed, 2 failed, 1 skipped"
        # or "1 passed in 0.05s"
        passed = 0
        failed = 0
        skipped = 0
        errors = 0

        # Match patterns like "5 passed", "2 failed", etc.
        passed_match = re.search(r"(\d+) passed", output)
        if passed_match:
            passed = int(passed_match.group(1))

        failed_match = re.search(r"(\d+) failed", output)
        if failed_match:
            failed = int(failed_match.group(1))

        skipped_match = re.search(r"(\d+) skipped", output)
        if skipped_match:
            skipped = int(skipped_match.group(1))

        error_match = re.search(r"(\d+) error", output)
        if error_match:
            errors = int(error_match.group(1))

        total = passed + failed + skipped + errors
        return total, passed, failed + errors, skipped

    def run_quick_check(self) -> TestResult:
        """Run a quick smoke test (collection only, no execution).

        Returns:
            TestResult indicating if tests can be collected
        """
        command = self.test_command.copy()
        command.extend(["--collect-only", "-q"])

        try:
            result = subprocess.run(
                command,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Count collected tests
            tests_collected = 0
            for line in result.stdout.splitlines():
                if "test" in line.lower() and "::" in line:
                    tests_collected += 1

            return TestResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                tests_run=tests_collected,
            )

        except Exception as e:
            return TestResult(
                success=False,
                exit_code=-1,
                error_message=f"Error collecting tests: {e}",
            )


def run_tests(project_path: Path, timeout: int = 300) -> TestResult:
    """Convenience function to run tests for a project.

    Args:
        project_path: Path to the project
        timeout: Maximum time in seconds

    Returns:
        TestResult with the outcome
    """
    runner = TestRunner(project_path, timeout=timeout)
    return runner.run()
