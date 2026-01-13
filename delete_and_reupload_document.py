"""
Delete failed document and re-upload it
This ensures the document is processed with the correct embedding dimensions
"""

import requests
import json
from connect_lightrag import LightRAGClient

LIGHTRAG_URL = "http://localhost:9262"
API_KEY = "MyCustomLightRagKey456"

def delete_document(doc_id: str) -> bool:
    """Delete a document from LightRAG"""
    url = f"{LIGHTRAG_URL}/documents/{doc_id}"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.delete(url, headers=headers, timeout=30)
        response.raise_for_status()
        print(f"✓ Deleted document: {doc_id}")
        return True
    except Exception as e:
        print(f"✗ Failed to delete document: {e}")
        return False


def get_documents() -> dict:
    """Get list of documents"""
    url = f"{LIGHTRAG_URL}/documents"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting documents: {e}")
        return {}


def main():
    """Delete failed documents and show re-upload instructions"""
    print("=" * 70)
    print("Delete Failed Documents")
    print("=" * 70)
    print()
    
    # Get all documents
    print("Fetching documents...")
    docs_data = get_documents()
    
    if "statuses" in docs_data:
        failed_docs = docs_data["statuses"].get("failed", [])
        
        if not failed_docs:
            print("No failed documents found.")
            return
        
        print(f"Found {len(failed_docs)} failed document(s)")
        print()
        
        # Delete each failed document
        for doc in failed_docs:
            doc_id = doc.get("id")
            summary = doc.get("content_summary", "Unknown")
            if isinstance(summary, dict):
                summary = summary.get("title", "Unknown")
            elif isinstance(summary, str):
                summary = summary[:50] + "..." if len(summary) > 50 else summary
            
            print(f"Deleting: {summary}")
            print(f"  ID: {doc_id}")
            
            if delete_document(doc_id):
                print(f"  ✓ Deleted successfully")
            else:
                print(f"  ✗ Failed to delete")
            print()
        
        print("=" * 70)
        print("Documents Deleted")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. Re-upload the document:")
        print("   python upload_to_knowledge_base.py scraped_text/EBL_Management_Committee.txt --knowledge-base ebl_website")
        print()
        print("2. Trigger scan in LightRAG web UI")
        print()
        print("3. Document should process successfully now!")
        print()
    else:
        print("Unexpected response format:")
        print(json.dumps(docs_data, indent=2)[:500])


if __name__ == "__main__":
    main()

