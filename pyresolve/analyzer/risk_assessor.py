"""Risk assessment for migration changes."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pyresolve.knowledge_base.models import BreakingChange, Severity
from pyresolve.migrator.ast_transforms import TransformResult


class RiskLevel(Enum):
    """Risk level for a migration."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        return order.index(self) < order.index(other)

    def __le__(self, other: object) -> bool:
        return self == other or self < other

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return not self <= other

    def __ge__(self, other: object) -> bool:
        return self == other or self > other


@dataclass
class RiskFactor:
    """A factor contributing to migration risk."""

    name: str
    description: str
    severity: RiskLevel
    score: float  # 0.0 to 1.0
    mitigation: Optional[str] = None


@dataclass
class RiskAssessment:
    """Overall risk assessment for a migration."""

    overall_risk: RiskLevel
    confidence_score: float  # 0.0 to 1.0 (how confident we are in the migration)
    factors: list[RiskFactor] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        """Check if the migration is considered safe."""
        return (
            self.overall_risk in (RiskLevel.LOW, RiskLevel.MEDIUM) and self.confidence_score >= 0.7
        )

    @property
    def summary(self) -> str:
        """Get a summary of the risk assessment."""
        risk_emoji = {
            RiskLevel.LOW: "✅",
            RiskLevel.MEDIUM: "⚠️",
            RiskLevel.HIGH: "🔶",
            RiskLevel.CRITICAL: "🔴",
        }
        return f"{risk_emoji.get(self.overall_risk, '❓')} {self.overall_risk.value.title()} risk (confidence: {self.confidence_score:.0%})"


