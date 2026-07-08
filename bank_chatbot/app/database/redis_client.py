"""
Redis client for caching LightRAG queries and responses.
Includes OpenAI response caching for token optimization.
"""

import redis.asyncio as aioredis
import json
import hashlib
import logging
import re
from typing import Optional, Any, List, Dict

from app.core.config import settings

logger = logging.getLogger(__name__)

# Response cache TTL (default 2 hours for OpenAI responses)
RESPONSE_CACHE_TTL = int(settings.REDIS_CACHE_TTL) if hasattr(settings, 'REDIS_CACHE_TTL') else 7200

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
    
    # ============================================================
    # OpenAI Response Caching (Token Optimization)
    # ============================================================
    
    def _get_response_cache_key(
        self,
        query: str,
        context_hash: str,
        knowledge_base: Optional[str] = None,
        route_scope: Optional[str] = None,
    ) -> str:
        """
        Generate cache key for OpenAI response.
        
        Args:
            query: Normalized user query
            context_hash: Hash of the context used for the response
            knowledge_base: KB version/name so cache invalidates when KB changes
            route_scope: Routing target (e.g. OPENAI_SMALL_TALK vs LIGHTRAG)
        
        Returns:
            Cache key string
        """
        # Normalize query for consistent caching
        normalized_query = re.sub(r'\s+', ' ', query.lower().strip())
        kb_part = (knowledge_base or "default").strip().lower()
        scope_part = (route_scope or "LIGHTRAG").strip().lower()
        combined = f"{scope_part}:{kb_part}:{normalized_query}:{context_hash}"
        cache_hash = hashlib.md5(combined.encode('utf-8')).hexdigest()
        return f"openai_response:{cache_hash}"
    
    def _hash_context(self, context: str) -> str:
        """
        Generate hash for context content.
        
        Args:
            context: The context string (from LightRAG/Fee Engine)
        
        Returns:
            MD5 hash of the context
        """
        if not context:
            return "empty"
        return hashlib.md5(context.encode('utf-8')).hexdigest()[:16]
    
    async def get_cached_response(
        self, 
        query: str, 
        context: str,
        include_metadata: bool = False,
        knowledge_base: Optional[str] = None,
        route_scope: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached OpenAI response for a query+context combination.
        
        Args:
            query: User query
            context: Context used for the response (from LightRAG/Fee Engine)
            include_metadata: If True, return full cache entry with metadata
        
        Returns:
            Cached response dict with 'response' key, or None if not found
        """
        if not self.client:
            logger.debug("[RESPONSE_CACHE] Redis not available - cache disabled")
            return None
        
        try:
            context_hash = self._hash_context(context)
            cache_key = self._get_response_cache_key(
                query,
                context_hash,
                knowledge_base=knowledge_base,
                route_scope=route_scope,
            )
            
            cached = await self.client.get(cache_key)
            if cached:
                data = json.loads(cached)
                logger.info(
                    f"[RESPONSE_CACHE] HIT for query: '{query[:50]}...' "
                    f"(kb={knowledge_base or 'default'}, context_hash: {context_hash})"
                )
                
                # Update hit count for analytics
                try:
                    await self.client.hincrby("response_cache:stats", "hits", 1)
                except Exception:
                    pass  # Stats are optional
                
                if include_metadata:
                    return data
                return {"response": data.get("response"), "sources": data.get("sources", [])}
            
            logger.debug(f"[RESPONSE_CACHE] MISS for query: '{query[:50]}...'")
            try:
                await self.client.hincrby("response_cache:stats", "misses", 1)
            except Exception:
                pass  # Stats are optional
            
            return None
        except Exception as e:
            logger.warning(f"[RESPONSE_CACHE] Get error: {e}")
            return None
    
    async def cache_response(
        self,
        query: str,
        context: str,
        response: str,
        sources: Optional[List[str]] = None,
        ttl: Optional[int] = None,
        routing_target: Optional[str] = None,
        knowledge_base: Optional[str] = None,
        route_scope: Optional[str] = None,
    ) -> bool:
        """
        Cache an OpenAI response.
        
        Args:
            query: User query
            context: Context used for the response
            response: The OpenAI response to cache
            sources: Optional list of sources used
            ttl: Time-to-live in seconds (default: RESPONSE_CACHE_TTL)
            routing_target: The routing target (for analytics)
        
        Returns:
            True if cached successfully
        """
        if not self.client:
            logger.debug("[RESPONSE_CACHE] Redis not available - cannot cache")
            return False
        
        # Don't cache error responses
        error_indicators = [
            "technical difficulties",
            "apologize",
            "try again later",
            "error occurred",
            "could not find reliable information in the knowledge base",
        ]
        response_lower = response.lower()
        if any(indicator in response_lower for indicator in error_indicators):
            logger.debug("[RESPONSE_CACHE] Not caching error response")
            return False
        
        # Don't cache very short responses (likely errors or incomplete)
        if len(response) < 50:
            logger.debug(f"[RESPONSE_CACHE] Not caching short response ({len(response)} chars)")
            return False
        
        try:
            context_hash = self._hash_context(context)
            cache_key = self._get_response_cache_key(
                query,
                context_hash,
                knowledge_base=knowledge_base,
                route_scope=route_scope,
            )
            
            cache_data = {
                "response": response,
                "sources": sources or [],
                "query": query[:200],  # Store truncated query for debugging
                "context_hash": context_hash,
                "knowledge_base": knowledge_base or "default",
                "routing_target": routing_target,
                "cached_at": __import__('datetime').datetime.utcnow().isoformat()
            }
            
            effective_ttl = ttl or RESPONSE_CACHE_TTL
            await self.client.setex(
                cache_key,
                effective_ttl,
                json.dumps(cache_data)
            )
            
            logger.info(
                f"[RESPONSE_CACHE] CACHED response for query: '{query[:50]}...' "
                f"(TTL: {effective_ttl}s, context_hash: {context_hash}, "
                f"response_len: {len(response)})"
            )
            return True
        except Exception as e:
            logger.warning(f"[RESPONSE_CACHE] Set error: {e}")
            return False
    
    async def get_response_cache_stats(self) -> Dict[str, Any]:
        """
        Get response cache statistics.
        
        Returns:
            Dict with hits, misses, and hit rate
        """
        if not self.client:
            return {"hits": 0, "misses": 0, "hit_rate": 0.0, "available": False}
        
        try:
            stats = await self.client.hgetall("response_cache:stats")
            hits = int(stats.get("hits", 0))
            misses = int(stats.get("misses", 0))
            total = hits + misses
            hit_rate = round((hits / total * 100), 2) if total > 0 else 0.0
            
            return {
                "hits": hits,
                "misses": misses,
                "total": total,
                "hit_rate": hit_rate,
                "available": True
            }
        except Exception as e:
            logger.warning(f"[RESPONSE_CACHE] Stats error: {e}")
            return {"hits": 0, "misses": 0, "hit_rate": 0.0, "available": False, "error": str(e)}
    
    async def clear_response_cache(self) -> int:
        """
        Clear all cached OpenAI responses.
        
        Returns:
            Number of keys deleted
        """
        if not self.client:
            return 0
        
        try:
            keys = []
            async for key in self.client.scan_iter(match="openai_response:*"):
                keys.append(key)
            
            if keys:
                deleted = await self.client.delete(*keys)
                logger.info(f"[RESPONSE_CACHE] Cleared {deleted} cached responses")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"[RESPONSE_CACHE] Clear error: {e}")
            return 0

