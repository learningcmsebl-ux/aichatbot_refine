"""
API routes for the Bank Chatbot.
"""

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import logging

from app.services.chat_orchestrator import ChatOrchestrator
from app.services.lightrag_client import LightRAGClient
from app.database.redis_client import RedisCache

logger = logging.getLogger(__name__)

# Create routers
health_router = APIRouter()
chat_router = APIRouter()
analytics_router = APIRouter()
debug_router = APIRouter()

# Initialize orchestrator (singleton)
orchestrator = ChatOrchestrator()


# Request/Response Models
class ChatRequest(BaseModel):
    """Chat request model"""
    query: str = Field(..., description="User's query or message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation history")
    knowledge_base: Optional[str] = Field(None, description="LightRAG knowledge base name")
    stream: bool = Field(True, description="Whether to stream the response")


class ChatResponse(BaseModel):
    """Chat response model"""
    response: str = Field(..., description="Assistant's response")
    session_id: str = Field(..., description="Session ID for the conversation")


# Health Check Routes
@health_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Bank Chatbot API"
    }


@health_router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with component status"""
    status = {
        "status": "healthy",
        "service": "Bank Chatbot API",
        "components": {}
    }
    
    # Check LightRAG
    try:
        lightrag_client = LightRAGClient()
        health = await lightrag_client.health_check()
        status["components"]["lightrag"] = {
            "status": "healthy" if health.get("status") != "error" else "unhealthy",
            "details": health
        }
        await lightrag_client.close()
    except Exception as e:
        status["components"]["lightrag"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check Redis
    try:
        redis_cache = RedisCache()
        # Try a simple operation
        await redis_cache.set("health_check", "ok", ttl=10)
        await redis_cache.get("health_check")
        status["components"]["redis"] = {
            "status": "healthy"
        }
    except Exception as e:
        status["components"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check PostgreSQL (basic check)
    try:
        from app.database.postgres import engine
        from sqlalchemy import text
        if engine:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            status["components"]["postgresql"] = {
                "status": "healthy"
            }
        else:
            status["components"]["postgresql"] = {
                "status": "unhealthy",
                "error": "Engine not initialized"
            }
    except Exception as e:
        status["components"]["postgresql"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Overall status
    all_healthy = all(
        comp.get("status") == "healthy"
        for comp in status["components"].values()
    )
    if not all_healthy:
        status["status"] = "degraded"
    
    return status


# Chat Routes
@chat_router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint - Process user query and return response
    
    Supports both streaming and non-streaming responses.
    """
    try:
        if request.stream:
            # Streaming response
            async def generate():
                async for chunk in orchestrator.process_chat(
                    query=request.query,
                    session_id=request.session_id,
                    knowledge_base=request.knowledge_base
                ):
                    yield chunk
            
            return StreamingResponse(
                generate(),
                media_type="text/plain",
                headers={
                    "X-Session-ID": request.session_id or "new",
                    "X-Content-Type": "streaming"
                }
            )
        else:
            # Non-streaming response
            result = await orchestrator.process_chat_sync(
                query=request.query,
                session_id=request.session_id,
                knowledge_base=request.knowledge_base
            )
            return ChatResponse(
                response=result["response"],
                session_id=result["session_id"]
            )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@chat_router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint - Stream response chunks
    """
    try:
        async def generate():
            async for chunk in orchestrator.process_chat(
                query=request.query,
                session_id=request.session_id,
                knowledge_base=request.knowledge_base
            ):
                yield chunk
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Session-ID": request.session_id or "new"
            }
        )
    except Exception as e:
        logger.error(f"Chat stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@chat_router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str, limit: Optional[int] = 50):
    """Get conversation history for a session"""
    try:
        from app.database.postgres import PostgresChatMemory, get_db
        
        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            history = memory.get_conversation_history(
                session_id=session_id,
                limit=limit
            )
            return {
                "session_id": session_id,
                "messages": [
                    {
                        "id": msg.id,
                        "role": msg.role,
                        "message": msg.message,
                        "created_at": msg.created_at.isoformat()
                    }
                    for msg in history
                ]
            }
        finally:
            memory.close()
            db.close()
    except Exception as e:
        logger.error(f"Get history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@chat_router.delete("/chat/history/{session_id}")
async def clear_chat_history(session_id: str):
    """Clear conversation history for a session"""
    try:
        from app.database.postgres import PostgresChatMemory, get_db
        
        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            success = memory.clear_session(session_id)
            return {
                "session_id": session_id,
                "cleared": success
            }
        finally:
            memory.close()
            db.close()
    except Exception as e:
        logger.error(f"Clear history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Analytics Routes
@analytics_router.get("/analytics/performance")
async def get_performance(days: int = Query(30, ge=1, le=365)):
    """Get performance metrics for the last N days"""
    try:
        from app.services.analytics import get_performance_metrics
        return get_performance_metrics(days=days)
    except Exception as e:
        logger.error(f"Analytics performance error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@analytics_router.get("/analytics/most-asked")
async def get_most_asked(limit: int = Query(20, ge=1, le=100)):
    """Get most frequently asked questions"""
    try:
        from app.services.analytics import get_most_asked_questions
        return {"questions": get_most_asked_questions(limit=limit)}
    except Exception as e:
        logger.error(f"Analytics most-asked error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@analytics_router.get("/analytics/unanswered")
async def get_unanswered(limit: int = Query(50, ge=1, le=200)):
    """Get questions that were not answered"""
    try:
        from app.services.analytics import get_unanswered_questions
        return {"questions": get_unanswered_questions(limit=limit)}
    except Exception as e:
        logger.error(f"Analytics unanswered error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@analytics_router.get("/analytics/history")
async def get_history(
    session_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get conversation history"""
    try:
        from app.services.analytics import get_conversation_history
        return {"conversations": get_conversation_history(session_id=session_id, limit=limit)}
    except Exception as e:
        logger.error(f"Analytics history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Debug Routes
@debug_router.get("/debug/lightrag")
async def debug_lightrag():
    """Debug endpoint for LightRAG status and last query"""
    try:
        lightrag_client = LightRAGClient()
        health = await lightrag_client.health_check()
        
        # Get last query info if available
        last_query_info = getattr(lightrag_client, '_last_query', None)
        
        await lightrag_client.close()
        
        return {
            "status": "ok",
            "lightrag_health": health,
            "last_query": last_query_info if last_query_info else "No queries yet"
        }
    except Exception as e:
        logger.error(f"Debug LightRAG error: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

