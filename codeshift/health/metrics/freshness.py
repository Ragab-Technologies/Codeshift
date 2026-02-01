"""Dependency freshness metric calculator."""

import logging
from pathlib import Path

import httpx
from packaging.version import Version

from codeshift.health.metrics import BaseMetricCalculator
from codeshift.health.models import DependencyHealth, MetricCategory, MetricResult
from codeshift.scanner.dependency_parser import DependencyParser

logger = logging.getLogger(__name__)

# PyPI API timeout
PYPI_TIMEOUT = 5.0


class FreshnessCalculator(BaseMetricCalculator):
    """Calculates dependency freshness score (30% weight).

    Score is based on how up-to-date dependencies are:
    - Major version behind: -15 points per dependency
    - Minor version behind: -5 points each (up to 3 per dependency)
    """

    @property
    def category(self) -> MetricCategory:
        return MetricCategory.FRESHNESS

    @property
    def weight(self) -> float:
        return 0.30

    def calculate(
        self,
        project_path: Path,
        dependencies: list[DependencyHealth] | None = None,
        **kwargs,
    ) -> MetricResult:
        """Calculate the freshness score.

        Args:
            project_path: Path to the project
            dependencies: Pre-populated dependency health list (optional)

        Returns:
            MetricResult with freshness score
        """
        if dependencies is None:
            dependencies = self._analyze_dependencies(project_path)

        if not dependencies:
            return self._create_result(
                score=100,
                description="No dependencies to analyze",
                details={"dependency_count": 0},
                recommendations=[],
            )

        # Calculate penalty
        total_penalty = 0
        outdated_deps: list[str] = []
        major_outdated: list[str] = []

        for dep in dependencies:
            if dep.is_outdated:
                outdated_deps.append(dep.name)
                penalty = dep.version_lag_penalty
                total_penalty += penalty

                if dep.major_versions_behind > 0:
                    major_outdated.append(
                        f"{dep.name} ({dep.current_version} -> {dep.latest_version})"
                    )

        # Score starts at 100, subtract penalties (min 0)
        score = max(0, 100 - total_penalty)

        # Build recommendations
        recommendations: list[str] = []
        if major_outdated:
            recommendations.append(
                f"Update major versions: {', '.join(major_outdated[:3])}"
                + (f" (+{len(major_outdated) - 3} more)" if len(major_outdated) > 3 else "")
            )
        if len(outdated_deps) > len(major_outdated):
            minor_count = len(outdated_deps) - len(major_outdated)
            recommendations.append(f"Update {minor_count} dependencies with minor version updates")

        return self._create_result(
            score=score,
            description=f"{len(outdated_deps)}/{len(dependencies)} dependencies outdated",
            details={
                "total_dependencies": len(dependencies),
                "outdated_count": len(outdated_deps),
                "major_outdated_count": len(major_outdated),
                "total_penalty": total_penalty,
            },
            recommendations=recommendations,
        )

    def _analyze_dependencies(self, project_path: Path) -> list[DependencyHealth]:
        """Analyze project dependencies for freshness.

        Args:
            project_path: Path to the project

        Returns:
            List of DependencyHealth objects
        """
        parser = DependencyParser(project_path)
        dependencies = parser.parse_all()

        results: list[DependencyHealth] = []

        for dep in dependencies:
            try:
                latest = self._get_latest_version(dep.name)
                current = dep.min_version

                if current and latest:
                    is_outdated = current < latest
                    major_behind = max(0, latest.major - current.major)
                    minor_behind = 0
                    if major_behind == 0:
                        minor_behind = max(0, latest.minor - current.minor)
                else:
                    is_outdated = False
                    major_behind = 0
                    minor_behind = 0

                results.append(
                    DependencyHealth(
                        name=dep.name,
                        current_version=str(current) if current else None,
                        latest_version=str(latest) if latest else None,
                        is_outdated=is_outdated,
                        major_versions_behind=major_behind,
                        minor_versions_behind=minor_behind,
                    )
                )
            except Exception as e:
                logger.debug(f"Error analyzing {dep.name}: {e}")
                # Add with unknown status
                results.append(
                    DependencyHealth(
                        name=dep.name,
                        current_version=str(dep.min_version) if dep.min_version else None,
                        latest_version=None,
                        is_outdated=False,
                    )
                )

        return results

    def _get_latest_version(self, package_name: str) -> Version | None:
        """Get the latest version of a package from PyPI.

        Args:
            package_name: Name of the package

        Returns:
            Latest Version or None if not found
        """
        try:
            response = httpx.get(
                f"https://pypi.org/pypi/{package_name}/json",
                timeout=PYPI_TIMEOUT,
            )
            if response.status_code == 200:
                data = response.json()
                version_str = data.get("info", {}).get("version")
                if version_str:
                    return Version(version_str)
        except Exception as e:
            logger.debug(f"Failed to get latest version for {package_name}: {e}")

        return None
