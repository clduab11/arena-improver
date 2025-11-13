"""Tests for caching utilities."""

import asyncio
import pytest
import tempfile
import shutil
from pathlib import Path

from src.utils.cache import (
    CacheEntry,
    LRUCache,
    PersistentCache,
    cache_key,
    cached
)


class TestCacheEntry:
    """Tests for CacheEntry."""

    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        entry = CacheEntry(value="test_value", ttl=3600)

        assert entry.value == "test_value"
        assert entry.ttl == 3600
        assert entry.timestamp > 0

    def test_cache_entry_not_expired(self):
        """Test that entry is not expired within TTL."""
        entry = CacheEntry(value="test", ttl=3600)

        assert not entry.is_expired()

    def test_cache_entry_expired(self):
        """Test that entry expires after TTL."""
        entry = CacheEntry(value="test", ttl=0.01)  # 10ms TTL

        import time
        time.sleep(0.02)  # Wait 20ms

        assert entry.is_expired()

    def test_cache_entry_no_expiration(self):
        """Test that TTL of 0 means no expiration."""
        entry = CacheEntry(value="test", ttl=0)

        import time
        time.sleep(0.01)

        assert not entry.is_expired()

    def test_cache_entry_age(self):
        """Test that age calculation works."""
        entry = CacheEntry(value="test", ttl=3600)

        import time
        time.sleep(0.01)

        assert entry.age() >= 0.01


class TestLRUCache:
    """Tests for LRUCache."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """Test basic set and get operations."""
        cache = LRUCache(max_size=10, default_ttl=3600)

        await cache.set("key1", "value1")
        result = await cache.get("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Test that get returns None for missing keys."""
        cache = LRUCache(max_size=10, default_ttl=3600)

        result = await cache.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """Test that expired entries are not returned."""
        cache = LRUCache(max_size=10, default_ttl=0.01)

        await cache.set("key1", "value1", ttl=0.01)

        # Wait for expiration
        await asyncio.sleep(0.02)

        result = await cache.get("key1")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self):
        """Test that least recently used items are evicted."""
        cache = LRUCache(max_size=3, default_ttl=3600)

        # Fill cache
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")

        # Access key1 to make it recently used
        await cache.get("key1")

        # Add new key, should evict key2 (least recently used)
        await cache.set("key4", "value4")

        # key1 and key3 should still be in cache
        assert await cache.get("key1") == "value1"
        assert await cache.get("key3") == "value3"

        # key2 should be evicted
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_cache_delete(self):
        """Test that delete removes entries."""
        cache = LRUCache(max_size=10, default_ttl=3600)

        await cache.set("key1", "value1")
        await cache.delete("key1")

        result = await cache.get("key1")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Test that clear removes all entries."""
        cache = LRUCache(max_size=10, default_ttl=3600)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_cache_cleanup_expired(self):
        """Test that cleanup removes expired entries."""
        cache = LRUCache(max_size=10, default_ttl=0.01)

        await cache.set("key1", "value1", ttl=0.01)
        await cache.set("key2", "value2", ttl=3600)  # Not expired

        # Wait for key1 to expire
        await asyncio.sleep(0.02)

        await cache.cleanup_expired()

        # key1 should be gone, key2 should remain
        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Test that stats tracking works."""
        cache = LRUCache(max_size=10, default_ttl=3600)

        await cache.set("key1", "value1")

        # Generate hits and misses
        await cache.get("key1")  # Hit
        await cache.get("key1")  # Hit
        await cache.get("key2")  # Miss

        stats = cache.stats()

        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2/3
        assert stats["size"] == 1
        assert stats["max_size"] == 10


