"""Tests for risk assessor."""

from pathlib import Path
from unittest.mock import MagicMock

from pyresolve.analyzer.risk_assessor import (
    RiskAssessment,
    RiskAssessor,
    RiskFactor,
    RiskLevel,
)
from pyresolve.knowledge_base.models import BreakingChange, ChangeType, Severity
from pyresolve.migrator.ast_transforms import TransformResult


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_risk_level_values(self):
        """Test risk level values."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


class TestRiskFactor:
    """Tests for RiskFactor dataclass."""

    def test_risk_factor_creation(self):
        """Test creating a risk factor."""
        factor = RiskFactor(
            name="Test Factor",
            description="A test factor",
            severity=RiskLevel.LOW,
            score=0.9,
        )
        assert factor.name == "Test Factor"
        assert factor.severity == RiskLevel.LOW
        assert factor.score == 0.9

    def test_risk_factor_with_mitigation(self):
        """Test creating a risk factor with mitigation."""
        factor = RiskFactor(
            name="Test Factor",
            description="A test factor",
            severity=RiskLevel.HIGH,
            score=0.4,
            mitigation="Do something",
        )
        assert factor.mitigation == "Do something"


class TestRiskAssessment:
    """Tests for RiskAssessment dataclass."""

    def test_is_safe_low_risk_high_confidence(self):
        """Test is_safe with low risk and high confidence."""
        assessment = RiskAssessment(
            overall_risk=RiskLevel.LOW,
            confidence_score=0.9,
        )
        assert assessment.is_safe is True

    def test_is_safe_medium_risk_high_confidence(self):
        """Test is_safe with medium risk and high confidence."""
        assessment = RiskAssessment(
            overall_risk=RiskLevel.MEDIUM,
            confidence_score=0.8,
        )
        assert assessment.is_safe is True

    def test_is_safe_high_risk(self):
        """Test is_safe with high risk."""
        assessment = RiskAssessment(
            overall_risk=RiskLevel.HIGH,
            confidence_score=0.9,
        )
        assert assessment.is_safe is False

    def test_is_safe_low_confidence(self):
        """Test is_safe with low confidence."""
        assessment = RiskAssessment(
            overall_risk=RiskLevel.LOW,
            confidence_score=0.5,
        )
        assert assessment.is_safe is False

    def test_summary_low_risk(self):
        """Test summary for low risk."""
        assessment = RiskAssessment(
            overall_risk=RiskLevel.LOW,
            confidence_score=0.9,
        )
        assert "Low" in assessment.summary
        assert "90%" in assessment.summary

    def test_summary_critical_risk(self):
        """Test summary for critical risk."""
        assessment = RiskAssessment(
            overall_risk=RiskLevel.CRITICAL,
            confidence_score=0.3,
        )
        assert "Critical" in assessment.summary


class TestRiskAssessor:
    """Tests for RiskAssessor class."""

    def _make_result(self, file_name: str, change_count: int) -> TransformResult:
        """Helper to create a TransformResult mock."""
        result = MagicMock(spec=TransformResult)
        result.file_path = Path(file_name)
        result.change_count = change_count
        result.changes = []
        return result

    def test_assess_no_results(self):
        """Test assessment with no results."""
        assessor = RiskAssessor()
        assessment = assessor.assess([])
        assert assessment.overall_risk == RiskLevel.LOW

    def test_assess_minimal_changes(self):
        """Test assessment with minimal changes."""
        assessor = RiskAssessor()
        results = [self._make_result("test.py", 5)]
        assessment = assessor.assess(results)
        assert assessment.overall_risk == RiskLevel.LOW

    def test_assess_many_changes(self):
        """Test assessment with many changes."""
        assessor = RiskAssessor()
        results = [
            self._make_result("file1.py", 30),
            self._make_result("file2.py", 30),
            self._make_result("file3.py", 30),
            self._make_result("file4.py", 30),
        ]
        assessment = assessor.assess(results)
        # 120 changes should be high complexity
        assert assessment.overall_risk in (RiskLevel.MEDIUM, RiskLevel.HIGH)

    def test_assess_with_critical_files(self):
        """Test assessment with critical file patterns."""
        assessor = RiskAssessor()
        results = [
            self._make_result("auth.py", 10),
            self._make_result("security.py", 10),
            self._make_result("payment.py", 10),
        ]
        assessment = assessor.assess(results)
        assert any("critical" in f.name.lower() for f in assessment.factors)

    def test_assess_with_test_coverage(self):
        """Test assessment with test coverage."""
        assessor = RiskAssessor()
        results = [self._make_result("test.py", 5)]

        # High coverage should improve confidence
        assessment_high = assessor.assess(results, test_coverage=0.9)
        assessment_low = assessor.assess(results, test_coverage=0.2)

        assert assessment_high.confidence_score > assessment_low.confidence_score

    def test_assess_with_breaking_changes(self):
        """Test assessment with breaking changes."""
        assessor = RiskAssessor()
        results = [self._make_result("test.py", 5)]

        breaking_changes = [
            BreakingChange(
                symbol="test_symbol",
                change_type=ChangeType.REMOVED,
                severity=Severity.HIGH,
                from_version="1.0",
                to_version="2.0",
                description="A test breaking change",
            ),
            BreakingChange(
                symbol="test_symbol_2",
                change_type=ChangeType.REMOVED,
                severity=Severity.HIGH,
                from_version="1.0",
                to_version="2.0",
                description="Another breaking change",
            ),
            BreakingChange(
                symbol="test_symbol_3",
                change_type=ChangeType.REMOVED,
                severity=Severity.HIGH,
                from_version="1.0",
                to_version="2.0",
                description="A third breaking change",
            ),
        ]

        assessment = assessor.assess(results, breaking_changes=breaking_changes)
        assert any("Breaking" in f.name for f in assessment.factors)

    def test_assess_recommendations(self):
        """Test that assessment includes recommendations."""
        assessor = RiskAssessor()
        results = [
            self._make_result("file1.py", 50),
            self._make_result("file2.py", 50),
        ]
        assessment = assessor.assess(results)
        assert len(assessment.recommendations) > 0


class TestAssessTestCoverage:
    """Tests for test coverage assessment."""

    def test_high_coverage(self):
        """Test high coverage assessment."""
        assessor = RiskAssessor()
        factor = assessor._assess_test_coverage(0.85)
        assert factor.severity == RiskLevel.LOW
        assert factor.score >= 0.8

    def test_moderate_coverage(self):
        """Test moderate coverage assessment."""
        assessor = RiskAssessor()
        factor = assessor._assess_test_coverage(0.65)
        assert factor.severity == RiskLevel.LOW

    def test_low_coverage(self):
        """Test low coverage assessment."""
        assessor = RiskAssessor()
        factor = assessor._assess_test_coverage(0.45)
        assert factor.severity == RiskLevel.MEDIUM

    def test_poor_coverage(self):
        """Test poor coverage assessment."""
        assessor = RiskAssessor()
        factor = assessor._assess_test_coverage(0.2)
        assert factor.severity == RiskLevel.HIGH


class TestAssessFileCriticality:
    """Tests for file criticality assessment."""

    def test_no_critical_files(self):
        """Test assessment with no critical files."""
        assessor = RiskAssessor()

        result = MagicMock(spec=TransformResult)
        result.file_path = Path("utils.py")
        result.change_count = 5

        factor = assessor._assess_file_criticality([result])
        assert factor.severity == RiskLevel.LOW

    def test_critical_files(self):
        """Test assessment with critical files."""
        assessor = RiskAssessor()

        results = []
        for name in ["auth.py", "database.py", "payment.py"]:
            result = MagicMock(spec=TransformResult)
            result.file_path = Path(name)
            result.change_count = 5
            results.append(result)

        factor = assessor._assess_file_criticality(results)
        assert factor.severity in (RiskLevel.MEDIUM, RiskLevel.HIGH)


class TestAssessBreakingChangeSeverity:
    """Tests for breaking change severity assessment."""

    def test_no_breaking_changes(self):
        """Test assessment with no breaking changes."""
        assessor = RiskAssessor()
        factor = assessor._assess_breaking_change_severity([])
        assert factor.severity == RiskLevel.LOW

    def test_critical_breaking_changes(self):
        """Test assessment with critical breaking changes."""
        assessor = RiskAssessor()
        breaking_changes = [
            BreakingChange(
                symbol="critical_symbol",
                change_type=ChangeType.REMOVED,
                severity=Severity.CRITICAL,
                from_version="1.0",
                to_version="2.0",
                description="Critical breaking change",
            )
        ]
        factor = assessor._assess_breaking_change_severity(breaking_changes)
        assert factor.severity == RiskLevel.CRITICAL

    def test_low_breaking_changes(self):
        """Test assessment with low severity breaking changes."""
        assessor = RiskAssessor()
        breaking_changes = [
            BreakingChange(
                symbol="low_symbol",
                change_type=ChangeType.BEHAVIOR_CHANGED,
                severity=Severity.LOW,
                from_version="1.0",
                to_version="2.0",
                description="Low breaking change",
            )
        ]
        factor = assessor._assess_breaking_change_severity(breaking_changes)
        assert factor.severity == RiskLevel.LOW
