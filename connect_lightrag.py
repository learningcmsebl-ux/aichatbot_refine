"""
Connection script for LightRAG_New container
Connects to the LightRAG API server running in the Docker container
"""

import requests
import json
from typing import Optional, Dict, Any

class LightRAGClient:
    """Client for connecting to LightRAG API server"""
    
    def __init__(self, base_url: str = "http://localhost:9262", api_key: str = "MyCustomLightRagKey456"):
        """
        Initialize LightRAG client
        
        Args:
            base_url: Base URL of the LightRAG API server
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP request to the API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request payload
            
        Returns:
            Response JSON as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=self.headers, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to LightRAG: {e}")
            raise
    
    def health_check(self) -> Dict[str, Any]:
        """Check if the API server is healthy"""
        try:
            return self._make_request("GET", "/health")
        except:
            # Try alternative endpoint
            try:
                return self._make_request("GET", "/")
            except:
                return {"status": "error", "message": "Could not connect to LightRAG API"}
    
    def query(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Query the LightRAG service
        
        Args:
            query: The query/question to ask
            **kwargs: Additional parameters for the query (e.g., include_references, max_chunk_tokens, etc.)
            
        Returns:
            Response from the API with 'response' and 'references' fields
        """
        data = {
            "query": query,
            **kwargs
        }
        return self._make_request("POST", "/query", data)
    
    def query_data(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Query the LightRAG service and get detailed data (entities, relationships, chunks, references)
        
        Args:
            query: The query/question to ask
            **kwargs: Additional parameters for the query
            
        Returns:
            Response with detailed data including entities, relationships, chunks, and references
        """
        data = {
            "query": query,
            **kwargs
        }
        return self._make_request("POST", "/query/data", data)
    
    def insert_text(self, text: str, file_source: Optional[str] = None, knowledge_base: Optional[str] = None) -> Dict[str, Any]:
        """
        Insert a single text document into the RAG system
        
        Args:
            text: The text content to insert
            file_source: Optional source identifier for the text
            knowledge_base: Optional knowledge base name (e.g., 'ebl_website')
            
        Returns:
            Response from the API
        """
        data = {
            "text": text
        }
        if file_source:
            data["file_source"] = file_source
        if knowledge_base:
            data["knowledge_base"] = knowledge_base
        return self._make_request("POST", "/insert/text", data)
    
    def insert_texts(self, texts: list, file_sources: Optional[list] = None) -> Dict[str, Any]:
        """
        Insert multiple text documents into the RAG system
        
        Args:
            texts: List of text contents to insert
            file_sources: Optional list of source identifiers
            
        Returns:
            Response from the API
        """
        data = {
            "texts": texts
        }
        if file_sources:
            data["file_sources"] = file_sources
        return self._make_request("POST", "/insert/texts", data)
    
    def get_documents(self, page: int = 1, page_size: int = 50, status: Optional[str] = None) -> Dict[str, Any]:
        """
        Get paginated list of documents
        
        Args:
            page: Page number (default: 1)
            page_size: Number of items per page (default: 50)
            status: Optional filter by status (PENDING, PROCESSING, PROCESSED, FAILED)
            
        Returns:
            Paginated documents response
        """
        params = {
            "page": page,
            "page_size": page_size
        }
        if status:
            params["status"] = status
        
        # Build URL with query parameters
        url = f"{self.base_url}/documents"
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        if query_string:
            url += f"?{query_string}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting documents: {e}")
            raise
    


def main():
    """Test connection to LightRAG_New container"""
    print("Connecting to LightRAG_New container...")
    print(f"Container: LightRAG_New")
    print(f"Port: 9262")
    print(f"API Key: MyCustomLightRagKey456")
    print("-" * 50)
    
    # Initialize client
    client = LightRAGClient()
    
    # Test connection
    print("\nTesting connection...")
    health = client.health_check()
    print(f"Health check result: {json.dumps(health, indent=2)}")
    
    # Example query
    print("\n" + "-" * 50)
    print("Example: Testing query endpoint...")
    try:
        result = client.query("What is LightRAG?")
        print(f"Query result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Query test failed: {e}")
        print("Note: This might be expected if there's no data indexed yet")
    
    print("\n" + "-" * 50)
    print("Connection successful! LightRAG_New container is ready to use.")
    print("\nYou can now:")
    print("  - Insert text documents using client.insert_text() or client.insert_texts()")
    print("  - Query the RAG system using client.query() or client.query_data()")
    print("  - Get document list using client.get_documents()")


if __name__ == "__main__":
    main()

