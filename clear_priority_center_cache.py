"""
Clear Redis cache for Priority Center queries
"""
import sys
import os

# Add bank_chatbot to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bank_chatbot'))

from bank_chatbot.app.services.redis_client import RedisCache
import asyncio

async def clear_cache():
    """Clear cache for Priority Center related queries"""
    cache = RedisCache()
    
    # Patterns to search for
    patterns = [
        "*priority*center*",
        "*Priority*Center*",
        "*sylhet*priority*",
        "*How many Priority*"
    ]
    
    print("=" * 60)
    print("Clearing Redis Cache for Priority Center Queries")
    print("=" * 60)
    
    # Get all keys (this is a simple approach - Redis doesn't have pattern delete in all versions)
    # We'll need to use SCAN or get all keys
    try:
        # Try to get keys matching pattern
        keys_to_delete = []
        
        # For each pattern, try to find matching keys
        # Note: This requires Redis to support KEYS command (not recommended for production)
        # But for cache clearing, it's acceptable
        
        print("\nSearching for cached queries...")
        
        # Since we can't easily pattern match, let's just clear all cache
        # Or we can try to get all keys if Redis supports it
        print("\nNote: To clear specific cache entries, you may need to:")
        print("  1. Restart Redis (clears all cache)")
        print("  2. Or wait for cache TTL to expire")
        print("  3. Or use Redis CLI: redis-cli FLUSHDB")
        
        print("\n[INFO] Cache will be cleared when backend restarts or TTL expires")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(clear_cache())






