"""Data models for the knowledge base."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ChangeType(Enum):
    """Types of breaking changes."""

    RENAMED = "renamed"
    REMOVED = "removed"
    SIGNATURE_CHANGED = "signature_changed"
    BEHAVIOR_CHANGED = "behavior_changed"
    DEPRECATED = "deprecated"
    TYPE_CHANGED = "type_changed"


class Severity(Enum):
    """Severity levels for breaking changes."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class BreakingChange:
    """Represents a single breaking change in a library."""

    symbol: str  # e.g., "BaseModel.Config", "@validator", ".dict()"
    change_type: ChangeType
    severity: Severity
    from_version: str
    to_version: str
    description: str
    replacement: Optional[str] = None  # e.g., "model_config = ConfigDict(...)"
    has_deterministic_transform: bool = False
    transform_name: Optional[str] = None  # e.g., "config_to_configdict"
    migration_guide_url: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "BreakingChange":
        """Create a BreakingChange from a dictionary."""
        return cls(
            symbol=data["symbol"],
            change_type=ChangeType(data["change_type"]),
            severity=Severity(data["severity"]),
            from_version=data["from_version"],
            to_version=data["to_version"],
            description=data["description"],
            replacement=data.get("replacement"),
            has_deterministic_transform=data.get("has_deterministic_transform", False),
            transform_name=data.get("transform_name"),
            migration_guide_url=data.get("migration_guide_url"),
            notes=data.get("notes"),
        )


@dataclass
class LibraryKnowledge:
    """Knowledge about a library's breaking changes."""

    name: str
    display_name: str
    description: str
    migration_guide_url: Optional[str]
    supported_migrations: list[tuple[str, str]]  # List of (from_version, to_version)
    breaking_changes: list[BreakingChange] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "LibraryKnowledge":
        """Create a LibraryKnowledge from a dictionary."""
        breaking_changes = [BreakingChange.from_dict(bc) for bc in data.get("breaking_changes", [])]
        supported_migrations = [(m["from"], m["to"]) for m in data.get("supported_migrations", [])]

        return cls(
            name=data["name"],
            display_name=data["display_name"],
            description=data.get("description", ""),
            migration_guide_url=data.get("migration_guide_url"),
            supported_migrations=supported_migrations,
            breaking_changes=breaking_changes,
        )

    def get_changes_for_migration(self, from_version: str, to_version: str) -> list[BreakingChange]:
        """Get all breaking changes relevant to a specific migration."""
        from packaging.version import Version

        from_v = Version(from_version)
        to_v = Version(to_version)

        relevant = []
        for change in self.breaking_changes:
            change_from = Version(change.from_version)
            change_to = Version(change.to_version)

            # Include if the change affects versions between from and to
            if change_from >= from_v and change_to <= to_v:
                relevant.append(change)

        return relevant

    def get_deterministic_transforms(
        self, from_version: str, to_version: str
    ) -> list[BreakingChange]:
        """Get all breaking changes that have deterministic transforms."""
        changes = self.get_changes_for_migration(from_version, to_version)
        return [c for c in changes if c.has_deterministic_transform]
