"""Knowledge base module for breaking change definitions."""

from pyresolve.knowledge_base.loader import KnowledgeBaseLoader
from pyresolve.knowledge_base.models import (
    BreakingChange,
    ChangeType,
    LibraryKnowledge,
    Severity,
)

__all__ = [
    "KnowledgeBaseLoader",
    "BreakingChange",
    "ChangeType",
    "Severity",
    "LibraryKnowledge",
]
