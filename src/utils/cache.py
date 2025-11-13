"""Caching utilities for Arena Improver.

Provides in-memory and persistent caching for:
- API responses
- Meta intelligence data
- Deck analyses
- Embedding computations
"""

import asyncio
import json
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, Generic
from functools import wraps
import hashlib

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheEntry(Generic[T]):
    """Single cache entry with expiration."""

    def __init__(self, value: T, ttl: float):
        """Initialize cache entry.

        Args:
            value: Cached value
            ttl: Time-to-live in seconds (0 = no expiration)
        """
        self.value = value
        self.timestamp = time.time()
        self.ttl = ttl

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl == 0:
            return False
        return (time.time() - self.timestamp) > self.ttl

    def age(self) -> float:
        """Get age of entry in seconds."""
        return time.time() - self.timestamp


class LRUCache(Generic[T]):
    """Thread-safe LRU cache with TTL support."""

    def __init__(self, max_size: int = 1000, default_ttl: float = 3600):
        """Initialize LRU cache.

        Args:
            max_size: Maximum number of entries
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[T]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                logger.debug(f"Cache entry expired: {key} (age: {entry.age():.1f}s)")
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            logger.debug(f"Cache hit: {key} (age: {entry.age():.1f}s)")
            return entry.value

    async def set(self, key: str, value: T, ttl: Optional[float] = None):
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        if ttl is None:
            ttl = self.default_ttl

        async with self._lock:
            # Remove oldest if at capacity
            if key not in self._cache and len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                logger.debug(f"Cache eviction: {oldest_key}")
                del self._cache[oldest_key]

            self._cache[key] = CacheEntry(value, ttl)
            self._cache.move_to_end(key)
            logger.debug(f"Cache set: {key} (ttl: {ttl}s)")

    async def delete(self, key: str):
        """Delete entry from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache delete: {key}")

    async def clear(self):
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            logger.info("Cache cleared")

    async def cleanup_expired(self):
        """Remove all expired entries."""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

    def stats(self) -> dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "utilization": len(self._cache) / self.max_size
        }


class PersistentCache:
    """Disk-based cache for long-term storage."""

    def __init__(self, cache_dir: str = "data/cache", default_ttl: float = 86400):
        """Initialize persistent cache.

        Args:
            cache_dir: Directory to store cache files
            default_ttl: Default time-to-live in seconds (24 hours default)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl
        self._lock = asyncio.Lock()

    def _get_cache_path(self, key: str) -> Path:
        """Get file path for cache key."""
        # Hash key to create safe filename
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from persistent cache."""
        cache_path = self._get_cache_path(key)

        def _read_and_check() -> Optional[Any]:
            """Blocking I/O operation to read and check cache file."""
            if not cache_path.exists():
                return None

            try:
                with open(cache_path, 'r') as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                # Handle partially written or corrupted files
                logger.warning(f"Corrupted cache file {key}: {e}")
                return None

            # Check expiration
            timestamp = data.get('timestamp', 0)
            ttl = data.get('ttl', self.default_ttl)

            if ttl > 0 and (time.time() - timestamp) > ttl:
                logger.debug(f"Persistent cache expired: {key}")
                cache_path.unlink()  # Delete expired file
                return None

            logger.debug(f"Persistent cache hit: {key}")
            return data.get('value')

        try:
            # Read under lock to prevent seeing partially written files
            async with self._lock:
                return await asyncio.to_thread(_read_and_check)

        except Exception as e:
            logger.warning(f"Error reading persistent cache {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Set value in persistent cache."""
        if ttl is None:
            ttl = self.default_ttl

        cache_path = self._get_cache_path(key)

        def _write_file() -> None:
            """Blocking I/O operation to write cache file atomically."""
            data = {
                'key': key,
                'value': value,
                'timestamp': time.time(),
                'ttl': ttl
            }

            # Write to temp file first, then atomic rename to prevent partial reads
            temp_path = cache_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            temp_path.replace(cache_path)  # Atomic on POSIX systems

            logger.debug(f"Persistent cache set: {key}")

        try:
            async with self._lock:
                # Ensure directory exists while holding lock
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                # Perform I/O while holding lock to prevent race conditions
                await asyncio.to_thread(_write_file)

        except Exception as e:
            logger.warning(f"Error writing persistent cache {key}: {e}")

    async def delete(self, key: str):
        """Delete entry from persistent cache."""
        cache_path = self._get_cache_path(key)

        def _delete_file():
            """Blocking I/O operation to delete cache file."""
            if cache_path.exists():
                cache_path.unlink()
                logger.debug(f"Persistent cache delete: {key}")

        try:
            # Perform blocking I/O in thread pool
            await asyncio.to_thread(_delete_file)
        except Exception as e:
            logger.warning(f"Error deleting persistent cache {key}: {e}")

    async def clear(self):
        """Clear all persistent cache entries."""
        
        def _clear_files():
            """Blocking I/O operation to clear all cache files."""
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("Persistent cache cleared")
        
        try:
            # Perform blocking I/O in thread pool
            await asyncio.to_thread(_clear_files)
        except Exception as e:
            logger.warning(f"Error clearing persistent cache: {e}")

    async def cleanup_expired(self):
        """Remove all expired cache files."""
        
        def _cleanup_one_file(cache_file):
            """Check and remove one expired cache file."""
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)

                timestamp = data.get('timestamp', 0)
                ttl = data.get('ttl', self.default_ttl)

                if ttl > 0 and (time.time() - timestamp) > ttl:
                    cache_file.unlink()
                    return True  # File was expired and removed
                return False  # File is still valid
            except Exception as e:
                logger.warning(f"Error checking cache file {cache_file}: {e}")
                return False

        def _cleanup_all():
            """Blocking I/O operation to cleanup expired files."""
            expired_count = 0
            for cache_file in self.cache_dir.glob("*.json"):
                if _cleanup_one_file(cache_file):
                    expired_count += 1
            return expired_count

        try:
            # Perform blocking I/O in thread pool
            expired_count = await asyncio.to_thread(_cleanup_all)

            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired persistent cache entries")

        except Exception as e:
            logger.warning(f"Error cleaning up persistent cache: {e}")


