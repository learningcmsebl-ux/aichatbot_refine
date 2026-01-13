"""
Test the complete cache workflow to verify caching is working
"""
import asyncio
import sys
import os

# Add bank_chatbot to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bank_chatbot'))

from app.database.redis_client import init_redis, RedisCache, get_cache_key
from app.core.config import settings

async def test_cache_workflow():
    print("Testing Cache Workflow...")
    print("=" * 50)
    
    # Initialize Redis
    await init_redis()
    cache = RedisCache()
    
    if not cache.client:
        print("✗ Redis client is not available - cannot test")
        return
    
    print("✓ Redis client initialized")
    print()
    
    # Simulate a query
    test_query = "tell me about EBL milestones"
    test_kb = "ebl_website"
    cache_key = get_cache_key(test_query, test_kb)
    
    print(f"Test Query: {test_query}")
    print(f"Knowledge Base: {test_kb}")
    print(f"Cache Key: {cache_key}")
    print()
    
    # Step 1: Check cache (should be MISS)
    print("Step 1: Checking cache (should be MISS)...")
    cached = await cache.get(cache_key)
    if cached:
        print("  ✗ Unexpected: Found cached value (should be empty)")
    else:
        print("  ✓ Cache MISS (expected for first query)")
    print()
    
    # Step 2: Simulate storing a response
    print("Step 2: Storing response in cache...")
    test_response = {
        "response": "EBL has achieved many milestones...",
        "chunks": [{"text": "Sample chunk"}],
        "entities": []
    }
    result = await cache.set(cache_key, test_response, ttl=60)
    if result:
        print("  ✓ Response stored in cache")
    else:
        print("  ✗ Failed to store response")
        return
    print()
    
    # Step 3: Check cache again (should be HIT)
    print("Step 3: Checking cache again (should be HIT)...")
    cached = await cache.get(cache_key)
    if cached:
        print("  ✓ Cache HIT - Retrieved cached value")
        print(f"  Response preview: {str(cached.get('response', ''))[:50]}...")
    else:
        print("  ✗ Cache MISS - Value not found (caching failed)")
    print()
    
    # Step 4: Verify in Redis directly
    print("Step 4: Verifying in Redis directly...")
    try:
        keys = []
        async for key in cache.client.scan_iter(match="lightrag:*"):
            keys.append(key)
        
        if cache_key in keys:
            print(f"  ✓ Key found in Redis: {cache_key}")
            ttl = await cache.client.ttl(cache_key)
            print(f"  TTL: {ttl} seconds")
        else:
            print(f"  ✗ Key not found in Redis")
            print(f"  Available keys: {keys}")
    except Exception as e:
        print(f"  ✗ Error checking Redis: {e}")
    print()
    
    # Step 5: Cleanup
    print("Step 5: Cleaning up test data...")
    await cache.delete(cache_key)
    print("  ✓ Test data cleaned up")
    print()
    
    print("=" * 50)
    print("Cache workflow test completed!")
    print()
    print("If all steps passed, caching is working correctly.")
    print("If the chatbot still shows no cache, check:")
    print("  1. Is the chatbot server running?")
    print("  2. Did the server initialize Redis? (check startup logs)")
    print("  3. Are queries going through LightRAG? (check routing logic)")

if __name__ == "__main__":
    asyncio.run(test_cache_workflow())

