"""
Script to check if Priority Center information exists in LightRAG
"""
import sys
import json
import os

# Configure stdout for UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

from connect_lightrag import LightRAGClient

# LightRAG configuration
BASE_URL = "http://localhost:9262"
API_KEY = "MyCustomLightRagKey456"
KNOWLEDGE_BASE = "ebl_website"  # Default knowledge base

def check_priority_centers():
    """Check if Priority Center information exists in LightRAG"""
    client = LightRAGClient(base_url=BASE_URL, api_key=API_KEY)
    
    print("=" * 60)
    print("Checking Priority Center Information in LightRAG")
    print("=" * 60)
    print(f"Knowledge Base: {KNOWLEDGE_BASE}")
    print(f"LightRAG URL: {BASE_URL}")
    print()
    
    # Step 1: Health check
    print("1. Checking LightRAG connection...")
    try:
        health = client.health_check()
        print(f"   [OK] LightRAG Health: {health.get('status', 'unknown')}")
        if health.get("status") != "ok":
            print(f"   [WARN] Warning: {health}")
    except Exception as e:
        print(f"   [ERROR] Error connecting to LightRAG: {e}")
        return False
    print()
    
    # Step 2: Check documents
    print("2. Checking uploaded documents...")
    try:
        documents = client.get_documents(page=1, page_size=100)
        if documents:
            total = documents.get('total', 0)
            items = documents.get('items', [])
            print(f"   [OK] Found {total} total documents")
            
            # Search for Priority Center related documents
            priority_docs = []
            for doc in items:
                file_source = doc.get('file_source', '')
                if 'priority' in file_source.lower() or 'center' in file_source.lower():
                    priority_docs.append(doc)
            
            if priority_docs:
                print(f"   [OK] Found {len(priority_docs)} Priority Center related document(s):")
                for doc in priority_docs:
                    print(f"      - {doc.get('file_source', 'Unknown')} (Status: {doc.get('status', 'Unknown')})")
            else:
                print("   [WARN] No Priority Center specific documents found")
        else:
            print("   [WARN] Could not retrieve documents list")
    except Exception as e:
        print(f"   [WARN] Could not check documents: {e}")
    print()
    
    # Step 3: Query for Priority Centers
    test_queries = [
        "How many Priority centers are there in Sylhet City?",
        "Priority Centers in Sylhet",
        "EBL Priority Centers",
        "Priority Banking centers"
    ]
    
    print("3. Testing queries for Priority Center information...")
    print()
    
    for i, query in enumerate(test_queries, 1):
        print(f"   Query {i}: {query}")
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
            
            if response and len(response.strip()) > 0:
                print(f"      [OK] Response received ({len(response)} chars)")
                # Show first 200 chars of response
                preview = response[:200].replace('\n', ' ')
                if len(response) > 200:
                    preview += "..."
                print(f"      Preview: {preview}")
                
                if references:
                    print(f"      [OK] Found {len(references)} reference(s)")
                    for ref in references[:3]:  # Show first 3 references
                        ref_text = ref.get('text', ref.get('chunk', ''))[:100]
                        print(f"         - {ref_text}...")
                else:
                    print(f"      [WARN] No references found")
            else:
                print(f"      [ERROR] No response or empty response")
                print(f"      Full result: {json.dumps(result, indent=2)[:300]}")
        except Exception as e:
            print(f"      [ERROR] Query failed: {e}")
        print()
    
    # Step 4: Query with detailed data
    print("4. Getting detailed query data...")
    try:
        detailed_result = client.query_data(
            query="Priority Centers in Sylhet City",
            knowledge_base=KNOWLEDGE_BASE,
            mode="mix",
            top_k=5,
            chunk_top_k=5
        )
        
        entities = detailed_result.get('entities', [])
        relationships = detailed_result.get('relationships', [])
        chunks = detailed_result.get('chunks', [])
        
        print(f"   Entities found: {len(entities)}")
        if entities:
            print("   Sample entities:")
            for entity in entities[:5]:
                print(f"      - {entity.get('name', 'Unknown')}: {entity.get('description', '')[:80]}...")
        
        print(f"   Relationships found: {len(relationships)}")
        if relationships:
            print("   Sample relationships:")
            for rel in relationships[:3]:
                print(f"      - {rel}")
        
        print(f"   Chunks found: {len(chunks)}")
        if chunks:
            print("   Sample chunks:")
            for chunk in chunks[:2]:
                chunk_text = chunk.get('text', chunk.get('content', ''))[:150]
                print(f"      - {chunk_text}...")
    except Exception as e:
        print(f"   [ERROR] Detailed query failed: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("Check completed!")
    print("=" * 60)

if __name__ == "__main__":
    check_priority_centers()

