"""Knowledge acquisition pipeline for auto-generated knowledge bases."""

from pyresolve.knowledge.cache import KnowledgeCache, get_knowledge_cache
from pyresolve.knowledge.generator import (
    TIER_1_LIBRARIES,
    KnowledgeGenerator,
    generate_knowledge_base,
    generate_knowledge_base_sync,
    get_knowledge_generator,
    is_tier_1_library,
)
from pyresolve.knowledge.models import (
    BreakingChange,
    ChangeCategory,
    ChangelogSource,
    Confidence,
    GeneratedKnowledgeBase,
)
from pyresolve.knowledge.parser import ChangelogParser, get_changelog_parser
from pyresolve.knowledge.sources import (
    PackageInfo,
    SourceFetcher,
    get_source_fetcher,
)

__all__ = [
    # Models
    "BreakingChange",
    "ChangeCategory",
    "ChangelogSource",
    "Confidence",
    "GeneratedKnowledgeBase",
    # Sources
    "PackageInfo",
    "SourceFetcher",
    "get_source_fetcher",
    # Parser
    "ChangelogParser",
    "get_changelog_parser",
    # Cache
    "KnowledgeCache",
    "get_knowledge_cache",
    # Generator
    "KnowledgeGenerator",
    "generate_knowledge_base",
    "generate_knowledge_base_sync",
    "get_knowledge_generator",
    "is_tier_1_library",
    "TIER_1_LIBRARIES",
]
