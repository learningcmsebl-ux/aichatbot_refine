"""
Redis client for caching LightRAG queries and responses.
"""

import redis.asyncio as aioredis
import json
import hashlib
import logging
from typing import Optional, Any, List, Dict

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
    # Normalize query: lowercase, strip whitespace, normalize multiple spaces
    import re
    normalized_query = re.sub(r'\s+', ' ', query.lower().strip())
    query_hash = hashlib.md5(normalized_query.encode('utf-8')).hexdigest()
    return f"lightrag:{knowledge_base}:query:{query_hash}"


class RedisCache:
    """Redis-based cache manager for LightRAG queries"""
    
    def __init__(self):
        self.client = redis_client
        self.ttl = settings.REDIS_CACHE_TTL
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        if not self.client:
            logger.info(f"[CACHE] Redis client not available - returning None for key: {key}")
            return None
        
        try:
            cached = await self.client.get(key)
            if cached:
                logger.info(f"[CACHE] HIT for key: {key}")
                return json.loads(cached)
            logger.info(f"[CACHE] MISS for key: {key}")
            return None
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set cached value"""
        if not self.client:
            logger.info(f"[CACHE] Redis client not available - cannot set key: {key}")
            return False
        
        try:
            ttl = ttl or self.ttl
            await self.client.setex(
                key,
                ttl,
                json.dumps(value)
            )
            logger.info(f"[CACHE] SET for key: {key} with TTL: {ttl}s")
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
    
    def _get_disambiguation_key(self, session_id: str) -> str:
        """Generate key for disambiguation state"""
        return f"disambiguation:{session_id}"
    
    async def store_disambiguation_state(
        self, 
        session_id: str, 
        product_line: str,
        charge_type: str,
        as_of_date: str,
        options: List[Dict[str, Any]],
        disambiguation_type: Optional[str] = None,
        prompt_message: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Store disambiguation state for a session.
        
        Args:
            session_id: Session ID
            product_line: Product line (e.g., RETAIL_ASSETS)
            charge_type: Charge type (e.g., PROCESSING_FEE)
            as_of_date: Date string (YYYY-MM-DD)
            options: List of option dicts with loan_product, loan_product_name, etc.
            disambiguation_type: Type of disambiguation ("LOAN_PRODUCT" or "CHARGE_CONTEXT")
            prompt_message: The exact prompt message to reuse on reprompt
        
        Returns:
            True if stored successfully
        """
        if not self.client:
            logger.info(f"[DISAMBIGUATION] Redis client not available - cannot store state for session: {session_id}")
            return False
        
        try:
            key = self._get_disambiguation_key(session_id)
            state = {
                "product_line": product_line,
                "charge_type": charge_type,
                "as_of_date": as_of_date,
                "options": options,  # List of dicts with loan_product, loan_product_name, charge_type, charge_context
                "disambiguation_type": disambiguation_type,  # "LOAN_PRODUCT" or "CHARGE_CONTEXT"
                "prompt_message": prompt_message,  # Exact prompt message to reuse on reprompt
                "extra": extra or {},
            }
            ttl = 300  # 5 minutes
            await self.client.setex(key, ttl, json.dumps(state))
            logger.info(f"[DISAMBIGUATION] Stored state for session {session_id} with TTL {ttl}s (type={disambiguation_type})")
            return True
        except Exception as e:
            logger.warning(f"Redis store disambiguation state error: {e}")
            return False
    
    async def get_disambiguation_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get disambiguation state for a session.
        
        Args:
            session_id: Session ID
        
        Returns:
            Disambiguation state dict or None if not found/expired
        """
        if not self.client:
            return None
        
        try:
            key = self._get_disambiguation_key(session_id)
            cached = await self.client.get(key)
            if cached:
                logger.info(f"[DISAMBIGUATION] Found state for session {session_id}")
                return json.loads(cached)
            return None
        except Exception as e:
            logger.warning(f"Redis get disambiguation state error: {e}")
            return None
    
    async def clear_disambiguation_state(self, session_id: str) -> bool:
        """
        Clear disambiguation state for a session.
        
        Args:
            session_id: Session ID
        
        Returns:
            True if cleared successfully
        """
        if not self.client:
            return False
        
        try:
            key = self._get_disambiguation_key(session_id)
            result = await self.client.delete(key)
            if result:
                logger.info(f"[DISAMBIGUATION] Cleared state for session {session_id}")
            return result > 0
        except Exception as e:
            logger.warning(f"Redis clear disambiguation state error: {e}")
            return False

