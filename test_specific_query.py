"""
Test the specific query directly with LightRAG
"""
import sys
import json

# Configure stdout for UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

from connect_lightrag import LightRAGClient

# LightRAG configuration
BASE_URL = "http://localhost:9262"
API_KEY = "MyCustomLightRagKey456"
KNOWLEDGE_BASE = "ebl_website"

def test_query():
    """Test the exact query"""
    client = LightRAGClient(base_url=BASE_URL, api_key=API_KEY)
    
    query = "How many Priority centers are there in Sylhet City?"
    
    print("=" * 60)
    print("Direct LightRAG Query Test")
    print("=" * 60)
    print(f"Query: {query}")
    print(f"Knowledge Base: {KNOWLEDGE_BASE}")
    print()
    
    # Test with working parameters
    try:
        result = client.query(
            query=query,
            knowledge_base=KNOWLEDGE_BASE,
            mode="mix",
            top_k=5,
            chunk_top_k=5,
            include_references=True,
            only_need_context=False
        )
        
        print("[OK] Query successful!")
        print()
        print("=" * 60)
        print("RESPONSE:")
        print("=" * 60)
        
        if "response" in result:
            response_text = result["response"]
            print(response_text)
            print()
            
            # Check if answer is present
            if "2 Priority" in response_text or "two Priority" in response_text.lower():
                print("[SUCCESS] Answer found: Information about 2 Priority Centers is present!")
            elif "Priority Center" in response_text or "Priority Centre" in response_text:
                print("[INFO] Priority Center information found, but number may not be explicit")
            else:
                print("[WARN] Priority Center information may not be clear in response")
        else:
            print("[ERROR] No 'response' key in result")
            print(f"Result keys: {list(result.keys())}")
            print(f"Full result: {json.dumps(result, indent=2)[:1000]}")
        
        print()
        print("=" * 60)
        print("REFERENCES:")
        print("=" * 60)
        
        if "references" in result:
            refs = result["references"]
            print(f"Found {len(refs)} reference(s):")
            for i, ref in enumerate(refs, 1):
                ref_text = ref.get('text', ref.get('chunk', ref.get('content', '')))
                ref_source = ref.get('source', ref.get('file_source', 'Unknown'))
                print(f"\n{i}. Source: {ref_source}")
                if ref_text:
                    print(f"   Text: {ref_text[:200]}...")
        else:
            print("No references found")
            
    except Exception as e:
        print(f"[ERROR] Query failed: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    test_query()