class TestPersistentCache:
    """Tests for PersistentCache."""

    @pytest.mark.asyncio
    async def test_persistent_cache_set_and_get(self):
        """Test basic set and get operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PersistentCache(cache_dir=tmpdir, default_ttl=3600)

            await cache.set("key1", "value1")
            result = await cache.get("key1")

            assert result == "value1"

    @pytest.mark.asyncio
    async def test_persistent_cache_survives_restart(self):
        """Test that cache persists across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First instance
            cache1 = PersistentCache(cache_dir=tmpdir, default_ttl=3600)
            await cache1.set("key1", "value1")

            # Second instance (simulates restart)
            cache2 = PersistentCache(cache_dir=tmpdir, default_ttl=3600)
            result = await cache2.get("key1")

            assert result == "value1"

    @pytest.mark.asyncio
    async def test_persistent_cache_expiration(self):
        """Test that expired entries are not returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PersistentCache(cache_dir=tmpdir, default_ttl=0.01)

            await cache.set("key1", "value1", ttl=0.01)

            # Wait for expiration
            await asyncio.sleep(0.02)

            result = await cache.get("key1")

            assert result is None

    @pytest.mark.asyncio
    async def test_persistent_cache_delete(self):
        """Test that delete removes files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PersistentCache(cache_dir=tmpdir, default_ttl=3600)

            await cache.set("key1", "value1")
            await cache.delete("key1")

            result = await cache.get("key1")

            assert result is None

    @pytest.mark.asyncio
    async def test_persistent_cache_clear(self):
        """Test that clear removes all files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PersistentCache(cache_dir=tmpdir, default_ttl=3600)

            await cache.set("key1", "value1")
            await cache.set("key2", "value2")
            await cache.clear()

            assert await cache.get("key1") is None
            assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_persistent_cache_cleanup_expired(self):
        """Test that cleanup removes expired files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PersistentCache(cache_dir=tmpdir, default_ttl=0.01)

            await cache.set("key1", "value1", ttl=0.01)
            await cache.set("key2", "value2", ttl=3600)

            # Wait for key1 to expire
            await asyncio.sleep(0.02)

            await cache.cleanup_expired()

            # key1 should be gone, key2 should remain
            assert await cache.get("key1") is None
            assert await cache.get("key2") == "value2"


class TestCacheKey:
    """Tests for cache_key function."""

    def test_cache_key_simple_args(self):
        """Test cache key generation with simple arguments."""
        key = cache_key("arg1", 42, True)

        assert "arg1" in key
        assert "42" in key
        assert "True" in key

    def test_cache_key_with_kwargs(self):
        """Test cache key generation with keyword arguments."""
        key = cache_key(param1="value1", param2=123)

        assert "param1=value1" in key
        assert "param2=123" in key

    def test_cache_key_with_complex_objects(self):
        """Test that complex objects use type name."""
        class CustomClass:
            pass

        obj = CustomClass()
        key = cache_key(obj)

        assert "CustomClass" in key

    def test_cache_key_deterministic(self):
        """Test that cache key is deterministic."""
        key1 = cache_key("arg1", param="value")
        key2 = cache_key("arg1", param="value")

        assert key1 == key2


class TestCachedDecorator:
    """Tests for cached decorator."""

    @pytest.mark.asyncio
    async def test_cached_decorator_basic(self):
        """Test that cached decorator caches results."""
        cache = LRUCache(max_size=10, default_ttl=3600)
        call_count = 0

        @cached(cache)
        async def expensive_func(param):
            nonlocal call_count
            call_count += 1
            return f"result_{param}"

        # First call should execute function
        result1 = await expensive_func("test")
        assert result1 == "result_test"
        assert call_count == 1

        # Second call should use cache
        result2 = await expensive_func("test")
        assert result2 == "result_test"
        assert call_count == 1  # Not incremented

    @pytest.mark.asyncio
    async def test_cached_decorator_different_args(self):
        """Test that different arguments create different cache entries."""
        cache = LRUCache(max_size=10, default_ttl=3600)
        call_count = 0

        @cached(cache)
        async def func(param):
            nonlocal call_count
            call_count += 1
            return f"result_{param}"

        # Call with different parameters
        result1 = await func("param1")
        result2 = await func("param2")

        assert result1 == "result_param1"
        assert result2 == "result_param2"
        assert call_count == 2  # Both calls executed

        # Call with same parameter should use cache
        result3 = await func("param1")
        assert result3 == "result_param1"
        assert call_count == 2  # Not incremented

    @pytest.mark.asyncio
    async def test_cached_decorator_with_ttl(self):
        """Test that TTL is respected."""
        cache = LRUCache(max_size=10, default_ttl=0.01)
        call_count = 0

        @cached(cache, ttl=0.01)
        async def func():
            nonlocal call_count
            call_count += 1
            return "result"

        # First call
        result1 = await func()
        assert result1 == "result"
        assert call_count == 1

        # Wait for expiration
        await asyncio.sleep(0.02)

        # Second call should re-execute
        result2 = await func()
        assert result2 == "result"
        assert call_count == 2
