"""
Fix failed documents in LightRAG
Check why documents failed and retry processing
"""

import requests
import json
from typing import Dict, List, Any

LIGHTRAG_URL = "http://localhost:9262"
API_KEY = "MyCustomLightRagKey456"

def get_documents(status: str = None) -> Dict[str, Any]:
    """Get list of documents from LightRAG"""
    url = f"{LIGHTRAG_URL}/documents"
    params = {}
    if status:
        params["status"] = status
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting documents: {e}")
        return {}


def get_document_details(doc_id: str) -> Dict[str, Any]:
    """Get details of a specific document"""
    url = f"{LIGHTRAG_URL}/documents/{doc_id}"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting document details: {e}")
        return {}


def delete_document(doc_id: str) -> bool:
    """Delete a failed document"""
    url = f"{LIGHTRAG_URL}/documents/{doc_id}"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.delete(url, headers=headers, timeout=30)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error deleting document: {e}")
        return False


def trigger_scan() -> bool:
    """Trigger document scanning/processing"""
    url = f"{LIGHTRAG_URL}/scan"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, timeout=30)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error triggering scan: {e}")
        return False


def main():
    """Main function to diagnose and fix failed documents"""
    print("=" * 70)
    print("LightRAG Failed Documents Diagnostic")
    print("=" * 70)
    
    # Get failed documents
    print("\n1. Checking failed documents...")
    failed_docs = get_documents(status="FAILED")
    
    if "documents" in failed_docs:
        failed_list = failed_docs["documents"]
        print(f"Found {len(failed_list)} failed documents")
        
        if len(failed_list) > 0:
            print("\n2. Document Details:")
            print("-" * 70)
            for doc in failed_list[:5]:  # Show first 5
                doc_id = doc.get("id", "unknown")
                summary = doc.get("summary", {})
                title = summary.get("title", "Unknown")
                status = doc.get("status", "Unknown")
                
                print(f"\nDocument ID: {doc_id}")
                print(f"  Title: {title}")
                print(f"  Status: {status}")
                
                # Get detailed error if available
                details = get_document_details(doc_id)
                if "error" in details:
                    print(f"  Error: {details['error']}")
                if "message" in details:
                    print(f"  Message: {details['message']}")
            
            print("\n" + "=" * 70)
            print("Recommended Actions:")
            print("=" * 70)
            print("\nOption 1: Delete failed documents and re-upload")
            print("  - Delete all failed documents")
            print("  - Re-upload the annual report (as single document, not split)")
            print("  - Trigger scan")
            
            print("\nOption 2: Check LightRAG logs")
            print("  docker logs LightRAG_New --tail 100")
            
            print("\nOption 3: Try uploading smaller chunks")
            print("  - Split large PDF into smaller parts")
            print("  - Upload each part separately")
            
            print("\n" + "=" * 70)
            print("Common Causes of Failed Documents:")
            print("=" * 70)
            print("1. Document too large (exceeds size limit)")
            print("2. PDF format issues (encrypted, corrupted, image-based)")
            print("3. Text extraction failed (OCR needed)")
            print("4. LightRAG processing timeout")
            print("5. Memory/resource constraints")
            
    else:
        print("No failed documents found or API response format unexpected")
        print(f"Response: {json.dumps(failed_docs, indent=2)[:500]}")


if __name__ == "__main__":
    main()

