"""
Redis client for caching LightRAG queries and responses.
"""

import redis.asyncio as aioredis
import json
import hashlib
import logging
from typing import Optional, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

redis_client: Optional[aioredis.Redis] = None


async def init_redis():
    """Initialize Redis connection"""
    global redis_client
    
    try:
        redis_client = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            decode_responses=True,
            socket_connect_timeout=5
        )
        
        # Test connection
        await redis_client.ping()
        logger.info("Redis connection initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")
        # Continue without Redis (graceful degradation)
        redis_client = None


async def close_redis():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")


def get_cache_key(query: str, knowledge_base: str = "default") -> str:
    """Generate cache key for a query"""
    # Normalize query (uppercase, strip whitespace)
    normalized_query = query.upper().strip()
    query_hash = hashlib.md5(normalized_query.encode()).hexdigest()
    return f"lightrag:{knowledge_base}:query:{query_hash}"


class RedisCache:
    """Redis-based cache manager for LightRAG queries"""
    
    def __init__(self):
        self.client = redis_client
        self.ttl = settings.REDIS_CACHE_TTL
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        if not self.client:
            return None
        
        try:
            cached = await self.client.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set cached value"""
        if not self.client:
            return False
        
        try:
            ttl = ttl or self.ttl
            await self.client.setex(
                key,
                ttl,
                json.dumps(value)
            )
            return True
        except Exception as e:
            logger.warning(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete cached value"""
        if not self.client:
            return False
        
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")
            return False
    
    async def clear_cache(self, pattern: str = "lightrag:*") -> int:
        """Clear all cache entries matching pattern"""
        if not self.client:
            return 0
        
        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                return await self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Redis clear cache error: {e}")
            return 0

