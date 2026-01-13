"""
API routes for the Bank Chatbot.
"""

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from fastapi import Request as FastAPIRequest
from pydantic import BaseModel, Field
from typing import Optional, List
import logging
import asyncio

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

# Export orchestrator for shutdown hook
__all__ = ['orchestrator', 'health_router', 'chat_router', 'analytics_router', 'debug_router']


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
    sources: Optional[List[str]] = Field(default=[], description="Knowledge base sources used")


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
    except asyncio.CancelledError:
        status["components"]["lightrag"] = {
            "status": "unhealthy",
            "error": "Connection cancelled/timeout"
        }
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
    except asyncio.CancelledError:
        status["components"]["redis"] = {
            "status": "unhealthy",
            "error": "Connection cancelled/timeout"
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
    except asyncio.CancelledError:
        status["components"]["postgresql"] = {
            "status": "unhealthy",
            "error": "Connection cancelled/timeout"
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


def is_local_network_ip(ip: str) -> bool:
    """Check if IP is a local network address"""
    if not ip or ip == "0.0.0.0" or ip == "unknown":
        return False
    
    # IPv4 local network ranges
    if ip.startswith("192.168."):
        return True
    if ip.startswith("10."):
        return True
    if ip.startswith("172."):
        parts = ip.split(".")
        if len(parts) == 4:
            try:
                second_octet = int(parts[1])
                if 16 <= second_octet <= 31:
                    return True  # 172.16.0.0 - 172.31.255.255
            except ValueError:
                pass
    
    # IPv6 local addresses
    if ip.startswith("fe80:") or ip.startswith("fc00:") or ip.startswith("fd00:"):
        return True
    
    return False


def get_client_ip(request: FastAPIRequest) -> str:
    """Extract client IP address from request - prioritizes local network IPs"""
    # Priority 1: Check for X-Client-IP header (sent by frontend with actual user IP from WebRTC)
    # This is the most reliable for local network IPs like 192.168.x.x
    client_ip_header = request.headers.get("X-Client-IP")
    if client_ip_header:
        ip = client_ip_header.strip()
        # Only accept local network IPs from X-Client-IP (reject public IPs)
        if is_local_network_ip(ip):
            logger.info(f"Using X-Client-IP header (local IP): {ip}")
            return ip
        else:
            logger.warning(f"X-Client-IP header contains public IP, ignoring: {ip}")
    
    # Priority 2: Check for forwarded IP (when behind proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, check all of them for local IPs first
        ips = [ip.strip() for ip in forwarded_for.split(",")]
        for ip in ips:
            if is_local_network_ip(ip):
                logger.info(f"Using X-Forwarded-For header (local IP): {ip}")
                return ip
        # If no local IP found, use first non-localhost IP
        for ip in ips:
            if ip and ip not in ["127.0.0.1", "::1", "localhost"]:
                logger.info(f"Using X-Forwarded-For header: {ip}")
                return ip
    
    # Priority 3: Check for real IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        ip = real_ip.strip()
        # Prefer local network IPs
        if is_local_network_ip(ip):
            logger.info(f"Using X-Real-IP header (local IP): {ip}")
            return ip
        if ip and ip not in ["127.0.0.1", "::1", "localhost"]:
            logger.info(f"Using X-Real-IP header: {ip}")
            return ip
    
    # Priority 4: Fall back to direct client IP
    if request.client:
        ip = request.client.host
        # Prefer local network IPs from direct connection
        if is_local_network_ip(ip):
            logger.info(f"Using direct client IP (local): {ip}")
            return ip
        # If it's localhost, this is likely a proxy situation
        if ip in ["127.0.0.1", "::1"]:
            # Check if there's any other header that might help
            cf_connecting_ip = request.headers.get("CF-Connecting-IP")  # Cloudflare
            if cf_connecting_ip and is_local_network_ip(cf_connecting_ip):
                logger.info(f"Using CF-Connecting-IP header (local): {cf_connecting_ip}")
                return cf_connecting_ip.strip()
            
            # Try to get IP from the connection's remote address if available
            # This might work if the proxy forwards the real IP in the connection
            try:
                # Check if we can get the remote address from the underlying connection
                if hasattr(request, 'scope') and 'client' in request.scope:
                    client_info = request.scope.get('client')
                    if client_info and len(client_info) > 0:
                        remote_ip = client_info[0]
                        if remote_ip and is_local_network_ip(remote_ip):
                            logger.info(f"Using remote address from scope (local): {remote_ip}")
                            return remote_ip
            except Exception as e:
                logger.debug(f"Could not get remote address from scope: {e}")
            
            # If direct connection is localhost but we're looking for local network IP,
            # this might be a proxy situation - log it
            logger.warning(f"Direct client IP is localhost ({ip}), but no local network IP found in headers. "
                          f"Request may be going through a proxy. Headers: {dict(request.headers)}")
        # If direct IP is not localhost and not a local network IP, it might be a public IP
        # In this case, we still return it but log a warning
        if not is_local_network_ip(ip) and ip not in ["127.0.0.1", "::1"]:
            logger.warning(f"Using direct client IP (public/non-local): {ip}")
        logger.info(f"Using direct client IP: {ip}")
        return ip
    
    logger.warning("Could not determine client IP, returning 'unknown'")
    return "unknown"


# Chat Routes
@chat_router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: FastAPIRequest):
    """
    Chat endpoint - Process user query and return response
    
    Supports both streaming and non-streaming responses.
    """
    try:
        client_ip = get_client_ip(http_request)
        
        if request.stream:
            # Streaming response
            async def generate():
                async for chunk in orchestrator.process_chat(
                    query=request.query,
                    session_id=request.session_id,
                    knowledge_base=request.knowledge_base,
                    client_ip=client_ip
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
                knowledge_base=request.knowledge_base,
                client_ip=client_ip
            )
            return ChatResponse(
                response=result["response"],
                session_id=result["session_id"],
                sources=result.get("sources", [])
            )
    except asyncio.CancelledError:
        logger.warning("Chat request was cancelled")
        raise HTTPException(status_code=499, detail="Request cancelled")
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@chat_router.post("/chat/stream")
async def chat_stream(request: ChatRequest, http_request: FastAPIRequest):
    """
    Streaming chat endpoint - Stream response chunks
    """
    try:
        client_ip = get_client_ip(http_request) if http_request else "unknown"
        
        async def generate():
            try:
                async for chunk in orchestrator.process_chat(
                    query=request.query,
                    session_id=request.session_id,
                    knowledge_base=request.knowledge_base,
                    client_ip=client_ip
                ):
                    yield chunk
            except asyncio.CancelledError:
                logger.warning("Chat stream generation was cancelled")
                yield "Error: Request was cancelled."
            except Exception as e:
                logger.error(f"Error in chat stream generation: {e}", exc_info=True)
                error_msg = f"Error: {str(e)}"
                yield error_msg
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Session-ID": request.session_id or "new"
            }
        )
    except asyncio.CancelledError:
        logger.warning("Chat stream request was cancelled")
        raise HTTPException(status_code=499, detail="Request cancelled")
    except Exception as e:
        logger.error(f"Chat stream error: {e}", exc_info=True)
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
@debug_router.post("/debug/test-conversation-log")
async def test_conversation_log():
    """Test endpoint to create a ConversationLog record"""
    try:
        from app.services.analytics import log_conversation
        
        log_conversation(
            session_id="debug_test_session",
            user_message="Test message from debug endpoint",
            assistant_response="This is a test response to verify ConversationLog creation.",
            knowledge_base="test",
            response_time_ms=100,
            client_ip="127.0.0.1"
        )
        
        return {
            "status": "success",
            "message": "Test ConversationLog record created successfully"
        }
    except Exception as e:
        logger.error(f"Error creating test ConversationLog: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@debug_router.get("/debug/check-conversation-log")
async def check_conversation_log():
    """Debug endpoint to directly query ConversationLog table"""
    try:
        from app.database.postgres import get_db
        from app.services.analytics import ConversationLog
        from sqlalchemy import inspect
        
        db = get_db()
        if not db:
            return {"status": "error", "message": "Database not available"}
        
        try:
            # Check if table exists
            inspector = inspect(db.bind)
            tables = inspector.get_table_names()
            table_exists = 'analytics_conversations' in tables
            
            # Count records
            count = db.query(ConversationLog).count() if table_exists else 0
            
            # Get recent records
            recent = []
            if table_exists and count > 0:
                recent_records = db.query(ConversationLog).order_by(
                    ConversationLog.created_at.desc()
                ).limit(5).all()
                recent = [{
                    "id": r.id,
                    "session_id": r.session_id,
                    "client_ip": r.client_ip,
                    "created_at": r.created_at.isoformat() if r.created_at else None
                } for r in recent_records]
            
            return {
                "status": "success",
                "table_exists": table_exists,
                "record_count": count,
                "recent_records": recent,
                "available_tables": tables
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error checking ConversationLog: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


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

