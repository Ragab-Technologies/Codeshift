"""Base class and utilities for health metric calculators."""

from abc import ABC, abstractmethod
from pathlib import Path

from codeshift.health.models import MetricCategory, MetricResult


class BaseMetricCalculator(ABC):
    """Abstract base class for health metric calculators."""

    @property
    @abstractmethod
    def category(self) -> MetricCategory:
        """Return the metric category."""
        ...

    @property
    @abstractmethod
    def weight(self) -> float:
        """Return the weight for this metric (0.0 to 1.0)."""
        ...

    @abstractmethod
    def calculate(self, project_path: Path, **kwargs) -> MetricResult:
        """Calculate the metric score.

        Args:
            project_path: Path to the project root
            **kwargs: Additional arguments specific to the metric

        Returns:
            MetricResult with score and details
        """
        ...

    def _create_result(
        self,
        score: float,
        description: str,
        details: dict | None = None,
        recommendations: list[str] | None = None,
    ) -> MetricResult:
        """Helper to create a MetricResult.

        Args:
            score: Score from 0-100
            description: Human-readable description
            details: Optional details dictionary
            recommendations: Optional list of recommendations

        Returns:
            MetricResult instance
        """
        return MetricResult(
            category=self.category,
            score=max(0, min(100, score)),  # Clamp to 0-100
            weight=self.weight,
            description=description,
            details=details or {},
            recommendations=recommendations or [],
        )
