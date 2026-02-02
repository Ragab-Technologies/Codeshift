"""Data models for the health score feature."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class MetricCategory(Enum):
    """Categories of health metrics."""

    FRESHNESS = "freshness"
    SECURITY = "security"
    MIGRATION_READINESS = "migration_readiness"
    TEST_COVERAGE = "test_coverage"
    DOCUMENTATION = "documentation"


class HealthGrade(Enum):
    """Letter grade for overall health score."""

    A = "A"  # 90-100
    B = "B"  # 80-89
    C = "C"  # 70-79
    D = "D"  # 60-69
    F = "F"  # Below 60

    @classmethod
    def from_score(cls, score: float) -> "HealthGrade":
        """Convert a numeric score to a letter grade.

        Args:
            score: Numeric score from 0-100

        Returns:
            Corresponding letter grade
        """
        if score >= 90:
            return cls.A
        elif score >= 80:
            return cls.B
        elif score >= 70:
            return cls.C
        elif score >= 60:
            return cls.D
        else:
            return cls.F

    @property
    def color(self) -> str:
        """Get the display color for this grade."""
        colors = {
            HealthGrade.A: "green",
            HealthGrade.B: "cyan",
            HealthGrade.C: "yellow",
            HealthGrade.D: "orange1",
            HealthGrade.F: "red",
        }
        return colors.get(self, "white")

    @property
    def emoji(self) -> str:
        """Get the emoji for this grade."""
        emojis = {
            HealthGrade.A: "🟢",
            HealthGrade.B: "🔵",
            HealthGrade.C: "🟡",
            HealthGrade.D: "🟠",
            HealthGrade.F: "🔴",
        }
        return emojis.get(self, "⚪")


class VulnerabilitySeverity(Enum):
    """Severity levels for security vulnerabilities."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def penalty(self) -> int:
        """Get the score penalty for this severity level."""
        penalties = {
            VulnerabilitySeverity.CRITICAL: 25,
            VulnerabilitySeverity.HIGH: 15,
            VulnerabilitySeverity.MEDIUM: 8,
            VulnerabilitySeverity.LOW: 3,
        }
        return penalties.get(self, 0)


@dataclass
class SecurityVulnerability:
    """Represents a security vulnerability in a dependency."""

    package: str
    vulnerability_id: str
    severity: VulnerabilitySeverity
    description: str
    fixed_in: str | None = None
    url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "package": self.package,
            "vulnerability_id": self.vulnerability_id,
            "severity": self.severity.value,
            "description": self.description,
            "fixed_in": self.fixed_in,
            "url": self.url,
        }


@dataclass
class DependencyHealth:
    """Health information for a single dependency."""

    name: str
    current_version: str | None
    latest_version: str | None
    is_outdated: bool
    major_versions_behind: int = 0
    minor_versions_behind: int = 0
    has_tier1_support: bool = False
    has_tier2_support: bool = False
    vulnerabilities: list[SecurityVulnerability] = field(default_factory=list)

    @property
    def version_lag_penalty(self) -> int:
        """Calculate the penalty for version lag."""
        # Major version lag: -15 points each
        # Minor version lag: -5 points each (max 3)
        major_penalty = self.major_versions_behind * 15
        minor_penalty = min(self.minor_versions_behind, 3) * 5
        return major_penalty + minor_penalty

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "is_outdated": self.is_outdated,
            "major_versions_behind": self.major_versions_behind,
            "minor_versions_behind": self.minor_versions_behind,
            "has_tier1_support": self.has_tier1_support,
            "has_tier2_support": self.has_tier2_support,
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
        }


@dataclass
class MetricResult:
    """Result from a single metric calculation."""

    category: MetricCategory
    score: float  # 0-100
    weight: float  # 0.0-1.0
    description: str
    details: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)

    @property
    def weighted_score(self) -> float:
        """Calculate the weighted score contribution."""
        return self.score * self.weight

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "score": self.score,
            "weight": self.weight,
            "weighted_score": self.weighted_score,
            "description": self.description,
            "details": self.details,
            "recommendations": self.recommendations,
        }


@dataclass
class HealthScore:
    """Complete health score for a project."""

    overall_score: float  # 0-100
    grade: HealthGrade
    metrics: list[MetricResult] = field(default_factory=list)
    dependencies: list[DependencyHealth] = field(default_factory=list)
    vulnerabilities: list[SecurityVulnerability] = field(default_factory=list)
    calculated_at: datetime = field(default_factory=datetime.now)
    project_path: Path = field(default_factory=lambda: Path("."))

    @property
    def summary(self) -> str:
        """Get a summary string of the health score."""
        return f"{self.grade.emoji} Grade {self.grade.value} ({self.overall_score:.1f}/100)"

    @property
    def top_recommendations(self) -> list[str]:
        """Get the top 5 recommendations across all metrics."""
        all_recs: list[tuple[float, str]] = []
        for metric in self.metrics:
            # Weight recommendations by how much improvement they could provide
            improvement_potential = 100 - metric.score
            for rec in metric.recommendations:
                all_recs.append((improvement_potential * metric.weight, rec))

        # Sort by improvement potential and return top 5
        all_recs.sort(key=lambda x: x[0], reverse=True)
        seen: set[str] = set()
        unique_recs: list[str] = []
        for _, rec in all_recs:
            if rec not in seen:
                seen.add(rec)
                unique_recs.append(rec)
                if len(unique_recs) >= 5:
                    break
        return unique_recs

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "overall_score": self.overall_score,
            "grade": self.grade.value,
            "metrics": [m.to_dict() for m in self.metrics],
            "dependencies": [d.to_dict() for d in self.dependencies],
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
            "calculated_at": self.calculated_at.isoformat(),
            "project_path": str(self.project_path),
            "recommendations": self.top_recommendations,
        }


@dataclass
class HealthReport:
    """Health report comparing current score to previous."""

    current: HealthScore
    previous: HealthScore | None = None

    @property
    def trend(self) -> str:
        """Get the trend direction."""
        if self.previous is None:
            return "new"

        diff = self.current.overall_score - self.previous.overall_score
        if diff > 2:
            return "improving"
        elif diff < -2:
            return "declining"
        else:
            return "stable"

    @property
    def trend_emoji(self) -> str:
        """Get the trend emoji."""
        emojis = {
            "improving": "📈",
            "declining": "📉",
            "stable": "➡️",
            "new": "🆕",
        }
        return emojis.get(self.trend, "")

    @property
    def score_delta(self) -> float | None:
        """Get the score change from previous."""
        if self.previous is None:
            return None
        return self.current.overall_score - self.previous.overall_score

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "current": self.current.to_dict(),
            "previous": self.previous.to_dict() if self.previous else None,
            "trend": self.trend,
            "score_delta": self.score_delta,
        }
