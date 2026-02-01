"""Main health score calculator orchestrator."""

import logging
from pathlib import Path

from codeshift.health.metrics import BaseMetricCalculator
from codeshift.health.metrics.documentation import DocumentationCalculator
from codeshift.health.metrics.freshness import FreshnessCalculator
from codeshift.health.metrics.migration_readiness import MigrationReadinessCalculator
from codeshift.health.metrics.security import SecurityCalculator
from codeshift.health.metrics.test_coverage import TestCoverageCalculator
from codeshift.health.models import (
    DependencyHealth,
    HealthGrade,
    HealthReport,
    HealthScore,
    MetricResult,
    SecurityVulnerability,
)

logger = logging.getLogger(__name__)


class HealthCalculator:
    """Orchestrates health score calculation across all metrics."""

    def __init__(self) -> None:
        """Initialize the calculator with all metric calculators."""
        self.calculators: list[BaseMetricCalculator] = [
            FreshnessCalculator(),
            SecurityCalculator(),
            MigrationReadinessCalculator(),
            TestCoverageCalculator(),
            DocumentationCalculator(),
        ]

    def calculate(self, project_path: Path) -> HealthScore:
        """Calculate the complete health score for a project.

        Args:
            project_path: Path to the project root

        Returns:
            HealthScore with all metrics and overall score
        """
        project_path = project_path.resolve()

        # First, analyze dependencies once to share across calculators
        dependencies = self._analyze_dependencies(project_path)

        # Calculate each metric
        metrics: list[MetricResult] = []
        for calculator in self.calculators:
            try:
                result = calculator.calculate(
                    project_path,
                    dependencies=dependencies,
                )
                metrics.append(result)
            except Exception as e:
                logger.warning(f"Failed to calculate {calculator.category.value}: {e}")
                # Add a neutral result on failure
                metrics.append(
                    MetricResult(
                        category=calculator.category,
                        score=50,
                        weight=calculator.weight,
                        description=f"Error: {str(e)[:50]}",
                        details={"error": str(e)},
                        recommendations=["Fix metric calculation error"],
                    )
                )

        # Calculate overall weighted score
        total_weight = sum(m.weight for m in metrics)
        if total_weight > 0:
            overall_score = sum(m.weighted_score for m in metrics) / total_weight
        else:
            overall_score = 0

        # Collect all vulnerabilities
        all_vulns: list[SecurityVulnerability] = []
        for dep in dependencies:
            all_vulns.extend(dep.vulnerabilities)

        return HealthScore(
            overall_score=overall_score,
            grade=HealthGrade.from_score(overall_score),
            metrics=metrics,
            dependencies=dependencies,
            vulnerabilities=all_vulns,
            project_path=project_path,
        )

    def calculate_report(
        self,
        project_path: Path,
        previous: HealthScore | None = None,
    ) -> HealthReport:
        """Calculate a health report with trend information.

        Args:
            project_path: Path to the project root
            previous: Optional previous health score for comparison

        Returns:
            HealthReport with current score and trend
        """
        current = self.calculate(project_path)
        return HealthReport(current=current, previous=previous)

    def _analyze_dependencies(self, project_path: Path) -> list[DependencyHealth]:
        """Analyze all dependencies for shared data.

        This method runs once and provides data for multiple calculators
        to avoid redundant API calls.

        Args:
            project_path: Path to the project

        Returns:
            List of DependencyHealth with all analyzable data
        """
        from codeshift.scanner.dependency_parser import DependencyParser

        parser = DependencyParser(project_path)
        raw_deps = parser.parse_all()

        # Get knowledge base info for tier support
        from codeshift.knowledge_base import KnowledgeBaseLoader

        loader = KnowledgeBaseLoader()
        supported_libraries = loader.get_supported_libraries()
        tier1_libraries = {"pydantic", "fastapi", "sqlalchemy", "pandas", "requests"}

        dependencies: list[DependencyHealth] = []

        for dep in raw_deps:
            dep_name_lower = dep.name.lower()

            # Get latest version and vulnerabilities from PyPI
            latest_version = None
            vulnerabilities: list[SecurityVulnerability] = []

            try:
                import httpx
                from packaging.version import Version

                response = httpx.get(
                    f"https://pypi.org/pypi/{dep.name}/json",
                    timeout=5.0,
                )
                if response.status_code == 200:
                    data = response.json()

                    # Get latest version
                    version_str = data.get("info", {}).get("version")
                    if version_str:
                        latest_version = Version(version_str)

                    # Get vulnerabilities
                    from codeshift.health.models import VulnerabilitySeverity

                    for vuln_data in data.get("vulnerabilities", []):
                        try:
                            severity = VulnerabilitySeverity.MEDIUM
                            vulnerabilities.append(
                                SecurityVulnerability(
                                    package=dep.name,
                                    vulnerability_id=vuln_data.get("id", "unknown"),
                                    severity=severity,
                                    description=vuln_data.get("summary", "")[:200],
                                    fixed_in=(
                                        vuln_data.get("fixed_in", [None])[0]
                                        if vuln_data.get("fixed_in")
                                        else None
                                    ),
                                    url=vuln_data.get("link"),
                                )
                            )
                        except Exception:
                            pass

            except Exception as e:
                logger.debug(f"Failed to fetch PyPI data for {dep.name}: {e}")

            # Calculate version lag
            current = dep.min_version
            is_outdated = False
            major_behind = 0
            minor_behind = 0

            if current and latest_version:
                is_outdated = current < latest_version
                major_behind = max(0, latest_version.major - current.major)
                if major_behind == 0:
                    minor_behind = max(0, latest_version.minor - current.minor)

            # Check tier support
            has_tier1 = dep_name_lower in tier1_libraries
            has_tier2 = dep_name_lower in [lib.lower() for lib in supported_libraries]

            dependencies.append(
                DependencyHealth(
                    name=dep.name,
                    current_version=str(current) if current else None,
                    latest_version=str(latest_version) if latest_version else None,
                    is_outdated=is_outdated,
                    major_versions_behind=major_behind,
                    minor_versions_behind=minor_behind,
                    has_tier1_support=has_tier1,
                    has_tier2_support=has_tier2,
                    vulnerabilities=vulnerabilities,
                )
            )

        return dependencies
