"""
Test LightRAG query with the exact parameters the chatbot uses
"""
import sys
import json
import asyncio
import os

# Configure stdout for UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Add bank_chatbot to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bank_chatbot'))

from bank_chatbot.app.services.lightrag_client import LightRAGClient

async def test_query():
    """Test query with chatbot's exact parameters"""
    client = LightRAGClient()
    
    query = "How many Priority centers are there in Sylhet City?"
    
    print("=" * 60)
    print("Testing LightRAG Query (Chatbot Parameters)")
    print("=" * 60)
    print(f"Query: {query}")
    print()
    
    # Test 1: With "hybrid" mode (what chatbot uses)
    print("Test 1: mode='hybrid' (chatbot's current setting)")
    try:
        response = await client.query(
            query=query,
            knowledge_base="ebl_website",
            mode="hybrid",  # This is what the chatbot uses
            top_k=8,
            chunk_top_k=5,
            include_references=True,
            only_need_context=False,
            max_entity_tokens=2500,
            max_relation_tokens=3500,
            max_total_tokens=12000,
            enable_rerank=True
        )
        
        print(f"   [OK] Response received")
        print(f"   Response keys: {list(response.keys())}")
        
        if "response" in response:
            resp_text = response["response"]
            print(f"   Response length: {len(resp_text)} chars")
            print(f"   Response preview: {resp_text[:300]}...")
        else:
            print(f"   [WARN] No 'response' key in response")
            print(f"   Full response: {json.dumps(response, indent=2)[:500]}")
            
    except Exception as e:
        print(f"   [ERROR] Query failed: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 2: With "mix" mode (what works in direct test)
    print("Test 2: mode='mix' (what works in direct test)")
    try:
        response = await client.query(
            query=query,
            knowledge_base="ebl_website",
            mode="mix",  # This is what works
            top_k=8,
            chunk_top_k=5,
            include_references=True,
            only_need_context=False
        )
        
        print(f"   [OK] Response received")
        print(f"   Response keys: {list(response.keys())}")
        
        if "response" in response:
            resp_text = response["response"]
            print(f"   Response length: {len(resp_text)} chars")
            print(f"   Response preview: {resp_text[:300]}...")
        else:
            print(f"   [WARN] No 'response' key in response")
            print(f"   Full response: {json.dumps(response, indent=2)[:500]}")
            
    except Exception as e:
        print(f"   [ERROR] Query failed: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_query())






