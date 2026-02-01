"""Tests for the codebase health scoring feature."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from codeshift.cli.commands.health import health
from codeshift.health import (
    HealthCalculator,
    HealthGrade,
    HealthScore,
    MetricCategory,
    MetricResult,
)
from codeshift.health.metrics.documentation import DocumentationCalculator
from codeshift.health.metrics.freshness import FreshnessCalculator
from codeshift.health.metrics.migration_readiness import MigrationReadinessCalculator
from codeshift.health.metrics.security import SecurityCalculator
from codeshift.health.metrics.test_coverage import TestCoverageCalculator
from codeshift.health.models import (
    DependencyHealth,
    HealthReport,
    SecurityVulnerability,
    VulnerabilitySeverity,
)
from codeshift.health.report import generate_html_report, generate_json_report

# ==============================================================================
# Model Tests
# ==============================================================================


class TestHealthGrade:
    """Tests for HealthGrade enum."""

    @pytest.mark.parametrize(
        "score,expected_grade",
        [
            (100, HealthGrade.A),
            (95, HealthGrade.A),
            (90, HealthGrade.A),
            (89, HealthGrade.B),
            (80, HealthGrade.B),
            (79, HealthGrade.C),
            (70, HealthGrade.C),
            (69, HealthGrade.D),
            (60, HealthGrade.D),
            (59, HealthGrade.F),
            (0, HealthGrade.F),
        ],
    )
    def test_from_score(self, score: float, expected_grade: HealthGrade) -> None:
        """Test grade assignment from score."""
        assert HealthGrade.from_score(score) == expected_grade

    def test_grade_colors(self) -> None:
        """Test that all grades have colors."""
        for grade in HealthGrade:
            assert grade.color is not None
            assert isinstance(grade.color, str)

    def test_grade_emojis(self) -> None:
        """Test that all grades have emojis."""
        for grade in HealthGrade:
            assert grade.emoji is not None


class TestDependencyHealth:
    """Tests for DependencyHealth dataclass."""

    def test_version_lag_penalty(self) -> None:
        """Test version lag penalty calculation."""
        dep = DependencyHealth(
            name="test",
            current_version="1.0.0",
            latest_version="3.2.0",
            is_outdated=True,
            major_versions_behind=2,
            minor_versions_behind=0,
        )
        # 2 major versions * 15 = 30
        assert dep.version_lag_penalty == 30

    def test_version_lag_penalty_minor(self) -> None:
        """Test version lag penalty with minor versions."""
        dep = DependencyHealth(
            name="test",
            current_version="1.0.0",
            latest_version="1.5.0",
            is_outdated=True,
            major_versions_behind=0,
            minor_versions_behind=5,
        )
        # Capped at 3 minor versions * 5 = 15
        assert dep.version_lag_penalty == 15

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        dep = DependencyHealth(
            name="pydantic",
            current_version="1.10.0",
            latest_version="2.5.0",
            is_outdated=True,
            major_versions_behind=1,
        )
        data = dep.to_dict()
        assert data["name"] == "pydantic"
        assert data["is_outdated"] is True


class TestSecurityVulnerability:
    """Tests for SecurityVulnerability dataclass."""

    def test_severity_penalty(self) -> None:
        """Test severity penalty values."""
        assert VulnerabilitySeverity.CRITICAL.penalty == 25
        assert VulnerabilitySeverity.HIGH.penalty == 15
        assert VulnerabilitySeverity.MEDIUM.penalty == 8
        assert VulnerabilitySeverity.LOW.penalty == 3


class TestMetricResult:
    """Tests for MetricResult dataclass."""

    def test_weighted_score(self) -> None:
        """Test weighted score calculation."""
        result = MetricResult(
            category=MetricCategory.FRESHNESS,
            score=80,
            weight=0.30,
            description="Test",
        )
        assert result.weighted_score == 24.0


class TestHealthScore:
    """Tests for HealthScore dataclass."""

    def test_summary(self) -> None:
        """Test summary property."""
        score = HealthScore(
            overall_score=92.5,
            grade=HealthGrade.A,
        )
        assert "A" in score.summary
        assert "92.5" in score.summary

    def test_top_recommendations(self) -> None:
        """Test top recommendations extraction."""
        metrics = [
            MetricResult(
                category=MetricCategory.FRESHNESS,
                score=50,
                weight=0.30,
                description="Test",
                recommendations=["Update deps", "Check versions"],
            ),
            MetricResult(
                category=MetricCategory.SECURITY,
                score=80,
                weight=0.25,
                description="Test",
                recommendations=["Fix vuln"],
            ),
        ]
        score = HealthScore(
            overall_score=65,
            grade=HealthGrade.D,
            metrics=metrics,
        )
        recs = score.top_recommendations
        # Should prioritize recommendations from lower-scoring metrics
        assert len(recs) <= 5
        assert "Update deps" in recs


class TestHealthReport:
    """Tests for HealthReport dataclass."""

    def test_trend_improving(self) -> None:
        """Test improving trend detection."""
        current = HealthScore(overall_score=80, grade=HealthGrade.B)
        previous = HealthScore(overall_score=70, grade=HealthGrade.C)
        report = HealthReport(current=current, previous=previous)
        assert report.trend == "improving"
        assert report.score_delta == 10

    def test_trend_declining(self) -> None:
        """Test declining trend detection."""
        current = HealthScore(overall_score=60, grade=HealthGrade.D)
        previous = HealthScore(overall_score=75, grade=HealthGrade.C)
        report = HealthReport(current=current, previous=previous)
        assert report.trend == "declining"
        assert report.score_delta == -15

    def test_trend_stable(self) -> None:
        """Test stable trend detection."""
        current = HealthScore(overall_score=75, grade=HealthGrade.C)
        previous = HealthScore(overall_score=74, grade=HealthGrade.C)
        report = HealthReport(current=current, previous=previous)
        assert report.trend == "stable"

    def test_trend_new(self) -> None:
        """Test new baseline detection."""
        current = HealthScore(overall_score=75, grade=HealthGrade.C)
        report = HealthReport(current=current, previous=None)
        assert report.trend == "new"
        assert report.score_delta is None


# ==============================================================================
# Metric Calculator Tests
# ==============================================================================


class TestFreshnessCalculator:
    """Tests for FreshnessCalculator."""

    def test_properties(self) -> None:
        """Test calculator properties."""
        calc = FreshnessCalculator()
        assert calc.category == MetricCategory.FRESHNESS
        assert calc.weight == 0.30

    def test_calculate_no_dependencies(self, tmp_path: Path) -> None:
        """Test with no dependencies."""
        calc = FreshnessCalculator()
        result = calc.calculate(tmp_path, dependencies=[])
        assert result.score == 100

    def test_calculate_with_outdated_deps(self, tmp_path: Path) -> None:
        """Test with outdated dependencies."""
        deps = [
            DependencyHealth(
                name="pkg1",
                current_version="1.0.0",
                latest_version="2.0.0",
                is_outdated=True,
                major_versions_behind=1,
            ),
            DependencyHealth(
                name="pkg2",
                current_version="1.0.0",
                latest_version="1.0.0",
                is_outdated=False,
            ),
        ]
        calc = FreshnessCalculator()
        result = calc.calculate(tmp_path, dependencies=deps)
        # Score should be 100 - 15 (one major behind) = 85
        assert result.score == 85
        assert "1/2" in result.description


class TestSecurityCalculator:
    """Tests for SecurityCalculator."""

    def test_properties(self) -> None:
        """Test calculator properties."""
        calc = SecurityCalculator()
        assert calc.category == MetricCategory.SECURITY
        assert calc.weight == 0.25

    def test_calculate_no_vulns(self, tmp_path: Path) -> None:
        """Test with no vulnerabilities."""
        deps = [
            DependencyHealth(
                name="pkg1",
                current_version="1.0.0",
                latest_version="1.0.0",
                is_outdated=False,
            ),
        ]
        calc = SecurityCalculator()
        result = calc.calculate(tmp_path, dependencies=deps)
        assert result.score == 100
        assert "No known vulnerabilities" in result.description

    def test_calculate_with_vulns(self, tmp_path: Path) -> None:
        """Test with vulnerabilities."""
        deps = [
            DependencyHealth(
                name="pkg1",
                current_version="1.0.0",
                latest_version="1.0.0",
                is_outdated=False,
                vulnerabilities=[
                    SecurityVulnerability(
                        package="pkg1",
                        vulnerability_id="CVE-2024-1234",
                        severity=VulnerabilitySeverity.HIGH,
                        description="Test vuln",
                    ),
                ],
            ),
        ]
        calc = SecurityCalculator()
        result = calc.calculate(tmp_path, dependencies=deps)
        # Score = 100 - 15 (high severity) = 85
        assert result.score == 85
        assert "1 vulnerabilities found" in result.description


class TestMigrationReadinessCalculator:
    """Tests for MigrationReadinessCalculator."""

    def test_properties(self) -> None:
        """Test calculator properties."""
        calc = MigrationReadinessCalculator()
        assert calc.category == MetricCategory.MIGRATION_READINESS
        assert calc.weight == 0.20

    def test_calculate_all_tier1(self, tmp_path: Path) -> None:
        """Test with all Tier 1 supported deps."""
        deps = [
            DependencyHealth(
                name="pydantic",
                current_version="1.0.0",
                latest_version="2.0.0",
                is_outdated=True,
                has_tier1_support=True,
            ),
        ]
        calc = MigrationReadinessCalculator()
        result = calc.calculate(tmp_path, dependencies=deps)
        assert result.score == 100

    def test_calculate_mixed_support(self, tmp_path: Path) -> None:
        """Test with mixed support levels."""
        deps = [
            DependencyHealth(
                name="pydantic",
                current_version="1.0.0",
                latest_version="2.0.0",
                is_outdated=True,
                has_tier1_support=True,
            ),
            DependencyHealth(
                name="httpx",
                current_version="0.24.0",
                latest_version="0.25.0",
                is_outdated=True,
                has_tier1_support=False,
                has_tier2_support=True,
            ),
        ]
        calc = MigrationReadinessCalculator()
        result = calc.calculate(tmp_path, dependencies=deps)
        # (1 * 100 + 1 * 50) / 2 = 75
        assert result.score == 75


class TestTestCoverageCalculator:
    """Tests for TestCoverageCalculator."""

    def test_properties(self) -> None:
        """Test calculator properties."""
        calc = TestCoverageCalculator()
        assert calc.category == MetricCategory.TEST_COVERAGE
        assert calc.weight == 0.15

    def test_calculate_no_coverage(self, tmp_path: Path) -> None:
        """Test with no coverage data."""
        calc = TestCoverageCalculator()
        result = calc.calculate(tmp_path)
        assert result.score == 50  # Neutral score
        assert "No coverage data found" in result.description

    def test_calculate_with_coverage_json(self, tmp_path: Path) -> None:
        """Test with coverage.json file."""
        coverage_file = tmp_path / "coverage.json"
        coverage_file.write_text(json.dumps({"totals": {"percent_covered": 85.5}}))

        calc = TestCoverageCalculator()
        result = calc.calculate(tmp_path)
        assert result.score == 85.5
        assert "test coverage" in result.description


class TestDocumentationCalculator:
    """Tests for DocumentationCalculator."""

    def test_properties(self) -> None:
        """Test calculator properties."""
        calc = DocumentationCalculator()
        assert calc.category == MetricCategory.DOCUMENTATION
        assert calc.weight == 0.10

    def test_calculate_no_files(self, tmp_path: Path) -> None:
        """Test with no Python files."""
        calc = DocumentationCalculator()
        result = calc.calculate(tmp_path)
        assert result.score == 100

    def test_calculate_with_typed_function(self, tmp_path: Path) -> None:
        """Test with typed function."""
        py_file = tmp_path / "example.py"
        py_file.write_text(
            '''
def typed_func(x: int) -> str:
    """Docstring."""
    return str(x)
'''
        )

        calc = DocumentationCalculator()
        result = calc.calculate(tmp_path)
        # 100% typed (70 pts) + 100% documented (30 pts) = 100
        assert result.score == 100

    def test_calculate_with_untyped_function(self, tmp_path: Path) -> None:
        """Test with untyped function."""
        py_file = tmp_path / "example.py"
        py_file.write_text(
            """def untyped_func(x):
    return str(x)