class RiskAssessor:
    """Assesses risk of migration changes."""

    def __init__(self) -> None:
        """Initialize the risk assessor."""
        # Weights for different risk factors
        self.weights = {
            "deterministic_transform": 0.3,
            "test_coverage": 0.25,
            "change_complexity": 0.2,
            "file_criticality": 0.15,
            "breaking_change_severity": 0.1,
        }

    def assess(
        self,
        results: list[TransformResult],
        breaking_changes: Optional[list[BreakingChange]] = None,
        test_coverage: Optional[float] = None,
    ) -> RiskAssessment:
        """Assess the risk of a migration.

        Args:
            results: List of transform results
            breaking_changes: List of breaking changes being addressed
            test_coverage: Optional test coverage percentage (0.0 to 1.0)

        Returns:
            RiskAssessment with overall risk evaluation
        """
        factors = []
        recommendations = []

        # Factor 1: Transform determinism
        deterministic_factor = self._assess_determinism(results)
        factors.append(deterministic_factor)

        # Factor 2: Change complexity
        complexity_factor = self._assess_complexity(results)
        factors.append(complexity_factor)

        # Factor 3: File criticality (heuristic based on file names/paths)
        criticality_factor = self._assess_file_criticality(results)
        factors.append(criticality_factor)

        # Factor 4: Breaking change severity
        if breaking_changes:
            severity_factor = self._assess_breaking_change_severity(breaking_changes)
            factors.append(severity_factor)

        # Factor 5: Test coverage
        if test_coverage is not None:
            coverage_factor = self._assess_test_coverage(test_coverage)
            factors.append(coverage_factor)
        else:
            recommendations.append("Run tests with coverage to improve confidence score")

        # Calculate overall risk and confidence
        overall_risk, confidence = self._calculate_overall_risk(factors)

        # Add recommendations based on risk factors
        for factor in factors:
            if factor.severity in (RiskLevel.HIGH, RiskLevel.CRITICAL) and factor.mitigation:
                recommendations.append(factor.mitigation)

        # Standard recommendations
        if overall_risk != RiskLevel.LOW:
            recommendations.append("Review the diff carefully before applying changes")
            recommendations.append("Run your full test suite after applying changes")
            recommendations.append("Consider applying changes incrementally to isolate issues")

        return RiskAssessment(
            overall_risk=overall_risk,
            confidence_score=confidence,
            factors=factors,
            recommendations=recommendations,
        )

    def _assess_determinism(self, results: list[TransformResult]) -> RiskFactor:
        """Assess risk based on transform determinism."""
        total_changes = sum(r.change_count for r in results)
        if total_changes == 0:
            return RiskFactor(
                name="Transform Determinism",
                description="No changes to assess",
                severity=RiskLevel.LOW,
                score=1.0,
            )

        # All our transforms are deterministic, so this is low risk
        # In the future, LLM-based transforms would increase risk
        return RiskFactor(
            name="Transform Determinism",
            description="All changes use deterministic AST transforms",
            severity=RiskLevel.LOW,
            score=0.9,
        )

    def _assess_complexity(self, results: list[TransformResult]) -> RiskFactor:
        """Assess risk based on change complexity."""
        total_changes = sum(r.change_count for r in results)
        total_files = len(results)

        if total_changes == 0:
            return RiskFactor(
                name="Change Complexity",
                description="No changes",
                severity=RiskLevel.LOW,
                score=1.0,
            )

        # More changes = higher risk
        if total_changes > 100:
            severity = RiskLevel.HIGH
            score = 0.4
            description = f"Large migration: {total_changes} changes across {total_files} files"
            mitigation = "Consider migrating in smaller batches"
        elif total_changes > 50:
            severity = RiskLevel.MEDIUM
            score = 0.6
            description = f"Medium migration: {total_changes} changes across {total_files} files"
            mitigation = "Review changes carefully"
        elif total_changes > 20:
            severity = RiskLevel.LOW
            score = 0.8
            description = f"Small migration: {total_changes} changes across {total_files} files"
            mitigation = None
        else:
            severity = RiskLevel.LOW
            score = 0.9
            description = f"Minimal migration: {total_changes} changes across {total_files} files"
            mitigation = None

        return RiskFactor(
            name="Change Complexity",
            description=description,
            severity=severity,
            score=score,
            mitigation=mitigation,
        )

    def _assess_file_criticality(self, results: list[TransformResult]) -> RiskFactor:
        """Assess risk based on which files are being modified."""
        critical_patterns = [
            "auth",
            "security",
            "payment",
            "billing",
            "config",
            "settings",
            "main",
            "app",
            "core",
            "database",
            "db",
            "migration",
        ]

        critical_files = []
        for result in results:
            file_name = result.file_path.name.lower()
            file_path_str = str(result.file_path).lower()

            for pattern in critical_patterns:
                if pattern in file_name or pattern in file_path_str:
                    critical_files.append(result.file_path)
                    break

        if not critical_files:
            return RiskFactor(
                name="File Criticality",
                description="No critical files identified",
                severity=RiskLevel.LOW,
                score=0.9,
            )

        ratio = len(critical_files) / len(results) if results else 0

        if ratio > 0.5:
            severity = RiskLevel.HIGH
            score = 0.4
        elif ratio > 0.2:
            severity = RiskLevel.MEDIUM
            score = 0.6
        else:
            severity = RiskLevel.LOW
            score = 0.8

        return RiskFactor(
            name="File Criticality",
            description=f"{len(critical_files)} critical file(s) affected: {', '.join(f.name for f in critical_files[:3])}",
            severity=severity,
            score=score,
            mitigation=(
                "Pay extra attention to critical files during review"
                if severity != RiskLevel.LOW
                else None
            ),
        )

    def _assess_breaking_change_severity(
        self, breaking_changes: list[BreakingChange]
    ) -> RiskFactor:
        """Assess risk based on breaking change severity."""
        if not breaking_changes:
            return RiskFactor(
                name="Breaking Change Severity",
                description="No breaking changes to assess",
                severity=RiskLevel.LOW,
                score=1.0,
            )

        severity_counts = {
            Severity.LOW: 0,
            Severity.MEDIUM: 0,
            Severity.HIGH: 0,
            Severity.CRITICAL: 0,
        }

        for change in breaking_changes:
            severity_counts[change.severity] += 1

        if severity_counts[Severity.CRITICAL] > 0:
            severity = RiskLevel.CRITICAL
            score = 0.2
        elif severity_counts[Severity.HIGH] > 2:
            severity = RiskLevel.HIGH
            score = 0.4
        elif severity_counts[Severity.HIGH] > 0 or severity_counts[Severity.MEDIUM] > 3:
            severity = RiskLevel.MEDIUM
            score = 0.6
        else:
            severity = RiskLevel.LOW
            score = 0.8

        return RiskFactor(
            name="Breaking Change Severity",
            description=f"Addressing {len(breaking_changes)} breaking changes",
            severity=severity,
            score=score,
            mitigation=(
                "Ensure thorough testing of affected functionality"
                if severity != RiskLevel.LOW
                else None
            ),
        )

    def _assess_test_coverage(self, coverage: float) -> RiskFactor:
        """Assess risk based on test coverage."""
        if coverage >= 0.8:
            severity = RiskLevel.LOW
            score = 0.9
            description = f"Good test coverage: {coverage:.0%}"
        elif coverage >= 0.6:
            severity = RiskLevel.LOW
            score = 0.7
            description = f"Moderate test coverage: {coverage:.0%}"
        elif coverage >= 0.4:
            severity = RiskLevel.MEDIUM
            score = 0.5
            description = f"Low test coverage: {coverage:.0%}"
            mitigation = "Consider adding more tests before migration"
        else:
            severity = RiskLevel.HIGH
            score = 0.3
            description = f"Poor test coverage: {coverage:.0%}"
            mitigation = "Strongly recommend adding tests before migration"

        return RiskFactor(
            name="Test Coverage",
            description=description,
            severity=severity,
            score=score,
            mitigation=mitigation if severity != RiskLevel.LOW else None,
        )

    def _calculate_overall_risk(self, factors: list[RiskFactor]) -> tuple[RiskLevel, float]:
        """Calculate overall risk level and confidence score."""
        if not factors:
            return RiskLevel.LOW, 1.0

        # Calculate weighted average score
        total_weight = 0.0
        weighted_score = 0.0

        for factor in factors:
            # Use factor name to look up weight, default to equal weighting
            weight = self.weights.get(factor.name.lower().replace(" ", "_"), 1.0 / len(factors))
            weighted_score += factor.score * weight
            total_weight += weight

        confidence = weighted_score / total_weight if total_weight > 0 else 0.5

        # Determine overall risk based on worst factor and average
        worst_severity = max(f.severity for f in factors)
        severity_values = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4,
        }

        avg_severity = sum(severity_values[f.severity] for f in factors) / len(factors)

        if worst_severity == RiskLevel.CRITICAL or avg_severity > 3:
            overall = RiskLevel.CRITICAL
        elif worst_severity == RiskLevel.HIGH or avg_severity > 2.5:
            overall = RiskLevel.HIGH
        elif avg_severity > 1.5:
            overall = RiskLevel.MEDIUM
        else:
            overall = RiskLevel.LOW

        return overall, confidence
