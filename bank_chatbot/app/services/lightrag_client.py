"""
LightRAG client for querying the RAG system.
"""

import httpx
import logging
from typing import Optional, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class LightRAGClient:
    """Client for connecting to LightRAG API"""
    
    def __init__(self):
        self.base_url = settings.LIGHTRAG_URL.rstrip('/')
        self.api_key = settings.LIGHTRAG_API_KEY
        self.knowledge_base = settings.LIGHTRAG_KNOWLEDGE_BASE
        self.timeout = settings.LIGHTRAG_TIMEOUT
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }
        self.client = httpx.AsyncClient(timeout=self.timeout)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if LightRAG API is healthy"""
        try:
            response = await self.client.get(
                f"{self.base_url}/health",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"LightRAG health check failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def query(
        self,
        query: str,
        knowledge_base: Optional[str] = None,
        mode: str = "mix",
        top_k: int = 5,
        chunk_top_k: int = 10,
        include_references: bool = True,
        only_need_context: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Query the LightRAG service
        
        Args:
            query: The query/question to ask
            knowledge_base: Knowledge base name (defaults to configured)
            mode: Query mode (mix, kg, chunk)
            top_k: Number of top entities from knowledge graph
            chunk_top_k: Number of top document chunks
            include_references: Include source references
            only_need_context: Return only context (not full response)
            **kwargs: Additional parameters
        
        Returns:
            Response from LightRAG API
        """
        kb = knowledge_base or self.knowledge_base
        
        data = {
            "query": query,
            "mode": mode,
            "top_k": top_k,
            "chunk_top_k": chunk_top_k,
            "include_references": include_references,
            "only_need_context": only_need_context,
            **kwargs
        }
        
        # Add knowledge base if specified
        if kb:
            data["knowledge_base"] = kb
        
        try:
            response = await self.client.post(
                f"{self.base_url}/query",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"LightRAG HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"LightRAG query error: {e}")
            raise
    
    async def query_data(
        self,
        query: str,
        knowledge_base: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Query LightRAG and get detailed data (entities, relationships, chunks)
        
        Args:
            query: The query/question to ask
            knowledge_base: Knowledge base name
            **kwargs: Additional parameters
        
        Returns:
            Detailed response with entities, relationships, chunks, and references
        """
        kb = knowledge_base or self.knowledge_base
        
        data = {
            "query": query,
            **kwargs
        }
        
        if kb:
            data["knowledge_base"] = kb
        
        try:
            response = await self.client.post(
                f"{self.base_url}/query/data",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"LightRAG query_data error: {e}")
            raise
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

