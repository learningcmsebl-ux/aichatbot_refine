"""
Check Redis cache for existing entries and verify cache hit functionality
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

async def check_cache_entries():
    """Check existing cache entries and their status"""
    print("=" * 70)
    print("Redis Cache Status Check")
    print("=" * 70)
    print()
    
    # Initialize Redis
    await init_redis()
    cache = RedisCache()
    
    if not cache.client:
        print("❌ Redis is not available!")
        return
    
    try:
        await cache.client.ping()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return
    
    print()
    print("Scanning for cache entries...")
    
    # Find all cache entries
    cache_entries = []
    try:
        async for key in cache.client.scan_iter(match="lightrag:*"):
            cache_entries.append(key)
    except Exception as e:
        print(f"❌ Error scanning cache: {e}")
        return
    
    print(f"Found {len(cache_entries)} cache entries")
    print()
    
    if cache_entries:
        print("Cache Entries:")
        print("-" * 70)
        
        for i, key in enumerate(cache_entries[:20], 1):  # Show first 20
            try:
                # Get TTL
                ttl = await cache.client.ttl(key)
                
                # Get value size
                value = await cache.client.get(key)
                size = len(value) if value else 0
                
                # Parse key to extract info
                parts = key.split(":")
                kb = parts[1] if len(parts) > 1 else "unknown"
                query_hash = parts[-1] if len(parts) > 2 else "unknown"
                
                ttl_str = f"{ttl}s" if ttl > 0 else ("persistent" if ttl == -1 else "expired")
                
                print(f"{i}. {key}")
                print(f"   KB: {kb} | Hash: {query_hash[:16]}... | TTL: {ttl_str} | Size: {size} bytes")
                
                # Try to get cached data
                cached_data = await cache.get(key)
                if cached_data:
                    if isinstance(cached_data, dict):
                        keys_in_data = list(cached_data.keys())
                        print(f"   Data keys: {keys_in_data}")
            except Exception as e:
                print(f"   ⚠️  Error reading entry: {e}")
        
        if len(cache_entries) > 20:
            print(f"\n... and {len(cache_entries) - 20} more entries")
    else:
        print("⚠️  No cache entries found!")
        print("   This could mean:")
        print("   - No queries have been cached yet")
        print("   - Cache entries have expired")
        print("   - Cache is not being used")
    
    print()
    print("=" * 70)
    print("Cache Statistics:")
    print("=" * 70)
    
    # Group by knowledge base
    kb_counts = {}
    for key in cache_entries:
        parts = key.split(":")
        if len(parts) > 1:
            kb = parts[1]
            kb_counts[kb] = kb_counts.get(kb, 0) + 1
    
    if kb_counts:
        print("\nEntries by Knowledge Base:")
        for kb, count in sorted(kb_counts.items()):
            print(f"  {kb}: {count} entries")
    
    # Check Redis memory
    try:
        info = await cache.client.info("memory")
        used_memory = info.get('used_memory_human', 'unknown')
        print(f"\nRedis Memory Usage: {used_memory}")
    except Exception as e:
        print(f"\n⚠️  Could not get memory info: {e}")
    
    await close_redis()
    print()
    print("=" * 70)
    print("Check Complete")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(check_cache_entries())

