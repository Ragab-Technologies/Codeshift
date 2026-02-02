"""Codebase health scoring module.

This module provides health scoring capabilities for Python projects,
analyzing dependency freshness, security, migration readiness, test
coverage, and documentation quality.

Example:
    >>> from codeshift.health import HealthCalculator
    >>> calculator = HealthCalculator()
    >>> score = calculator.calculate(Path("."))
    >>> print(score.summary)
    🟢 Grade A (92.5/100)
"""

from codeshift.health.calculator import HealthCalculator
from codeshift.health.models import (
    DependencyHealth,
    HealthGrade,
    HealthReport,
    HealthScore,
    MetricCategory,
    MetricResult,
    SecurityVulnerability,
    VulnerabilitySeverity,
)
from codeshift.health.report import (
    generate_html_report,
    generate_json_report,
    save_html_report,
    save_json_report,
)

__all__ = [
    # Main calculator
    "HealthCalculator",
    # Models
    "DependencyHealth",
    "HealthGrade",
    "HealthReport",
    "HealthScore",
    "MetricCategory",
    "MetricResult",
    "SecurityVulnerability",
    "VulnerabilitySeverity",
    # Report functions
    "generate_html_report",
    "generate_json_report",
    "save_html_report",
    "save_json_report",
]
