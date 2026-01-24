"""Cache for LLM responses and expensive operations."""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CacheEntry:
    """A cached entry with metadata."""

    key: str
    value: Any
    created_at: float
    expires_at: float | None = None
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class Cache:
    """Simple file-based cache for PyResolve."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        default_ttl: int | None = None,
    ):
        """Initialize the cache.

        Args:
            cache_dir: Directory to store cache files.
                      Defaults to ~/.pyresolve/cache
            default_ttl: Default time-to-live in seconds. None means no expiration.
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".pyresolve" / "cache"
        self.cache_dir = cache_dir
        self.default_ttl = default_ttl
        self._memory_cache: dict[str, CacheEntry] = {}

    def _ensure_dir(self) -> None:
        """Ensure the cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _make_key(self, *args: Any) -> str:
        """Create a cache key from arguments."""
        key_data = json.dumps(args, sort_keys=True, default=str)
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    def _get_cache_path(self, key: str) -> Path:
        """Get the file path for a cache key."""
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> Any | None:
        """Get a value from the cache.

        Args:
            key: The cache key

        Returns:
            The cached value or None if not found/expired
        """
        # Check memory cache first
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if not entry.is_expired:
                entry.hits += 1
                return entry.value
            else:
                del self._memory_cache[key]

        # Check file cache
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text())
                entry = CacheEntry(
                    key=data["key"],
                    value=data["value"],
                    created_at=data["created_at"],
                    expires_at=data.get("expires_at"),
                    hits=data.get("hits", 0),
                )

                if entry.is_expired:
                    cache_path.unlink()
                    return None

                # Store in memory cache
                entry.hits += 1
                self._memory_cache[key] = entry

                # Update file with new hit count
                data["hits"] = entry.hits
                cache_path.write_text(json.dumps(data))

                return entry.value

            except (json.JSONDecodeError, KeyError):
                # Invalid cache file, remove it
                cache_path.unlink()

        return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a value in the cache.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds. None uses default, 0 means no expiration.
        """
        self._ensure_dir()

        if ttl is None:
            ttl = self.default_ttl

        now = time.time()
        expires_at = now + ttl if ttl else None

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=now,
            expires_at=expires_at,
            hits=0,
        )

        # Store in memory
        self._memory_cache[key] = entry

        # Store in file
        cache_path = self._get_cache_path(key)
        cache_path.write_text(
            json.dumps(
                {
                    "key": entry.key,
                    "value": entry.value,
                    "created_at": entry.created_at,
                    "expires_at": entry.expires_at,
                    "hits": entry.hits,
                }
            )
        )

    def delete(self, key: str) -> bool:
        """Delete a value from the cache.

        Args:
            key: The cache key

        Returns:
            True if the key was found and deleted
        """
        found = False

        if key in self._memory_cache:
            del self._memory_cache[key]
            found = True

        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
            found = True

        return found

    def clear(self) -> int:
        """Clear all cached entries.

        Returns:
            Number of entries cleared
        """
        count = len(self._memory_cache)
        self._memory_cache.clear()

        if self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
                count += 1

        return count

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        count = 0

        # Clean memory cache
        expired_keys = [k for k, v in self._memory_cache.items() if v.is_expired]
        for key in expired_keys:
            del self._memory_cache[key]
            count += 1

        # Clean file cache
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    data = json.loads(cache_file.read_text())
                    expires_at = data.get("expires_at")
                    if expires_at and time.time() > expires_at:
                        cache_file.unlink()
                        count += 1
                except (json.JSONDecodeError, KeyError):
                    cache_file.unlink()
                    count += 1

        return count

    def stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        memory_entries = len(self._memory_cache)
        file_entries = len(list(self.cache_dir.glob("*.json"))) if self.cache_dir.exists() else 0
        total_hits = sum(e.hits for e in self._memory_cache.values())

        return {
            "memory_entries": memory_entries,
            "file_entries": file_entries,
            "total_hits": total_hits,
            "cache_dir": str(self.cache_dir),
        }


class LLMCache(Cache):
    """Specialized cache for LLM responses."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        default_ttl: int = 86400 * 7,  # 7 days default
    ):
        """Initialize the LLM cache.

        Args:
            cache_dir: Directory to store cache files
            default_ttl: Default TTL in seconds (default: 7 days)
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".pyresolve" / "cache" / "llm"
        super().__init__(cache_dir, default_ttl)

    def get_migration(
        self,
        code: str,
        library: str,
        from_version: str,
        to_version: str,
    ) -> str | None:
        """Get a cached migration result.

        Args:
            code: The source code
            library: Library name
            from_version: Source version
            to_version: Target version

        Returns:
            Cached migrated code or None
        """
        key = self._make_key("migrate", code, library, from_version, to_version)
        return self.get(key)

    def set_migration(
        self,
        code: str,
        library: str,
        from_version: str,
        to_version: str,
        result: str,
    ) -> None:
        """Cache a migration result.

        Args:
            code: The source code
            library: Library name
            from_version: Source version
            to_version: Target version
            result: The migrated code
        """
        key = self._make_key("migrate", code, library, from_version, to_version)
        self.set(key, result)


# Default cache instances
_default_cache: Cache | None = None
_llm_cache: LLMCache | None = None


def get_cache() -> Cache:
    """Get the default cache instance."""
    global _default_cache
    if _default_cache is None:
        _default_cache = Cache()
    return _default_cache


def get_llm_cache() -> LLMCache:
    """Get the LLM cache instance."""
    global _llm_cache
    if _llm_cache is None:
        _llm_cache = LLMCache()
    return _llm_cache
