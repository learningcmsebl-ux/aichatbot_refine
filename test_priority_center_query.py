"""
Test the exact query about priority center in Sylhet
"""
import sys
from connect_lightrag import LightRAGClient

# LightRAG configuration
BASE_URL = "http://localhost:9262"
API_KEY = "MyCustomLightRagKey456"
KNOWLEDGE_BASE = "ebl_website"

def test_query():
    """Test the exact query"""
    client = LightRAGClient(base_url=BASE_URL, api_key=API_KEY)
    
    # Test multiple query variations
    queries = [
        "tell me about priority center in sylhet",
        "How many Priority centers are there in Sylhet City?",
        "Priority Centers in Sylhet",
        "priority center sylhet"
    ]
    
    for query in queries:
        print("=" * 60)
        print(f"Testing Query: '{query}'")
        print("=" * 60)
        print()
        
        try:
            result = client.query(
                query=query,
                knowledge_base=KNOWLEDGE_BASE,
                mode="mix",
                top_k=5,
                chunk_top_k=5,
                include_references=True
            )
            
            response = result.get('response', '')
            references = result.get('references', [])
            
            print("Response:")
            print("-" * 60)
            print(response)
            print("-" * 60)
            print()
            
            print(f"References found: {len(references)}")
            if references:
                print("\nFirst reference preview:")
                ref_text = references[0].get('text', references[0].get('chunk', references[0].get('content', '')))
                if ref_text:
                    print(f"   {ref_text[:300]}...")
                else:
                    print("   [EMPTY REFERENCE]")
            print("\n" + "=" * 60 + "\n")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            print("\n" + "=" * 60 + "\n")
    
    return None
    
    print("=" * 60)
    print(f"Testing Query: '{query}'")
    print(f"Knowledge Base: {KNOWLEDGE_BASE}")
    print("=" * 60)
    print()
    
    try:
        result = client.query(
            query=query,
            knowledge_base=KNOWLEDGE_BASE,
            mode="mix",
            top_k=5,
            chunk_top_k=5,
            include_references=True
        )
        
        response = result.get('response', '')
        references = result.get('references', [])
        
        print("Response:")
        print("-" * 60)
        print(response)
        print("-" * 60)
        print()
        
        print(f"References found: {len(references)}")
        if references:
            print("\nReferences:")
            for i, ref in enumerate(references, 1):
                ref_text = ref.get('text', ref.get('chunk', ref.get('content', '')))
                print(f"\n{i}. Full reference:")
                print(f"   {ref_text}")
                print(f"   Metadata: {ref.get('metadata', {})}")
        
        return result
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_query()

