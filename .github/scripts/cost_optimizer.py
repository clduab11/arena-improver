#!/usr/bin/env python3
"""
Cost Optimization Module

Implements caching, rate limiting, and batch processing to reduce API costs.
"""

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass
class CacheEntry:
    """Cache entry for review results."""

    key: str
    content_hash: str
    review_result: str
    model: str
    timestamp: datetime
    ttl: int  # seconds


class CostOptimizer:
    """Cost optimization utilities."""

    def __init__(self, cache_db: str = ".github/review_cache.db") -> None:
        """Initialize cost optimizer."""
        self.cache_db = cache_db
        self.rate_limit_file = ".github/rate_limits.json"
        self.batch_queue_file = ".github/batch_queue.json"

        self._init_cache_db()

    def _init_cache_db(self) -> None:
        """Initialize cache database."""
        os.makedirs(os.path.dirname(self.cache_db), exist_ok=True)

        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_cache (
                key TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                review_result TEXT NOT NULL,
                model TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                ttl INTEGER NOT NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_content_hash
            ON review_cache(content_hash)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON review_cache(timestamp)
        """)

        conn.commit()
        conn.close()

    def get_cached_review(
        self, file_content: str, review_mode: str, model: str
    ) -> str | None:
        """
        Get cached review result if available.

        Args:
            file_content: The file content to review
            review_mode: Review mode (triage, standard, deep, security)
            model: Claude model name

        Returns:
            Cached review result or None
        """
        # Generate cache key
        content_hash = self._hash_content(file_content)
        cache_key = f"{content_hash}:{review_mode}:{model}"

        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT review_result, timestamp, ttl FROM review_cache
            WHERE key = ?
        """,
            (cache_key,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        review_result, timestamp_str, ttl = row
        timestamp = datetime.fromisoformat(timestamp_str)

        # Check if cache is still valid
        if datetime.now() - timestamp > timedelta(seconds=ttl):
            # Cache expired
            self._delete_cache_entry(cache_key)
            return None

        print(f"✓ Cache hit for {cache_key[:16]}...")
        return review_result

    def cache_review(
        self,
        file_content: str,
        review_mode: str,
        model: str,
        review_result: str,
        ttl: int = 86400,  # 24 hours
    ) -> None:
        """Cache a review result."""
        content_hash = self._hash_content(file_content)
        cache_key = f"{content_hash}:{review_mode}:{model}"

        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO review_cache
            (key, content_hash, review_result, model, timestamp, ttl)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                cache_key,
                content_hash,
                review_result,
                model,
                datetime.now().isoformat(),
                ttl,
            ),
        )

        conn.commit()
        conn.close()

        print(f"✓ Cached review for {cache_key[:16]}...")

    def check_rate_limit(self, pr_number: int, max_calls: int = 5) -> bool:
        """
        Check if PR has exceeded rate limit.

        Args:
            pr_number: PR number
            max_calls: Maximum API calls per PR

        Returns:
            True if within limit, False if exceeded
        """
        limits = self._load_rate_limits()

        pr_key = f"pr_{pr_number}"
        if pr_key not in limits:
            limits[pr_key] = {
                "count": 0,
                "first_call": datetime.now().isoformat(),
                "last_call": datetime.now().isoformat(),
            }

        # Check count
        if limits[pr_key]["count"] >= max_calls:
            print(f"⚠️  Rate limit exceeded for PR #{pr_number} ({max_calls} calls)")
            return False

        # Increment counter
        limits[pr_key]["count"] += 1
        limits[pr_key]["last_call"] = datetime.now().isoformat()

        self._save_rate_limits(limits)
        return True

    def add_to_batch_queue(self, pr_number: int, priority: int = 3) -> None:
        """Add PR to batch processing queue."""
        queue = self._load_batch_queue()

        queue.append(
            {
                "pr_number": pr_number,
                "priority": priority,
                "added_at": datetime.now().isoformat(),
                "status": "queued",
            }
        )

        self._save_batch_queue(queue)
        print(f"✓ Added PR #{pr_number} to batch queue (priority: {priority})")

    def get_batch(self, max_size: int = 10, max_wait: int = 300) -> list[dict[str, Any]]:
        """
        Get batch of PRs to process together.

        Args:
            max_size: Maximum batch size
            max_wait: Maximum wait time in seconds

        Returns:
            List of PR items to process
        """
        queue = self._load_batch_queue()

        # Filter queued items
        queued = [item for item in queue if item["status"] == "queued"]

        if not queued:
            return []

        # Sort by priority (1 = highest)
        queued.sort(key=lambda x: x["priority"])

        # Check if oldest item has waited long enough
        oldest = queued[0]
        added_at = datetime.fromisoformat(oldest["added_at"])
        wait_time = (datetime.now() - added_at).total_seconds()

        # Return batch if:
        # 1. Queue is full (>= max_size)
        # 2. Oldest item has waited >= max_wait seconds
        if len(queued) >= max_size or wait_time >= max_wait:
            batch = queued[:max_size]

            # Mark as processing
            for item in batch:
                item["status"] = "processing"

            self._save_batch_queue(queue)
            return batch

        return []

    def complete_batch_item(self, pr_number: int) -> None:
        """Mark a batch item as completed."""
        queue = self._load_batch_queue()

        for item in queue:
            if item["pr_number"] == pr_number:
                item["status"] = "completed"
                item["completed_at"] = datetime.now().isoformat()

        self._save_batch_queue(queue)

    def cleanup_cache(self, days: int = 7) -> int:
        """
        Clean up old cache entries.

        Args:
            days: Remove entries older than this

        Returns:
            Number of entries deleted
        """
        cutoff = datetime.now() - timedelta(days=days)

        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM review_cache
            WHERE timestamp < ?
        """,
            (cutoff.isoformat(),),
        )

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        if deleted > 0:
            print(f"✓ Cleaned up {deleted} old cache entries")

        return deleted

    def get_cost_stats(self, days: int = 30) -> dict[str, Any]:
        """Get cost optimization statistics."""
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        # Cache hits
        cursor.execute(
            """
            SELECT COUNT(*) FROM review_cache
            WHERE timestamp > ?
        """,
            (cutoff,),
        )
        cache_entries = cursor.fetchone()[0]

        conn.close()

        # Rate limit stats
        limits = self._load_rate_limits()
        total_calls = sum(item["count"] for item in limits.values())

        # Batch stats
        queue = self._load_batch_queue()
        completed_batches = [item for item in queue if item["status"] == "completed"]

        return {
            "period_days": days,
            "cache": {
                "total_entries": cache_entries,
                "estimated_api_calls_saved": cache_entries,
            },
            "rate_limiting": {
                "total_api_calls": total_calls,
                "unique_prs": len(limits),
                "avg_calls_per_pr": total_calls / len(limits) if limits else 0,
            },
            "batching": {
                "total_batched": len(completed_batches),
                "items_in_queue": len([i for i in queue if i["status"] == "queued"]),
            },
        }

    def _hash_content(self, content: str) -> str:
        """Generate hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def _delete_cache_entry(self, key: str) -> None:
        """Delete a cache entry."""
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM review_cache WHERE key = ?", (key,))
        conn.commit()
        conn.close()

    def _load_rate_limits(self) -> dict[str, Any]:
        """Load rate limit data."""
        if os.path.exists(self.rate_limit_file):
            with open(self.rate_limit_file, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_rate_limits(self, limits: dict[str, Any]) -> None:
        """Save rate limit data."""
        os.makedirs(os.path.dirname(self.rate_limit_file), exist_ok=True)
        with open(self.rate_limit_file, "w", encoding="utf-8") as f:
            json.dump(limits, f, indent=2)

    def _load_batch_queue(self) -> list[dict[str, Any]]:
        """Load batch queue."""
        if os.path.exists(self.batch_queue_file):
            with open(self.batch_queue_file, encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_batch_queue(self, queue: list[dict[str, Any]]) -> None:
        """Save batch queue."""
        os.makedirs(os.path.dirname(self.batch_queue_file), exist_ok=True)
        with open(self.batch_queue_file, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2)


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Cost Optimizer")
    parser.add_argument("--cleanup", action="store_true", help="Clean up old cache")
    parser.add_argument("--stats", action="store_true", help="Show cost stats")
    parser.add_argument("--days", type=int, default=7, help="Days for cleanup/stats")
    args = parser.parse_args()

    optimizer = CostOptimizer()

    if args.cleanup:
        deleted = optimizer.cleanup_cache(args.days)
        print(f"Removed {deleted} cache entries older than {args.days} days")

    if args.stats:
        stats = optimizer.get_cost_stats(args.days)

        print("\n" + "=" * 80)
        print(f"Cost Optimization Statistics ({args.days} days)")
        print("=" * 80)
        print(f"\nCache:")
        print(f"  Total Entries: {stats['cache']['total_entries']}")
        print(f"  API Calls Saved: ~{stats['cache']['estimated_api_calls_saved']}")

        print(f"\nRate Limiting:")
        print(f"  Total API Calls: {stats['rate_limiting']['total_api_calls']}")
        print(f"  Unique PRs: {stats['rate_limiting']['unique_prs']}")
        print(f"  Avg Calls/PR: {stats['rate_limiting']['avg_calls_per_pr']:.1f}")

        print(f"\nBatching:")
        print(f"  Completed Batches: {stats['batching']['total_batched']}")
        print(f"  Queued Items: {stats['batching']['items_in_queue']}")
        print("=" * 80)


if __name__ == "__main__":
    main()
