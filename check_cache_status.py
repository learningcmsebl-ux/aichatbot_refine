"""
Check Redis cache status for LightRAG queries
"""
import asyncio
import sys
import os

# Add bank_chatbot to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bank_chatbot'))

from app.database.redis_client import init_redis, RedisCache, get_cache_key
from app.core.config import settings

async def check_cache():
    print("Checking Redis Cache Status...")
    print("=" * 50)
    
    # Initialize Redis first
    await init_redis()
    
    cache = RedisCache()
    
    if not cache.client:
        print("✗ Redis client is not available")
        print("  Caching is NOT working")
        return
    
    print("✓ Redis client is available")
    print()
    
    # Check for cached keys
    try:
        # Get all lightrag keys
        keys = []
        async for key in cache.client.scan_iter(match="lightrag:*"):
            keys.append(key)
        
        print(f"Found {len(keys)} cached entries")
        print()
        
        if keys:
            print("Sample cached keys:")
            for i, key in enumerate(keys[:10], 1):
                # Get TTL
                ttl = await cache.client.ttl(key)
                print(f"  {i}. {key}")
                print(f"     TTL: {ttl} seconds ({ttl // 60} minutes)")
                
                # Get a sample value (first 100 chars)
                try:
                    value = await cache.client.get(key)
                    if value:
                        import json
                        data = json.loads(value)
                        if isinstance(data, dict):
                            if 'response' in data:
                                preview = str(data['response'])[:100]
                            elif 'chunks' in data:
                                preview = f"Chunks: {len(data.get('chunks', []))}"
                            else:
                                preview = str(data)[:100]
                        else:
                            preview = str(data)[:100]
                        print(f"     Preview: {preview}...")
                except:
                    pass
                print()
            
            if len(keys) > 10:
                print(f"  ... and {len(keys) - 10} more entries")
        else:
            print("⚠ No cached entries found")
            print("  This could mean:")
            print("    - No queries have been made yet")
            print("    - Cache TTL has expired")
            print("    - Cache was cleared")
            print()
            print("  To test caching:")
            print("    1. Make a query through the chatbot")
            print("    2. Make the same query again")
            print("    3. Check logs for 'Cache HIT' message")
        
        print()
        print("Cache Configuration:")
        print(f"  TTL: {cache.ttl} seconds ({cache.ttl // 60} minutes)")
        print(f"  Redis Host: {settings.REDIS_HOST}")
        print(f"  Redis Port: {settings.REDIS_PORT}")
        print(f"  Redis DB: {settings.REDIS_DB}")
        
    except Exception as e:
        print(f"✗ Error checking cache: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_cache())

