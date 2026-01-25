"""Knowledge base module for breaking change definitions."""

from codeshift.knowledge_base.loader import KnowledgeBaseLoader
from codeshift.knowledge_base.models import (
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
