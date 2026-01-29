"""Nox configuration for linting and testing."""

import nox

nox.options.sessions = ["lint", "test"]


@nox.session
def lint(session: nox.Session) -> None:
    """Run linting and auto-fix issues (ruff, black, mypy)."""
    session.install("-e", ".[dev]")
    session.run("ruff", "check", "--fix", "codeshift", "tests")
    session.run("black", "codeshift", "tests")
    session.run("mypy", "codeshift", "--ignore-missing-imports")


@nox.session
def test(session: nox.Session) -> None:
    """Run the test suite."""
    session.install("-e", ".[dev]")
    session.run("pytest")


@nox.session
def test_cov(session: nox.Session) -> None:
    """Run tests with coverage."""
    session.install("-e", ".[dev]")
    session.run("pytest", "--cov=codeshift", "--cov-report=term-missing")


@nox.session
def format(session: nox.Session) -> None:
    """Format code with black."""
    session.install("black==24.*")
    session.run("black", "codeshift", "tests")
