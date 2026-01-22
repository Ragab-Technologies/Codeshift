"""Cache for generated knowledge bases."""

import json
import time
from pathlib import Path
from typing import Optional

from pyresolve.knowledge.models import GeneratedKnowledgeBase


class KnowledgeCache:
    """Cache for storing generated knowledge bases."""

    DEFAULT_TTL = 86400 * 7  # 7 days

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl: int = DEFAULT_TTL,
    ):
        """Initialize the cache.

        Args:
            cache_dir: Directory to store cache files.
            ttl: Time-to-live in seconds.
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".pyresolve" / "cache" / "knowledge"
        self.cache_dir = cache_dir
        self.ttl = ttl

    def _ensure_dir(self) -> None:
        """Ensure cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, package: str, old_version: str, new_version: str) -> str:
        """Generate cache key for a knowledge base."""
        return f"{package}_{old_version}_to_{new_version}".replace(".", "_")

    def _get_cache_path(self, key: str) -> Path:
        """Get file path for a cache key."""
        return self.cache_dir / f"{key}.json"

    def get(
        self,
        package: str,
        old_version: str,
        new_version: str,
    ) -> Optional[GeneratedKnowledgeBase]:
        """Get a cached knowledge base.

        Args:
            package: Package name.
            old_version: Starting version.
            new_version: Target version.

        Returns:
            Cached GeneratedKnowledgeBase or None if not found/expired.
        """
        key = self._get_cache_key(package, old_version, new_version)
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            data = json.loads(cache_path.read_text())

            # Check expiration
            created_at = data.get("_created_at", 0)
            if time.time() - created_at > self.ttl:
                cache_path.unlink()
                return None

            return GeneratedKnowledgeBase.from_dict(data["knowledge_base"])

        except (json.JSONDecodeError, KeyError):
            # Invalid cache, remove it
            cache_path.unlink(missing_ok=True)
            return None

    def set(self, kb: GeneratedKnowledgeBase) -> None:
        """Store a knowledge base in cache.

        Args:
            kb: GeneratedKnowledgeBase to cache.
        """
        self._ensure_dir()

        key = self._get_cache_key(kb.package, kb.old_version, kb.new_version)
        cache_path = self._get_cache_path(key)

        data = {
            "_created_at": time.time(),
            "knowledge_base": kb.to_dict(),
        }

        cache_path.write_text(json.dumps(data, indent=2))

    def delete(self, package: str, old_version: str, new_version: str) -> bool:
        """Delete a cached knowledge base.

        Args:
            package: Package name.
            old_version: Starting version.
            new_version: Target version.

        Returns:
            True if deleted, False if not found.
        """
        key = self._get_cache_key(package, old_version, new_version)
        cache_path = self._get_cache_path(key)

        if cache_path.exists():
            cache_path.unlink()
            return True
        return False

    def clear(self) -> int:
        """Clear all cached knowledge bases.

        Returns:
            Number of entries cleared.
        """
        count = 0
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
                count += 1
        return count

    def list_cached(self) -> list[tuple[str, str, str]]:
        """List all cached knowledge bases.

        Returns:
            List of (package, old_version, new_version) tuples.
        """
        cached: list[tuple[str, str, str]] = []
        if not self.cache_dir.exists():
            return cached

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(cache_file.read_text())
                kb_data = data.get("knowledge_base", {})
                cached.append(
                    (
                        kb_data.get("package", ""),
                        kb_data.get("old_version", ""),
                        kb_data.get("new_version", ""),
                    )
                )
            except Exception:
                continue

        return cached


# Singleton instance
_default_cache: Optional[KnowledgeCache] = None


def get_knowledge_cache() -> KnowledgeCache:
    """Get the default knowledge cache instance."""
    global _default_cache
    if _default_cache is None:
        _default_cache = KnowledgeCache()
    return _default_cache
