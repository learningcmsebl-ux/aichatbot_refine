"""
Test Redis connection for the chatbot
"""
import asyncio
import sys
import os

# Add bank_chatbot to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bank_chatbot'))

from app.database.redis_client import init_redis, RedisCache
from app.core.config import settings

async def test_redis():
    print("Testing Redis connection...")
    print(f"Redis Host: {settings.REDIS_HOST}")
    print(f"Redis Port: {settings.REDIS_PORT}")
    print(f"Redis DB: {settings.REDIS_DB}")
    print(f"Redis Password: {'***' if settings.REDIS_PASSWORD else '(none)'}")
    print()
    
    try:
        await init_redis()
        print("✓ Redis initialization completed")
        
        # Test cache operations
        cache = RedisCache()
        if cache.client:
            print("✓ Redis client is available")
            
            # Test set
            result = await cache.set("test_key", "test_value", ttl=10)
            if result:
                print("✓ Redis SET operation successful")
            else:
                print("✗ Redis SET operation failed")
            
            # Test get
            value = await cache.get("test_key")
            if value == "test_value":
                print("✓ Redis GET operation successful")
                print(f"  Retrieved value: {value}")
            else:
                print(f"✗ Redis GET operation failed. Got: {value}")
            
            # Test ping
            try:
                await cache.client.ping()
                print("✓ Redis PING successful")
            except Exception as e:
                print(f"✗ Redis PING failed: {e}")
        else:
            print("✗ Redis client is NOT available (None)")
            print("  This means Redis initialization failed silently")
    except Exception as e:
        print(f"✗ Error during Redis test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_redis())
