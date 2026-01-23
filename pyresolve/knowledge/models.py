"""Data models for auto-generated knowledge bases."""

from dataclasses import dataclass, field
from enum import Enum


class ChangeCategory(Enum):
    """Categories of breaking changes."""

    REMOVED = "removed"
    RENAMED = "renamed"
    SIGNATURE_CHANGED = "signature_changed"
    BEHAVIOR_CHANGED = "behavior_changed"


class Confidence(Enum):
    """Confidence levels for detected changes."""

    HIGH = "high"  # From migration guide or explicit changelog
    MEDIUM = "medium"  # From changelog parsing
    LOW = "low"  # From AST diff only

    def __ge__(self, other: "Confidence") -> bool:
        order = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}
        return order[self] >= order[other]

    def __gt__(self, other: "Confidence") -> bool:
        order = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}
        return order[self] > order[other]

    def __le__(self, other: "Confidence") -> bool:
        order = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}
        return order[self] <= order[other]

    def __lt__(self, other: "Confidence") -> bool:
        order = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}
        return order[self] < order[other]


@dataclass
class BreakingChange:
    """Represents a single breaking change detected from sources."""

    category: ChangeCategory
    old_api: str
    new_api: str | None
    description: str
    confidence: Confidence
    source: str | None = None  # Where this change was detected from

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "category": self.category.value,
            "old_api": self.old_api,
            "new_api": self.new_api,
            "description": self.description,
            "confidence": self.confidence.value,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BreakingChange":
        """Create from dictionary."""
        return cls(
            category=ChangeCategory(data["category"]),
            old_api=data["old_api"],
            new_api=data.get("new_api"),
            description=data["description"],
            confidence=Confidence(data["confidence"]),
            source=data.get("source"),
        )


@dataclass
class ChangelogSource:
    """Represents a source of changelog information."""

    url: str
    source_type: str  # "changelog", "migration_guide", "release_notes"
    content: str
    version_range: tuple[str, str] | None = None  # (from_version, to_version)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "source_type": self.source_type,
            "content": self.content,
            "version_range": self.version_range,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChangelogSource":
        """Create from dictionary."""
        return cls(
            url=data["url"],
            source_type=data["source_type"],
            content=data["content"],
            version_range=tuple(data["version_range"]) if data.get("version_range") else None,
        )


@dataclass
class GeneratedKnowledgeBase:
    """Auto-generated knowledge base from changelogs and API diffs."""

    package: str
    old_version: str
    new_version: str
    breaking_changes: list[BreakingChange] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)  # URLs of sources used
    overall_confidence: Confidence = Confidence.LOW

    @property
    def has_changes(self) -> bool:
        """Check if there are any breaking changes."""
        return len(self.breaking_changes) > 0

    def get_changes_by_confidence(self, min_confidence: Confidence) -> list[BreakingChange]:
        """Get changes with at least the specified confidence level."""
        return [c for c in self.breaking_changes if c.confidence >= min_confidence]

    def get_changes_by_category(self, category: ChangeCategory) -> list[BreakingChange]:
        """Get changes of a specific category."""
        return [c for c in self.breaking_changes if c.category == category]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "package": self.package,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "breaking_changes": [c.to_dict() for c in self.breaking_changes],
            "sources": self.sources,
            "overall_confidence": self.overall_confidence.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GeneratedKnowledgeBase":
        """Create from dictionary."""
        return cls(
            package=data["package"],
            old_version=data["old_version"],
            new_version=data["new_version"],
            breaking_changes=[
                BreakingChange.from_dict(c) for c in data.get("breaking_changes", [])
            ],
            sources=data.get("sources", []),
            overall_confidence=Confidence(data.get("overall_confidence", "low")),
        )
