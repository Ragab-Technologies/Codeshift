"""Test coverage metric calculator."""

import json
import logging
from pathlib import Path
from typing import Any

from codeshift.health.metrics import BaseMetricCalculator
from codeshift.health.models import MetricCategory, MetricResult

logger = logging.getLogger(__name__)


class TestCoverageCalculator(BaseMetricCalculator):
    """Calculates test coverage score (15% weight).

    Score is directly mapped from coverage percentage.
    Returns 50 (neutral) if no coverage data is found.
    """

    @property
    def category(self) -> MetricCategory:
        return MetricCategory.TEST_COVERAGE

    @property
    def weight(self) -> float:
        return 0.15

    def calculate(self, project_path: Path, **kwargs: Any) -> MetricResult:
        """Calculate the test coverage score.

        Args:
            project_path: Path to the project

        Returns:
            MetricResult with test coverage score
        """
        coverage, source = self._get_coverage(project_path)

        if coverage is None:
            return self._create_result(
                score=50,  # Neutral score when no data
                description="No coverage data found",
                details={"coverage_found": False},
                recommendations=[
                    "Run tests with coverage: pytest --cov",
                    "Generate coverage report: coverage run -m pytest && coverage report",
                ],
            )

        # Direct mapping: coverage % = score
        score = coverage * 100

        recommendations: list[str] = []
        if coverage < 0.5:
            recommendations.append("Increase test coverage to at least 50%")
        elif coverage < 0.8:
            recommendations.append("Consider increasing test coverage to 80% or higher")

        return self._create_result(
            score=score,
            description=f"{coverage:.0%} test coverage",
            details={
                "coverage_found": True,
                "coverage_percentage": coverage * 100,
                "source": source,
            },
            recommendations=recommendations,
        )

    def _get_coverage(self, project_path: Path) -> tuple[float | None, str]:
        """Get test coverage from available sources.

        Args:
            project_path: Path to the project

        Returns:
            Tuple of (coverage percentage as 0-1 or None, source description)
        """
        # Try coverage.json first (pytest-cov JSON output)
        coverage_json = project_path / "coverage.json"
        if coverage_json.exists():
            try:
                data = json.loads(coverage_json.read_text())
                totals = data.get("totals", {})
                percent = totals.get("percent_covered", 0)
                return percent / 100, "coverage.json"
            except Exception as e:
                logger.debug(f"Failed to parse coverage.json: {e}")

        # Try .coverage SQLite database
        coverage_db = project_path / ".coverage"
        if coverage_db.exists():
            coverage = self._read_coverage_db(coverage_db)
            if coverage is not None:
                return coverage, ".coverage database"

        # Try htmlcov/index.html for percentage
        htmlcov_index = project_path / "htmlcov" / "index.html"
        if htmlcov_index.exists():
            coverage = self._parse_htmlcov(htmlcov_index)
            if coverage is not None:
                return coverage, "htmlcov"

        # Try pytest-cov XML format
        coverage_xml = project_path / "coverage.xml"
        if coverage_xml.exists():
            coverage = self._parse_coverage_xml(coverage_xml)
            if coverage is not None:
                return coverage, "coverage.xml"

        return None, ""

    def _read_coverage_db(self, db_path: Path) -> float | None:
        """Read coverage from SQLite database.

        Args:
            db_path: Path to .coverage database

        Returns:
            Coverage percentage as 0-1 or None
        """
        try:
            import sqlite3

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get total lines and covered lines
            cursor.execute(
                """
                SELECT SUM(num_lines), SUM(num_hits)
                FROM line_counts
                """
            )
            row = cursor.fetchone()
            conn.close()

            if row and row[0] and row[0] > 0:
                total_lines = row[0]
                covered_lines = row[1] or 0
                return float(covered_lines / total_lines) if total_lines > 0 else None

        except Exception as e:
            logger.debug(f"Failed to read .coverage database: {e}")

        return None

    def _parse_htmlcov(self, index_path: Path) -> float | None:
        """Parse coverage percentage from htmlcov index.

        Args:
            index_path: Path to htmlcov/index.html

        Returns:
            Coverage percentage as 0-1 or None
        """
        try:
            import re

            content = index_path.read_text()
            # Look for patterns like "85%" or "coverage: 85"
            match = re.search(r"(\d+(?:\.\d+)?)\s*%", content)
            if match:
                return float(match.group(1)) / 100
        except Exception as e:
            logger.debug(f"Failed to parse htmlcov: {e}")

        return None

    def _parse_coverage_xml(self, xml_path: Path) -> float | None:
        """Parse coverage from Cobertura XML format.

        Args:
            xml_path: Path to coverage.xml

        Returns:
            Coverage percentage as 0-1 or None
        """
        try:
            import re

            content = xml_path.read_text()
            # Look for line-rate="0.85" attribute
            match = re.search(r'line-rate="(\d+(?:\.\d+)?)"', content)
            if match:
                return float(match.group(1))
        except Exception as e:
            logger.debug(f"Failed to parse coverage.xml: {e}")

        return None
