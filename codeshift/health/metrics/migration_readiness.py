"""Migration readiness metric calculator."""

import logging
from pathlib import Path

from codeshift.health.metrics import BaseMetricCalculator
from codeshift.health.models import DependencyHealth, MetricCategory, MetricResult
from codeshift.knowledge_base import KnowledgeBaseLoader
from codeshift.scanner.dependency_parser import DependencyParser

logger = logging.getLogger(__name__)


class MigrationReadinessCalculator(BaseMetricCalculator):
    """Calculates migration readiness score (20% weight).

    Score based on Tier 1/2 support coverage:
    - Tier 1 (deterministic AST): 100% score contribution
    - Tier 2 (knowledge base + LLM): 50% score contribution
    - No support: 0% score contribution
    """

    @property
    def category(self) -> MetricCategory:
        return MetricCategory.MIGRATION_READINESS

    @property
    def weight(self) -> float:
        return 0.20

    def calculate(
        self,
        project_path: Path,
        dependencies: list[DependencyHealth] | None = None,
        **kwargs,
    ) -> MetricResult:
        """Calculate the migration readiness score.

        Args:
            project_path: Path to the project
            dependencies: Pre-populated dependency health list (optional)

        Returns:
            MetricResult with migration readiness score
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

        tier1_count = sum(1 for d in dependencies if d.has_tier1_support)
        tier2_count = sum(1 for d in dependencies if d.has_tier2_support and not d.has_tier1_support)
        no_support_count = len(dependencies) - tier1_count - tier2_count

        total = len(dependencies)
        # Score: Tier 1 gets full points, Tier 2 gets half points
        score = ((tier1_count * 100) + (tier2_count * 50)) / total if total > 0 else 100

        # Build recommendations
        recommendations: list[str] = []

        if no_support_count > 0:
            unsupported = [d.name for d in dependencies if not d.has_tier1_support and not d.has_tier2_support]
            recommendations.append(
                f"Consider requesting Tier 1 support for: {', '.join(unsupported[:3])}"
                + (f" (+{len(unsupported) - 3} more)" if len(unsupported) > 3 else "")
            )

        if tier2_count > 0:
            tier2_deps = [d.name for d in dependencies if d.has_tier2_support and not d.has_tier1_support]
            recommendations.append(
                f"Libraries with Tier 2 (LLM) support: {', '.join(tier2_deps[:3])}"
            )

        return self._create_result(
            score=score,
            description=f"{tier1_count} Tier 1, {tier2_count} Tier 2, {no_support_count} unsupported",
            details={
                "total_dependencies": total,
                "tier1_count": tier1_count,
                "tier2_count": tier2_count,
                "unsupported_count": no_support_count,
                "tier1_ratio": tier1_count / total if total > 0 else 0,
                "tier2_ratio": tier2_count / total if total > 0 else 0,
            },
            recommendations=recommendations,
        )

    def _analyze_dependencies(self, project_path: Path) -> list[DependencyHealth]:
        """Analyze project dependencies for migration support.

        Args:
            project_path: Path to the project

        Returns:
            List of DependencyHealth objects with tier support info
        """
        parser = DependencyParser(project_path)
        dependencies = parser.parse_all()

        loader = KnowledgeBaseLoader()
        supported_libraries = loader.get_supported_libraries()

        results: list[DependencyHealth] = []

        # Tier 1 supported libraries (have AST transformers)
        tier1_libraries = {"pydantic", "fastapi", "sqlalchemy", "pandas", "requests"}

        for dep in dependencies:
            dep_name_lower = dep.name.lower()

            # Check Tier 1 support (deterministic AST transforms)
            has_tier1 = dep_name_lower in tier1_libraries

            # Check Tier 2 support (knowledge base exists)
            has_tier2 = dep_name_lower in [lib.lower() for lib in supported_libraries]

            results.append(
                DependencyHealth(
                    name=dep.name,
                    current_version=str(dep.min_version) if dep.min_version else None,
                    latest_version=None,
                    is_outdated=False,
                    has_tier1_support=has_tier1,
                    has_tier2_support=has_tier2,
                )
            )

        return results
