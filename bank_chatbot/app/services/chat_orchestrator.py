"""
Chat Orchestrator - Coordinates all components for chat processing.
"""

import uuid
import logging
from typing import Optional, AsyncGenerator, List, Dict, Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.database.postgres import PostgresChatMemory, get_db
from app.database.redis_client import RedisCache, get_cache_key
from app.services.lightrag_client import LightRAGClient

logger = logging.getLogger(__name__)


class ChatOrchestrator:
    """Orchestrates chat processing with PostgreSQL, Redis, and LightRAG"""
    
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.lightrag_client = LightRAGClient()
        self.redis_cache = RedisCache()
        self.system_message = self._get_system_message()
    
    def _get_system_message(self) -> str:
        """Get system message for the chatbot"""
        return """You are a helpful and professional banking assistant for a financial institution.
Your role is to assist customers with banking-related queries, product information, account services, and general banking questions.

Guidelines:
1. Always be professional, friendly, and helpful
2. Use the provided context from the knowledge base to answer questions accurately
3. If information is not available in the context, politely inform the user
4. For banking queries, always use the provided context from LightRAG
5. Never make up specific numbers, rates, or product details
6. If asked about products, services, or policies, refer to the knowledge base context
7. For general greetings or small talk, respond naturally without requiring context

When responding:
- Be concise but thorough
- Use clear, simple language
- Structure product information clearly
- Always prioritize accuracy over speed"""
    
    def _is_small_talk(self, query: str) -> bool:
        """Detect if query is small talk (greetings, thanks, etc.)"""
        query_lower = query.lower().strip()
        
        # Banking keywords override - never treat as small talk
        banking_keywords = [
            "loan", "card", "account", "balance", "deposit", "withdrawal",
            "interest", "rate", "fee", "service", "product", "banking",
            "credit", "debit", "transaction", "statement", "minimum", "maximum"
        ]
        
        if any(keyword in query_lower for keyword in banking_keywords):
            return False
        
        # Small talk patterns
        small_talk_patterns = [
            "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
            "how are you", "how's it going", "what's up",
            "thanks", "thank you", "appreciate it",
            "bye", "goodbye", "see you", "farewell",
            "what are you", "who are you", "what can you do"
        ]
        
        return any(pattern in query_lower for pattern in small_talk_patterns)
    
    def _format_lightrag_context(self, lightrag_response: Dict[str, Any]) -> str:
        """Format LightRAG response into context string"""
        context_parts = []
        
        # Extract entities from knowledge graph
        if "entities" in lightrag_response:
            entities = lightrag_response.get("entities", [])
            if entities:
                context_parts.append("Entities Data From Knowledge Graph(KG):")
                for entity in entities[:5]:  # Limit to top 5
                    if isinstance(entity, dict):
                        name = entity.get("name", "")
                        desc = entity.get("description", "")
                        if name or desc:
                            context_parts.append(f"- {name}: {desc}")
        
        # Extract relationships
        if "relationships" in lightrag_response:
            relationships = lightrag_response.get("relationships", [])
            if relationships:
                context_parts.append("\nRelationships Data From Knowledge Graph(KG):")
                for rel in relationships[:5]:  # Limit to top 5
                    if isinstance(rel, dict):
                        source = rel.get("source", "")
                        relation = rel.get("relation", "")
                        target = rel.get("target", "")
                        if source and relation and target:
                            context_parts.append(f"- {source} → {relation} → {target}")
        
        # Extract document chunks
        if "chunks" in lightrag_response:
            chunks = lightrag_response.get("chunks", [])
            if chunks:
                context_parts.append("\nOriginal Texts From Document Chunks(DC):")
                for chunk in chunks[:10]:  # Limit to top 10
                    if isinstance(chunk, dict):
                        text = chunk.get("text", chunk.get("content", ""))
                        if text:
                            context_parts.append(f"- {text}")
        
        # Fallback: use response text if available
        if not context_parts and "response" in lightrag_response:
            context_parts.append(lightrag_response["response"])
        
        return "\n".join(context_parts) if context_parts else ""
    
    async def _get_lightrag_context(
        self,
        query: str,
        knowledge_base: Optional[str] = None
    ) -> str:
        """Get context from LightRAG (with caching)"""
        kb = knowledge_base or settings.LIGHTRAG_KNOWLEDGE_BASE
        cache_key = get_cache_key(query, kb)
        
        # Check cache first
        cached = await self.redis_cache.get(cache_key)
        if cached:
            logger.info(f"Cache HIT for query: {query[:50]}...")
            return self._format_lightrag_context(cached)
        
        # Query LightRAG
        try:
            logger.info(f"Querying LightRAG for: {query[:50]}...")
            response = await self.lightrag_client.query(
                query=query,
                knowledge_base=kb,
                mode="mix",
                top_k=5,
                chunk_top_k=10,
                include_references=True,
                only_need_context=True
            )
            
            # Cache the response
            await self.redis_cache.set(cache_key, response)
            
            return self._format_lightrag_context(response)
        except Exception as e:
            logger.error(f"LightRAG query failed: {e}")
            return ""  # Return empty context on error
    
    def _build_messages(
        self,
        query: str,
        context: str,
        conversation_history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Build messages for OpenAI API"""
        messages = [
            {"role": "system", "content": self.system_message}
        ]
        
        # Add conversation history
        for msg in conversation_history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("message", "")
            })
        
        # Add current query with context
        if context:
            user_message = f"Context from knowledge base:\n{context}\n\nUser query: {query}"
        else:
            user_message = query
        
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages
    
    async def process_chat(
        self,
        query: str,
        session_id: Optional[str] = None,
        knowledge_base: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Process a chat query and stream the response
        
        Args:
            query: User's query
            session_id: Session ID for conversation history
            knowledge_base: LightRAG knowledge base name
        
        Yields:
            Response chunks as strings
        """
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Get conversation history
        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            history = memory.get_conversation_history(
                session_id=session_id,
                limit=settings.MAX_CONVERSATION_HISTORY
            )
            conversation_history = [
                {"role": msg.role, "message": msg.message}
                for msg in history
            ]
        finally:
            memory.close()
            db.close()
        
        # Determine if we need LightRAG context
        is_small_talk = self._is_small_talk(query)
        context = ""
        
        if not is_small_talk:
            context = await self._get_lightrag_context(query, knowledge_base)
        
        # Build messages
        messages = self._build_messages(query, context, conversation_history)
        
        # Save user message
        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            memory.add_message(session_id, "user", query)
        finally:
            memory.close()
            db.close()
        
        # Stream response from OpenAI
        full_response = ""
        try:
            stream = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=settings.OPENAI_MAX_TOKENS,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            error_message = "I apologize, but I'm experiencing technical difficulties. Please try again later."
            yield error_message
            full_response = error_message
        
        # Save assistant response
        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            memory.add_message(session_id, "assistant", full_response)
        finally:
            memory.close()
            db.close()
    
    async def process_chat_sync(
        self,
        query: str,
        session_id: Optional[str] = None,
        knowledge_base: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a chat query and return complete response (non-streaming)
        
        Args:
            query: User's query
            session_id: Session ID for conversation history
            knowledge_base: LightRAG knowledge base name
        
        Returns:
            Dictionary with response and session_id
        """
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Get conversation history
        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            history = memory.get_conversation_history(
                session_id=session_id,
                limit=settings.MAX_CONVERSATION_HISTORY
            )
            conversation_history = [
                {"role": msg.role, "message": msg.message}
                for msg in history
            ]
        finally:
            memory.close()
            db.close()
        
        # Determine if we need LightRAG context
        is_small_talk = self._is_small_talk(query)
        context = ""
        
        if not is_small_talk:
            context = await self._get_lightrag_context(query, knowledge_base)
        
        # Build messages
        messages = self._build_messages(query, context, conversation_history)
        
        # Save user message
        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            memory.add_message(session_id, "user", query)
        finally:
            memory.close()
            db.close()
        
        # Get response from OpenAI
        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=settings.OPENAI_MAX_TOKENS,
                stream=False
            )
            
            full_response = response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            full_response = "I apologize, but I'm experiencing technical difficulties. Please try again later."
        
        # Save assistant response
        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            memory.add_message(session_id, "assistant", full_response)
        finally:
            memory.close()
            db.close()
        
        return {
            "response": full_response,
            "session_id": session_id
        }

