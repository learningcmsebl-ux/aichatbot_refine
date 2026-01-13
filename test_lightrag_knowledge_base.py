"""
Test LightRAG knowledge base access
Check if knowledge bases exist and can be queried
"""

import asyncio
import httpx
from connect_lightrag import LightRAGClient

async def test_knowledge_bases():
    """Test if knowledge bases exist and can be queried"""
    
    client = LightRAGClient(
        base_url="http://localhost:9262",
        api_key="MyCustomLightRagKey456"
    )
    
    # Test health
    print("=" * 70)
    print("Testing LightRAG Connection")
    print("=" * 70)
    
    health = client.health_check()
    print(f"Health Status: {health.get('status', 'unknown')}")
    print()
    
    # Test knowledge bases
    knowledge_bases = [
        "ebl_financial_reports",
        "ebl_user_documents",
        "ebl_website",
        "default"
    ]
    
    print("=" * 70)
    print("Testing Knowledge Bases")
    print("=" * 70)
    
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        for kb in knowledge_bases:
            print(f"\nTesting knowledge base: {kb}")
            print("-" * 70)
            
            try:
                # Try to query the knowledge base
                data = {
                    "query": "test query",
                    "knowledge_base": kb,
                    "mode": "mix",
                    "top_k": 1,
                    "chunk_top_k": 1,
                    "include_references": False,
                    "only_need_context": True
                }
                
                response = await http_client.post(
                    "http://localhost:9262/query",
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key": "MyCustomLightRagKey456"
                    },
                    json=data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"  ✓ Knowledge base '{kb}' exists and is accessible")
                    if "entities" in result or "chunks" in result:
                        entities_count = len(result.get("entities", []))
                        chunks_count = len(result.get("chunks", []))
                        print(f"    - Entities: {entities_count}")
                        print(f"    - Chunks: {chunks_count}")
                elif response.status_code == 404:
                    print(f"  ✗ Knowledge base '{kb}' not found (404)")
                else:
                    print(f"  ✗ Error {response.status_code}: {response.text[:200]}")
                    
            except httpx.RequestError as e:
                print(f"  ✗ Connection error: {e}")
            except Exception as e:
                print(f"  ✗ Error: {e}")
    
    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)
    
    print("\nRecommendations:")
    print("1. If 'ebl_financial_reports' doesn't exist, upload reports first:")
    print("   python download_and_upload_financial_reports.py")
    print("2. Check LightRAG logs for more details:")
    print("   docker logs LightRAG_New")
    print("3. Verify LightRAG API endpoint is correct:")
    print("   http://localhost:9262/query")


if __name__ == "__main__":
    asyncio.run(test_knowledge_bases())