def cache_key(*args, **kwargs) -> str:
    """Generate cache key from function arguments."""
    
    # Convert args and kwargs to a stable string representation
    key_parts = []

    def serialize_value(value):
        """Serialize a value to a stable string representation."""
        if isinstance(value, (str, int, float, bool, type(None))):
            # For primitives, use simple string representation
            # Use json.dumps for strings to handle escaping, but remove quotes
            if isinstance(value, str):
                # Use JSON serialization for proper escaping, then strip quotes
                json_str = json.dumps(value, sort_keys=True)
                return json_str[1:-1] if json_str.startswith('"') else json_str
            else:
                return str(value)
        elif isinstance(value, (list, tuple)):
            # Recursively serialize sequences - JSON serialize entire structure
            return json.dumps(value, default=str, sort_keys=True)
        elif isinstance(value, dict):
            # Recursively serialize dicts with sorted keys
            return json.dumps(value, default=str, sort_keys=True)
        else:
            # Use a stable hash for non-serializable types
            # Avoid repr() as it can include memory addresses
            return f"{type(value).__module__}.{type(value).__qualname__}:{hash(str(value))}"

    for arg in args:
        key_parts.append(serialize_value(arg))

    for k, v in sorted(kwargs.items()):
        serialized = serialize_value(v)
        key_parts.append(f"{k}={serialized}")

    return ":".join(key_parts)


def cached(
    cache: LRUCache,
    ttl: Optional[float] = None,
    key_func: Optional[Callable] = None
):
    """Decorator to cache function results.

    Args:
        cache: Cache instance to use
        ttl: Time-to-live for cached result (uses cache default if None)
        key_func: Function to generate cache key (uses default if None)

    Usage:
        cache = LRUCache(max_size=100, default_ttl=3600)

        @cached(cache, ttl=1800)
        async def expensive_operation(param1, param2):
            # Your code here
            return result
    """
    if key_func is None:
        key_func = cache_key

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Generate cache key
            key = f"{func.__name__}:{key_func(*args, **kwargs)}"

            # Try to get from cache
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(key, result, ttl)

            return result

        return wrapper

    return decorator


# Global cache instances
_meta_cache = LRUCache(max_size=100, default_ttl=3600)  # 1 hour
_deck_cache = LRUCache(max_size=500, default_ttl=1800)  # 30 minutes
_persistent_cache = PersistentCache(cache_dir="data/cache", default_ttl=86400)  # 24 hours


def get_meta_cache() -> LRUCache:
    """Get global meta intelligence cache."""
    return _meta_cache


def get_deck_cache() -> LRUCache:
    """Get global deck analysis cache."""
    return _deck_cache


def get_persistent_cache() -> PersistentCache:
    """Get global persistent cache."""
    return _persistent_cache
