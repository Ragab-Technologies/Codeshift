"""Knowledge base generator - orchestrates the knowledge acquisition pipeline."""

from typing import Callable, Optional

from pyresolve.knowledge.cache import KnowledgeCache, get_knowledge_cache
from pyresolve.knowledge.models import (
    BreakingChange,
    Confidence,
    GeneratedKnowledgeBase,
)
from pyresolve.knowledge.parser import ChangelogParser, get_changelog_parser
from pyresolve.knowledge.sources import SourceFetcher, get_source_fetcher


class KnowledgeGenerator:
    """Orchestrates knowledge base generation from multiple sources."""

    def __init__(
        self,
        fetcher: Optional[SourceFetcher] = None,
        parser: Optional[ChangelogParser] = None,
        cache: Optional[KnowledgeCache] = None,
        use_cache: bool = True,
    ):
        """Initialize the generator.

        Args:
            fetcher: Source fetcher instance.
            parser: Changelog parser instance.
            cache: Knowledge cache instance.
            use_cache: Whether to use caching.
        """
        self.fetcher = fetcher or get_source_fetcher()
        self.parser = parser or get_changelog_parser()
        self.cache = cache or get_knowledge_cache() if use_cache else None
        self.use_cache = use_cache

    def generate(
        self,
        package: str,
        old_version: str,
        new_version: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> GeneratedKnowledgeBase:
        """Generate a knowledge base for a package migration.

        Args:
            package: Package name.
            old_version: Starting version.
            new_version: Target version.
            progress_callback: Optional callback for progress updates.

        Returns:
            GeneratedKnowledgeBase with detected breaking changes.
        """

        def report(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        # Check cache first
        if self.use_cache and self.cache:
            cached = self.cache.get(package, old_version, new_version)
            if cached:
                report("Using cached knowledge base")
                return cached

        report("Fetching changelog sources...")

        # Discover sources
        sources = self.fetcher.discover_sources_sync(package, new_version)

        if not sources:
            report("No changelog sources found")
            return GeneratedKnowledgeBase(
                package=package,
                old_version=old_version,
                new_version=new_version,
                overall_confidence=Confidence.LOW,
            )

        source_urls = [s.url for s in sources]
        report(f"Found {len(sources)} source(s)")

        # Extract version-specific content from changelogs
        for source in sources:
            if source.source_type == "changelog":
                source.content = self.fetcher.extract_version_changelog(
                    source.content,
                    old_version,
                    new_version,
                )

        # Parse sources with LLM
        breaking_changes: list[BreakingChange] = []

        if self.parser.is_available:
            report("Parsing changelog with LLM...")
            breaking_changes = self.parser.parse_multiple_sources(
                sources,
                package,
                old_version,
                new_version,
            )
            report(f"Found {len(breaking_changes)} breaking change(s)")
        else:
            report("LLM not available - skipping changelog parsing")

        # Determine overall confidence
        overall_confidence = self._calculate_overall_confidence(breaking_changes, sources)

        # Create knowledge base
        kb = GeneratedKnowledgeBase(
            package=package,
            old_version=old_version,
            new_version=new_version,
            breaking_changes=breaking_changes,
            sources=source_urls,
            overall_confidence=overall_confidence,
        )

        # Cache result
        if self.use_cache and self.cache:
            self.cache.set(kb)
            report("Cached knowledge base")

        return kb

    def _calculate_overall_confidence(
        self,
        changes: list[BreakingChange],
        sources: list,
    ) -> Confidence:
        """Calculate overall confidence based on changes and sources.

        Args:
            changes: List of breaking changes.
            sources: List of sources used.

        Returns:
            Overall confidence level.
        """
        if not changes:
            return Confidence.LOW

        # Check if we have migration guide (high confidence source)
        has_migration_guide = any(s.source_type == "migration_guide" for s in sources)

        if has_migration_guide:
            return Confidence.HIGH

        # Count confidence levels
        high_count = sum(1 for c in changes if c.confidence == Confidence.HIGH)
        medium_count = sum(1 for c in changes if c.confidence == Confidence.MEDIUM)

        if high_count >= len(changes) / 2:
            return Confidence.HIGH
        elif medium_count + high_count >= len(changes) / 2:
            return Confidence.MEDIUM

        return Confidence.LOW


# Tier 1 libraries with deterministic AST transforms
TIER_1_LIBRARIES = {"pydantic", "fastapi", "sqlalchemy", "pandas", "requests"}


def is_tier_1_library(library: str) -> bool:
    """Check if a library is Tier 1 (has deterministic transforms).

    Args:
        library: Library name.

    Returns:
        True if Tier 1.
    """
    return library.lower() in TIER_1_LIBRARIES


async def generate_knowledge_base(
    package: str,
    old_version: str,
    new_version: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> GeneratedKnowledgeBase:
    """Async interface for generating knowledge base.

    Args:
        package: Package name.
        old_version: Starting version.
        new_version: Target version.
        progress_callback: Optional callback for progress updates.

    Returns:
        GeneratedKnowledgeBase with detected breaking changes.
    """
    generator = KnowledgeGenerator()
    return generator.generate(package, old_version, new_version, progress_callback)


def generate_knowledge_base_sync(
    package: str,
    old_version: str,
    new_version: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> GeneratedKnowledgeBase:
    """Synchronous interface for generating knowledge base.

    Args:
        package: Package name.
        old_version: Starting version.
        new_version: Target version.
        progress_callback: Optional callback for progress updates.

    Returns:
        GeneratedKnowledgeBase with detected breaking changes.
    """
    generator = KnowledgeGenerator()
    return generator.generate(package, old_version, new_version, progress_callback)


# Singleton instance
_default_generator: Optional[KnowledgeGenerator] = None


def get_knowledge_generator() -> KnowledgeGenerator:
    """Get the default knowledge generator instance."""
    global _default_generator
    if _default_generator is None:
        _default_generator = KnowledgeGenerator()
    return _default_generator
