"""
Test Redis cache functionality and check if cache hits are working
"""

import asyncio
import sys
import os

# Add bank_chatbot to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bank_chatbot'))

from app.database.redis_client import RedisCache, get_cache_key, init_redis, close_redis
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_redis_cache():
    """Test Redis cache functionality"""
    print("=" * 70)
    print("Redis Cache Test")
    print("=" * 70)
    print()
    
    # Initialize Redis
    print("1. Initializing Redis connection...")
    await init_redis()
    
    # Create cache instance
    cache = RedisCache()
    
    if not cache.client:
        print("❌ Redis client is None - Redis is not available!")
        print("   Check if Redis is running and configuration is correct.")
        return
    
    # Test connection
    print("2. Testing Redis connection...")
    try:
        await cache.client.ping()
        print("✅ Redis connection successful!")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return
    
    print()
    print("3. Testing cache operations...")
    
    # Test query
    test_query = "What is the audit committee?"
    test_kb = "ebl_website"
    
    cache_key = get_cache_key(test_query, test_kb)
    print(f"   Test Query: '{test_query}'")
    print(f"   Knowledge Base: {test_kb}")
    print(f"   Cache Key: {cache_key}")
    print()
    
    # Check if key exists
    print("4. Checking for existing cache entries...")
    try:
        existing_value = await cache.get(cache_key)
        if existing_value:
            print(f"✅ Cache HIT! Found cached value for this query.")
            print(f"   Cached data keys: {list(existing_value.keys()) if isinstance(existing_value, dict) else 'N/A'}")
        else:
            print(f"❌ Cache MISS - No cached value found for this query.")
    except Exception as e:
        print(f"❌ Error checking cache: {e}")
    
    print()
    print("5. Testing cache set operation...")
    test_data = {
        "response": "Test response",
        "entities": [],
        "chunks": []
    }
    
    try:
        result = await cache.set(cache_key, test_data, ttl=3600)
        if result:
            print("✅ Successfully set test cache entry")
        else:
            print("❌ Failed to set cache entry")
    except Exception as e:
        print(f"❌ Error setting cache: {e}")
    
    print()
    print("6. Testing cache get operation...")
    try:
        retrieved = await cache.get(cache_key)
        if retrieved:
            print("✅ Successfully retrieved cached value")
            print(f"   Retrieved data: {retrieved.get('response', 'N/A')}")
        else:
            print("❌ Failed to retrieve cached value")
    except Exception as e:
        print(f"❌ Error getting cache: {e}")
    
    print()
    print("7. Checking all cache keys...")
    try:
        keys = []
        async for key in cache.client.scan_iter(match="lightrag:*"):
            keys.append(key)
        
        print(f"   Found {len(keys)} cache entries")
        if keys:
            print("   Sample keys:")
            for key in keys[:5]:
                print(f"     - {key}")
            if len(keys) > 5:
                print(f"     ... and {len(keys) - 5} more")
        else:
            print("   No cache entries found")
    except Exception as e:
        print(f"❌ Error scanning cache keys: {e}")
    
    print()
    print("8. Testing cache TTL...")
    try:
        ttl = await cache.client.ttl(cache_key)
        if ttl > 0:
            print(f"✅ Cache entry has TTL: {ttl} seconds ({ttl/3600:.2f} hours)")
        elif ttl == -1:
            print("⚠️  Cache entry has no expiration (persistent)")
        elif ttl == -2:
            print("❌ Cache entry does not exist")
    except Exception as e:
        print(f"❌ Error checking TTL: {e}")
    
    print()
    print("9. Redis Configuration:")
    print(f"   Host: {settings.REDIS_HOST}")
    print(f"   Port: {settings.REDIS_PORT}")
    print(f"   DB: {settings.REDIS_DB}")
    print(f"   Cache TTL: {settings.REDIS_CACHE_TTL} seconds ({settings.REDIS_CACHE_TTL/3600:.2f} hours)")
    
    # Clean up test entry
    print()
    print("10. Cleaning up test entry...")
    try:
        await cache.delete(cache_key)
        print("✅ Test cache entry deleted")
    except Exception as e:
        print(f"⚠️  Could not delete test entry: {e}")
    
    # Close Redis
    await close_redis()
    
    print()
    print("=" * 70)
    print("Test Complete")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_redis_cache())