"""
        )

        calc = DocumentationCalculator()
        result = calc.calculate(tmp_path)
        # 0% typed + 0% documented = 0
        assert result.score == 0


# ==============================================================================
# Calculator Integration Tests
# ==============================================================================


class TestHealthCalculator:
    """Tests for HealthCalculator orchestrator."""

    @patch("httpx.get")
    def test_calculate_basic(self, mock_get: MagicMock, tmp_path: Path) -> None:
        """Test basic calculation."""
        # Mock PyPI response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        # Create a minimal pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test"
dependencies = []
"""
        )

        calculator = HealthCalculator()
        score = calculator.calculate(tmp_path)

        assert isinstance(score, HealthScore)
        assert 0 <= score.overall_score <= 100
        assert score.grade in list(HealthGrade)
        assert len(score.metrics) == 5


# ==============================================================================
# Report Tests
# ==============================================================================


class TestReportGeneration:
    """Tests for report generation."""

    def test_generate_json_report(self) -> None:
        """Test JSON report generation."""
        score = HealthScore(
            overall_score=85.5,
            grade=HealthGrade.B,
            metrics=[
                MetricResult(
                    category=MetricCategory.FRESHNESS,
                    score=90,
                    weight=0.30,
                    description="Test",
                )
            ],
        )

        json_str = generate_json_report(score)
        data = json.loads(json_str)

        assert data["overall_score"] == 85.5
        assert data["grade"] == "B"
        assert len(data["metrics"]) == 1

    def test_generate_html_report(self) -> None:
        """Test HTML report generation."""
        score = HealthScore(
            overall_score=85.5,
            grade=HealthGrade.B,
            metrics=[
                MetricResult(
                    category=MetricCategory.FRESHNESS,
                    score=90,
                    weight=0.30,
                    description="Test",
                )
            ],
        )

        html_str = generate_html_report(score)

        assert "<!DOCTYPE html>" in html_str
        assert "85.5" in html_str
        assert 'class="grade b"' in html_str
        assert ">B<" in html_str  # Grade letter in HTML


