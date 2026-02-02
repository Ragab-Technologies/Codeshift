"""Documentation quality metric calculator."""

import logging
from pathlib import Path
from typing import Any

import libcst as cst

from codeshift.health.metrics import BaseMetricCalculator
from codeshift.health.models import MetricCategory, MetricResult

logger = logging.getLogger(__name__)


class DocumentationCalculator(BaseMetricCalculator):
    """Calculates documentation score (10% weight).

    Score based on:
    - Type hints coverage: 70% of score
    - Docstring coverage: 30% of score
    """

    @property
    def category(self) -> MetricCategory:
        return MetricCategory.DOCUMENTATION

    @property
    def weight(self) -> float:
        return 0.10

    def calculate(self, project_path: Path, **kwargs: Any) -> MetricResult:
        """Calculate the documentation score.

        Args:
            project_path: Path to the project

        Returns:
            MetricResult with documentation score
        """
        # Find all Python files
        python_files = list(project_path.rglob("*.py"))

        # Exclude common non-source directories
        excluded_patterns = [
            ".venv",
            "venv",
            ".git",
            "__pycache__",
            ".tox",
            ".eggs",
            "build",
            "dist",
            ".mypy_cache",
            ".pytest_cache",
        ]

        python_files = [
            f for f in python_files if not any(pattern in str(f) for pattern in excluded_patterns)
        ]

        if not python_files:
            return self._create_result(
                score=100,
                description="No Python files to analyze",
                details={"file_count": 0},
                recommendations=[],
            )

        # Analyze files
        total_functions = 0
        typed_functions = 0
        documented_functions = 0

        for file_path in python_files:
            try:
                source = file_path.read_text()
                tree = cst.parse_module(source)
                stats = self._analyze_file(tree)

                total_functions += stats["total"]
                typed_functions += stats["typed"]
                documented_functions += stats["documented"]
            except Exception as e:
                logger.debug(f"Failed to analyze {file_path}: {e}")

        if total_functions == 0:
            return self._create_result(
                score=100,
                description="No functions found to analyze",
                details={"file_count": len(python_files), "function_count": 0},
                recommendations=[],
            )

        typed_ratio = typed_functions / total_functions
        documented_ratio = documented_functions / total_functions

        # Score = (typed_ratio * 70) + (documented_ratio * 30)
        score = (typed_ratio * 70) + (documented_ratio * 30)

        recommendations: list[str] = []
        if typed_ratio < 0.5:
            recommendations.append(
                f"Add type hints to functions ({typed_functions}/{total_functions} typed)"
            )
        if documented_ratio < 0.3:
            recommendations.append(
                f"Add docstrings to functions ({documented_functions}/{total_functions} documented)"
            )

        return self._create_result(
            score=score,
            description=f"{typed_ratio:.0%} typed, {documented_ratio:.0%} documented",
            details={
                "file_count": len(python_files),
                "function_count": total_functions,
                "typed_count": typed_functions,
                "documented_count": documented_functions,
                "typed_ratio": typed_ratio,
                "documented_ratio": documented_ratio,
            },
            recommendations=recommendations,
        )

    def _analyze_file(self, tree: cst.Module) -> dict:
        """Analyze a file for type hints and docstrings.

        Args:
            tree: Parsed CST module

        Returns:
            Dict with total, typed, and documented counts
        """
        visitor = FunctionAnalyzer()
        # Use MetadataWrapper to walk the tree with the visitor
        wrapper = cst.MetadataWrapper(tree)
        wrapper.visit(visitor)

        return {
            "total": visitor.total_functions,
            "typed": visitor.typed_functions,
            "documented": visitor.documented_functions,
        }


class FunctionAnalyzer(cst.CSTVisitor):
    """CST visitor to analyze functions for type hints and docstrings."""

    def __init__(self) -> None:
        self.total_functions = 0
        self.typed_functions = 0
        self.documented_functions = 0

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        self.total_functions += 1

        # Check for type hints
        if self._has_type_hints(node):
            self.typed_functions += 1

        # Check for docstring
        if self._has_docstring(node):
            self.documented_functions += 1

        return True  # Continue visiting nested functions

    def _has_type_hints(self, node: cst.FunctionDef) -> bool:
        """Check if a function has type hints.

        Args:
            node: Function definition node

        Returns:
            True if function has return type or any parameter types
        """
        # Check return type
        if node.returns is not None:
            return True

        # Check parameter types
        for param in node.params.params:
            if param.annotation is not None:
                return True

        return False

    def _has_docstring(self, node: cst.FunctionDef) -> bool:
        """Check if a function has a docstring.

        Args:
            node: Function definition node

        Returns:
            True if function has a docstring
        """
        if not node.body.body:
            return False

        first_stmt = node.body.body[0]

        # Check if first statement is an expression statement with a string
        if isinstance(first_stmt, cst.SimpleStatementLine):
            if first_stmt.body and isinstance(first_stmt.body[0], cst.Expr):
                expr = first_stmt.body[0].value
                if isinstance(expr, (cst.SimpleString, cst.ConcatenatedString)):
                    return True
                if isinstance(expr, cst.FormattedString):
                    return True

        return False
