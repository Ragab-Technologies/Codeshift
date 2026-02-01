"""Security vulnerabilities metric calculator."""

import logging
from pathlib import Path

import httpx

from codeshift.health.metrics import BaseMetricCalculator
from codeshift.health.models import (
    DependencyHealth,
    MetricCategory,
    MetricResult,
    SecurityVulnerability,
    VulnerabilitySeverity,
)
from codeshift.scanner.dependency_parser import DependencyParser

logger = logging.getLogger(__name__)

# PyPI API timeout
PYPI_TIMEOUT = 5.0


class SecurityCalculator(BaseMetricCalculator):
    """Calculates security score based on known vulnerabilities (25% weight).

    Penalties:
    - Critical: -25 points
    - High: -15 points
    - Medium: -8 points
    - Low: -3 points
    """

    @property
    def category(self) -> MetricCategory:
        return MetricCategory.SECURITY

    @property
    def weight(self) -> float:
        return 0.25

    def calculate(
        self,
        project_path: Path,
        dependencies: list[DependencyHealth] | None = None,
        **kwargs,
    ) -> MetricResult:
        """Calculate the security score.

        Args:
            project_path: Path to the project
            dependencies: Pre-populated dependency health list (optional)

        Returns:
            MetricResult with security score
        """
        if dependencies is None:
            dependencies = self._analyze_dependencies(project_path)

        if not dependencies:
            return self._create_result(
                score=100,
                description="No dependencies to analyze",
                details={"dependency_count": 0, "vulnerability_count": 0},
                recommendations=[],
            )

        # Collect all vulnerabilities
        all_vulns: list[SecurityVulnerability] = []
        vuln_counts = {
            VulnerabilitySeverity.CRITICAL: 0,
            VulnerabilitySeverity.HIGH: 0,
            VulnerabilitySeverity.MEDIUM: 0,
            VulnerabilitySeverity.LOW: 0,
        }

        for dep in dependencies:
            for vuln in dep.vulnerabilities:
                all_vulns.append(vuln)
                vuln_counts[vuln.severity] += 1

        # Calculate penalty
        total_penalty = sum(
            count * severity.penalty for severity, count in vuln_counts.items()
        )
        score = max(0, 100 - total_penalty)

        # Build recommendations
        recommendations: list[str] = []
        if vuln_counts[VulnerabilitySeverity.CRITICAL] > 0:
            critical_pkgs = list(
                {v.package for v in all_vulns if v.severity == VulnerabilitySeverity.CRITICAL}
            )
            recommendations.append(
                f"URGENT: Fix critical vulnerabilities in: {', '.join(critical_pkgs)}"
            )

        if vuln_counts[VulnerabilitySeverity.HIGH] > 0:
            high_pkgs = list(
                {v.package for v in all_vulns if v.severity == VulnerabilitySeverity.HIGH}
            )
            recommendations.append(
                f"Address high severity vulnerabilities in: {', '.join(high_pkgs)}"
            )

        if vuln_counts[VulnerabilitySeverity.MEDIUM] > 0:
            recommendations.append(
                f"Review {vuln_counts[VulnerabilitySeverity.MEDIUM]} medium severity vulnerabilities"
            )

        return self._create_result(
            score=score,
            description=f"{len(all_vulns)} vulnerabilities found" if all_vulns else "No known vulnerabilities",
            details={
                "total_vulnerabilities": len(all_vulns),
                "critical": vuln_counts[VulnerabilitySeverity.CRITICAL],
                "high": vuln_counts[VulnerabilitySeverity.HIGH],
                "medium": vuln_counts[VulnerabilitySeverity.MEDIUM],
                "low": vuln_counts[VulnerabilitySeverity.LOW],
                "total_penalty": total_penalty,
            },
            recommendations=recommendations,
        )

    def _analyze_dependencies(self, project_path: Path) -> list[DependencyHealth]:
        """Analyze project dependencies for security vulnerabilities.

        Args:
            project_path: Path to the project

        Returns:
            List of DependencyHealth objects with vulnerability data
        """
        parser = DependencyParser(project_path)
        dependencies = parser.parse_all()

        results: list[DependencyHealth] = []

        for dep in dependencies:
            vulns = self._get_vulnerabilities(dep.name)
            results.append(
                DependencyHealth(
                    name=dep.name,
                    current_version=str(dep.min_version) if dep.min_version else None,
                    latest_version=None,
                    is_outdated=False,
                    vulnerabilities=vulns,
                )
            )

        return results

    def _get_vulnerabilities(self, package_name: str) -> list[SecurityVulnerability]:
        """Get known vulnerabilities for a package from PyPI.

        Args:
            package_name: Name of the package

        Returns:
            List of SecurityVulnerability objects
        """
        vulns: list[SecurityVulnerability] = []

        try:
            response = httpx.get(
                f"https://pypi.org/pypi/{package_name}/json",
                timeout=PYPI_TIMEOUT,
            )
            if response.status_code == 200:
                data = response.json()
                vulnerabilities = data.get("vulnerabilities", [])

                for vuln_data in vulnerabilities:
                    severity_str = self._parse_severity(vuln_data)
                    try:
                        severity = VulnerabilitySeverity(severity_str.lower())
                    except ValueError:
                        severity = VulnerabilitySeverity.MEDIUM

                    fixed_in = None
                    if vuln_data.get("fixed_in"):
                        fixed_versions = vuln_data.get("fixed_in", [])
                        if fixed_versions:
                            fixed_in = fixed_versions[0]

                    vulns.append(
                        SecurityVulnerability(
                            package=package_name,
                            vulnerability_id=vuln_data.get("id", "unknown"),
                            severity=severity,
                            description=vuln_data.get("summary", vuln_data.get("details", ""))[:200],
                            fixed_in=fixed_in,
                            url=vuln_data.get("link"),
                        )
                    )

        except Exception as e:
            logger.debug(f"Failed to get vulnerabilities for {package_name}: {e}")

        return vulns

    def _parse_severity(self, vuln_data: dict) -> str:
        """Parse severity from vulnerability data.

        Args:
            vuln_data: Vulnerability data dictionary

        Returns:
            Severity string (critical, high, medium, low)
        """
        # Try to get severity from aliases (e.g., CVE data)
        aliases = vuln_data.get("aliases", [])
        for alias in aliases:
            if "CRITICAL" in alias.upper():
                return "critical"
            elif "HIGH" in alias.upper():
                return "high"

        # Default to medium if not specified
        return "medium"