# ==============================================================================
# CLI Tests
# ==============================================================================


class TestHealthCLI:
    """Tests for health CLI command."""

    def test_help(self) -> None:
        """Test help output."""
        runner = CliRunner()
        result = runner.invoke(health, ["--help"])
        assert result.exit_code == 0
        assert "Analyze codebase health" in result.output

    @patch("httpx.get")
    def test_basic_run(self, mock_get: MagicMock, tmp_path: Path) -> None:
        """Test basic command execution."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\ndependencies = []\n')

        runner = CliRunner()
        result = runner.invoke(health, ["--path", str(tmp_path)])

        assert result.exit_code == 0
        assert "Grade" in result.output

    @patch("httpx.get")
    def test_json_report(self, mock_get: MagicMock, tmp_path: Path) -> None:
        """Test JSON report generation."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\ndependencies = []\n')

        output_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            health, ["--path", str(tmp_path), "--report", "json", "--output", str(output_file)]
        )

        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "overall_score" in data

    @patch("httpx.get")
    def test_ci_mode_pass(self, mock_get: MagicMock, tmp_path: Path) -> None:
        """Test CI mode when score passes threshold."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\ndependencies = []\n')

        runner = CliRunner()
        result = runner.invoke(health, ["--path", str(tmp_path), "--ci", "--threshold", "0"])

        assert result.exit_code == 0
        assert "CI Check Passed" in result.output

    @patch("httpx.get")
    def test_ci_mode_fail(self, mock_get: MagicMock, tmp_path: Path) -> None:
        """Test CI mode when score fails threshold."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\ndependencies = []\n')

        runner = CliRunner()
        result = runner.invoke(health, ["--path", str(tmp_path), "--ci", "--threshold", "100"])

        assert result.exit_code == 1
        assert "CI Check Failed" in result.output
