"""
Test with exact parameters that worked in direct test
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

async def test_exact_params():
    """Test with exact parameters that worked in direct test"""
    client = LightRAGClient()
    
    query = "How many Priority centers are there in Sylhet City?"
    
    print("=" * 60)
    print("Testing with EXACT parameters from working direct test")
    print("=" * 60)
    print(f"Query: {query}")
    print()
    
    # Test with exact parameters from check_priority_centers_in_lightrag.py
    print("Test: mode='mix', top_k=5, chunk_top_k=5 (exact working params)")
    try:
        response = await client.query(
            query=query,
            knowledge_base="ebl_website",
            mode="mix",
            top_k=5,
            chunk_top_k=5,
            include_references=True,
            only_need_context=False  # Changed from True to False
        )
        
        print(f"   [OK] Response received")
        print(f"   Response keys: {list(response.keys())}")
        
        if "response" in response:
            resp_text = response["response"]
            print(f"   Response length: {len(resp_text)} chars")
            print(f"   Full response:")
            print(f"   {resp_text}")
            
            if "2 Priority Centers" in resp_text or "2 Priority" in resp_text:
                print(f"   [SUCCESS] Found the answer!")
            else:
                print(f"   [WARN] Answer not found in response")
        else:
            print(f"   [WARN] No 'response' key in response")
            print(f"   Full response: {json.dumps(response, indent=2)}")
            
        if "references" in response:
            refs = response["references"]
            print(f"   References: {len(refs)} found")
            for i, ref in enumerate(refs[:3], 1):
                ref_text = ref.get('text', ref.get('chunk', ''))[:150]
                print(f"      {i}. {ref_text}...")
            
    except Exception as e:
        print(f"   [ERROR] Query failed: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    
    # Test with only_need_context=True
    print("Test 2: with only_need_context=True")
    try:
        response = await client.query(
            query=query,
            knowledge_base="ebl_website",
            mode="mix",
            top_k=5,
            chunk_top_k=5,
            include_references=True,
            only_need_context=True  # This might be the issue
        )
        
        print(f"   [OK] Response received")
        if "response" in response:
            resp_text = response["response"]
            print(f"   Response length: {len(resp_text)} chars")
            print(f"   Response: {resp_text[:300]}...")
        else:
            print(f"   Full response: {json.dumps(response, indent=2)[:500]}")
            
    except Exception as e:
        print(f"   [ERROR] Query failed: {e}")
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_exact_params())






