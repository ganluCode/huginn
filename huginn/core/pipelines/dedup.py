"""DedupPipeline: Content-based deduplication using Redis.

This pipeline uses content hashing to detect and filter duplicate items.
Duplicate detection is per-source (different sources don't interfere).
"""

import logging

from redis import Redis

from huginn.core.items import CollectedItem
from huginn.core.pipelines import Pipeline
from huginn.core.utils.text import content_hash

logger = logging.getLogger(__name__)


class DedupPipeline(Pipeline):
    """Content-based deduplication pipeline.

    Uses Redis sets to track seen items by content hash. Items with the same
    content (regardless of field order) are detected as duplicates.

    Duplicate detection is isolated per source - the same content from
    different sources is not considered duplicate.
    """

    def __init__(self, redis_url: str, ttl: int = 604800, _redis_client: Redis | None = None):
        """Initialize the deduplication pipeline.

        Args:
            redis_url: Redis connection URL.
            ttl: Time-to-live for dedup sets in seconds (default: 7 days).
            _redis_client: Optional Redis client for testing.
        """
        self.redis_url = redis_url
        self.ttl = ttl

        if _redis_client is not None:
            self._redis = _redis_client
        else:
            self._redis = Redis.from_url(redis_url, decode_responses=True)

    def process(self, item: CollectedItem) -> CollectedItem | None:
        """Check if item is duplicate and filter if so.

        Args:
            item: The item to check.

        Returns:
            The item if not seen before, None if duplicate.
        """
        hash_key = self._get_hash_key(item)
        set_key = self._get_set_key(item.source)

        try:
            # Check if already in set
            if self._redis.sismember(set_key, hash_key):
                logger.debug("Duplicate item detected: source=%s hash=%s", item.source, hash_key)
                return None

            # Add to set
            self._redis.sadd(set_key, hash_key)

            # Set TTL if not already set
            if self._redis.ttl(set_key) == -1:
                self._redis.expire(set_key, self.ttl)

            return item

        except (ConnectionError, Exception) as e:
            # Fallback: return item on Redis errors
            logger.warning("Redis error during deduplication: %s. Returning item.", e)
            return item

    def _get_hash_key(self, item: CollectedItem) -> str:
        """Get the content hash key for an item.

        Uses first 16 chars of SHA256 hash of item data.
        """
        return content_hash(item.data)

    def _get_set_key(self, source: str) -> str:
        """Get the Redis set key for a source."""
        return f"huginn:dedup:{source}"
