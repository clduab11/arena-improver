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
        """
        Create a CacheEntry storing a value with a creation timestamp and TTL.
        
        Parameters:
            value (T): The value to store in the cache.
            ttl (float): Time-to-live in seconds; 0 means the entry does not expire.
        """
        self.value = value
        self.timestamp = time.time()
        self.ttl = ttl

    def is_expired(self) -> bool:
        """
        Determine whether this cache entry's time-to-live has been exceeded. Entries with a TTL of 0 never expire.
        
        Returns:
            `True` if the elapsed time since the entry's creation is greater than its TTL, `False` otherwise.
        """
        if self.ttl == 0:
            return False
        return (time.time() - self.timestamp) > self.ttl

    def age(self) -> float:
        """
        Age of the cache entry in seconds.
        
        Returns:
            float: Seconds elapsed since the entry was created.
        """
        return time.time() - self.timestamp


class LRUCache(Generic[T]):
    """Thread-safe LRU cache with TTL support."""

    def __init__(self, max_size: int = 1000, default_ttl: float = 3600):
        """
        Create a new least-recently-used (LRU) in-memory cache with a fixed capacity and default time-to-live.
        
        Parameters:
            max_size (int): Maximum number of entries the cache will hold before evicting the least-recently-used item.
            default_ttl (float): Default time-to-live for entries in seconds; a value of 0 means entries do not expire.
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[T]:
        """
        Retrieve the value associated with the given key from the cache.
        
        If the entry exists and has not expired, it is marked most-recently-used and its value is returned.
        
        Returns:
            The cached value if present and not expired, `None` otherwise.
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
        """
        Store a value in the in-memory LRU cache under the given key.
        
        If the cache is at capacity and the key is new, evict the least-recently-used entry to make room. The entry is recorded with the provided time-to-live (in seconds); if `ttl` is None the cache's `default_ttl` is used. A `ttl` of 0 indicates the entry does not expire. The entry is marked most-recently-used after insertion.
         
        Parameters:
            key (str): Cache key.
            value (T): Value to store.
            ttl (Optional[float]): Time-to-live in seconds for this entry; uses the cache's `default_ttl` when None.
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
        """
        Remove the entry with the given key from the in-memory cache.
        
        If the key exists it will be removed; if it does not exist, no action is taken.
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache delete: {key}")

    async def clear(self):
        """
        Remove all entries from the cache and reset hit/miss counters.
        
        This clears the in-memory store and sets the cache's hit and miss counters back to zero.
        """
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            logger.info("Cache cleared")

    async def cleanup_expired(self):
        """
        Remove expired entries from the in-memory cache.
        
        Deletes cache entries whose TTL has elapsed, mutating the cache state. If any entries are removed, an informational log is emitted.
        """
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
        """
        Return cache metrics including current size, capacity, hit/miss counts, hit rate, and utilization.
        
        Returns:
            stats (dict): Mapping with the following keys:
                - size (int): Number of entries currently stored in the cache.
                - max_size (int): Configured maximum number of entries the cache can hold.
                - hits (int): Total number of cache hits.
                - misses (int): Total number of cache misses.
                - hit_rate (float): Ratio of hits to total lookups (value between 0 and 1).
                - utilization (float): Fraction of capacity currently used (value between 0 and 1).
        """
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
        """
        Initialize the persistent disk-backed cache and create its storage directory.
        
        Parameters:
            cache_dir (str): Path to the directory where cache files will be stored; directory is created if it does not exist.
            default_ttl (float): Default time-to-live for cache entries in seconds (default 86400, i.e., 24 hours).
        
        Notes:
            Sets up an internal asyncio lock for concurrent access.
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl
        self._lock = asyncio.Lock()

    def _get_cache_path(self, key: str) -> Path:
        """
        Return the filesystem path where a cache entry for the given key is stored.
        
        The path is deterministic: it uses the SHA-256 hash of `key` as a safe filename and appends the `.json` extension inside the cache directory.
        
        Parameters:
            key (str): Cache key used to derive the filename.
        
        Returns:
            Path: Filesystem path to the JSON file for the given cache key.
        """
        # Hash key to create safe filename
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from the persistent disk cache for the given key.
        
        If a cache file exists for the key and its TTL has not elapsed, the stored value is returned.
        If the entry is expired, the file is removed and `None` is returned. On missing files or any
        read/parsing error, `None` is returned.
        
        Returns:
            The stored value if present and not expired, `None` otherwise.
        """
        cache_path = self._get_cache_path(key)

        try:
            async with self._lock:
                if not cache_path.exists():
                    return None

                with open(cache_path, 'r') as f:
                    data = json.load(f)

                # Check expiration
                timestamp = data.get('timestamp', 0)
                ttl = data.get('ttl', self.default_ttl)

                if ttl > 0 and (time.time() - timestamp) > ttl:
                    logger.debug(f"Persistent cache expired: {key}")
                    cache_path.unlink()  # Delete expired file
                    return None

                logger.debug(f"Persistent cache hit: {key}")
                return data.get('value')

        except Exception as e:
            logger.warning(f"Error reading persistent cache {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """
        Store a value in the persistent disk cache under the given key.
        
        Parameters:
            key (str): Cache key used to identify the entry.
            value (Any): JSON-serializable value to store.
            ttl (Optional[float]): Time-to-live in seconds for this entry; if omitted, the cache's default_ttl is used. A value of 0 means the entry does not expire.
        """
        if ttl is None:
            ttl = self.default_ttl

        cache_path = self._get_cache_path(key)

        try:
            async with self._lock:
                data = {
                    'key': key,
                    'value': value,
                    'timestamp': time.time(),
                    'ttl': ttl
                }

                with open(cache_path, 'w') as f:
                    json.dump(data, f, indent=2)

                logger.debug(f"Persistent cache set: {key}")

        except Exception as e:
            logger.warning(f"Error writing persistent cache {key}: {e}")

    async def delete(self, key: str):
        """
        Remove the on-disk cache entry associated with the given key.
        
        Deletes the persistent cache file for the key if it exists; I/O errors are caught and logged and will not be raised.
        """
        cache_path = self._get_cache_path(key)

        try:
            async with self._lock:
                if cache_path.exists():
                    cache_path.unlink()
                    logger.debug(f"Persistent cache delete: {key}")
        except Exception as e:
            logger.warning(f"Error deleting persistent cache {key}: {e}")

    async def clear(self):
        """
        Clear all entries in the persistent disk cache by deleting every JSON cache file in the cache directory.
        
        This operation acquires the cache's async lock to prevent concurrent access; I/O errors are caught and logged rather than raised.
        """
        try:
            async with self._lock:
                for cache_file in self.cache_dir.glob("*.json"):
                    cache_file.unlink()
                logger.info("Persistent cache cleared")
        except Exception as e:
            logger.warning(f"Error clearing persistent cache: {e}")

    async def cleanup_expired(self):
        """
        Remove expired entries from the persistent disk cache.
        
        Scans JSON cache files in the cache directory and deletes files whose stored
        timestamp plus TTL is older than the current time. Logs a summary when any
        entries are removed and emits warnings for individual file-read or cleanup errors.
        """
        expired_count = 0

        try:
            async with self._lock:
                for cache_file in self.cache_dir.glob("*.json"):
                    try:
                        with open(cache_file, 'r') as f:
                            data = json.load(f)

                        timestamp = data.get('timestamp', 0)
                        ttl = data.get('ttl', self.default_ttl)

                        if ttl > 0 and (time.time() - timestamp) > ttl:
                            cache_file.unlink()
                            expired_count += 1

                    except Exception as e:
                        logger.warning(f"Error checking cache file {cache_file}: {e}")
                        continue

            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired persistent cache entries")

        except Exception as e:
            logger.warning(f"Error cleaning up persistent cache: {e}")


def cache_key(*args, **kwargs) -> str:
    """
    Generate a stable string fragment representing the provided positional and keyword arguments for use in cache keys.
    
    Positional arguments are converted to their string form for common scalar types (str, int, float, bool); other objects are represented by their type name. Keyword arguments are sorted by key and formatted as `key=value` for scalar values or `key=TypeName` for non-scalar values. Parts are joined with colons.
    
    Returns:
        key (str): Colon-separated representation of the arguments suitable for use as a cache key fragment.
    """
    # Convert args and kwargs to a stable string representation
    key_parts = []

    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        else:
            # Use type name for complex objects
            key_parts.append(f"{type(arg).__name__}")

    for k, v in sorted(kwargs.items()):
        if isinstance(v, (str, int, float, bool)):
            key_parts.append(f"{k}={v}")
        else:
            key_parts.append(f"{k}={type(v).__name__}")

    return ":".join(key_parts)


def cached(
    cache: LRUCache,
    ttl: Optional[float] = None,
    key_func: Optional[Callable] = None
):
    """
    Create a decorator that caches a function's results in the provided LRUCache.
    
    The returned decorator builds a cache key as "func_name:<key_parts>" where <key_parts> is produced by `key_func`. The decorator expects the decorated callable to be asynchronous: it will attempt to retrieve a cached value before awaiting the function and will store the awaited result in the cache.
    
    Parameters:
        cache (LRUCache): Cache instance used to store and retrieve values.
        ttl (Optional[float]): Time-to-live in seconds for cached entries; if None, the cache's default TTL is used.
        key_func (Optional[Callable]): Function that receives the decorated function's args and kwargs and returns a stable string fragment for the key; if None, the module's `cache_key` is used.
    
    Returns:
        Callable: A decorator that, when applied to an async function, caches its return value using the constructed key and TTL.
    """
    if key_func is None:
        key_func = cache_key

    def decorator(func: Callable) -> Callable:
        """
        Wrap an async function so its results are cached in the enclosing LRUCache using the provided key function and TTL.
        
        The wrapper builds a composite cache key using the wrapped function's name and the key function's stable representation of the call arguments, returns a cached result when present, and otherwise executes the wrapped function, caches its result with the configured TTL, and returns it.
        
        Parameters:
            func (Callable): The asynchronous function to wrap.
        
        Returns:
            Callable: An async function that returns the wrapped function's result, using cached values when available.
        """
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
    """
    Get the global LRU cache used for meta intelligence data.
    
    Returns:
        LRUCache: The module-level cache instance configured for meta intelligence entries.
    """
    return _meta_cache


def get_deck_cache() -> LRUCache:
    """
    Access the global LRU cache used for deck analyses.
    
    Returns:
        The global LRUCache instance used for caching deck analysis results.
    """
    return _deck_cache


def get_persistent_cache() -> PersistentCache:
    """
    Return the module's shared disk-backed persistent cache instance.
    
    Returns:
        The singleton PersistentCache used for long-term (disk) caching.
    """
    return _persistent_cache