"""
API routes for the Bank Chatbot.

Uses Dependency Injection for services via FastAPI's Depends().
Uses Pydantic DTOs for request/response validation and documentation.
"""

from fastapi import APIRouter, HTTPException, Request, Query, Depends
from fastapi.responses import StreamingResponse
from fastapi import Request as FastAPIRequest
from typing import Optional, List, Dict, Any
import logging
import asyncio

from app.services.chat_orchestrator import ChatOrchestrator
from app.services.lightrag_client import LightRAGClient
from app.database.redis_client import RedisCache
from app.core.dependencies import (
    get_orchestrator,
    get_lightrag_client,
    get_redis_cache,
    get_container,
    ServiceContainer,
)

# Import DTOs from models
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    ChatHistoryResponse,
    ClearHistoryResponse,
    RouteDebugResponse,
)
from app.models.health import (
    HealthResponse,
    DetailedHealthResponse,
    ComponentHealth,
)
from app.models.analytics import (
    PerformanceMetricsResponse,
    OverallMetrics,
    DailyMetric,
    MostAskedQuestionsResponse,
    MostAskedQuestion,
    UnansweredQuestionsResponse,
    UnansweredQuestion,
    ConversationHistoryResponse,
    ConversationRecord,
    RoutingDistributionResponse,
    RoutingDistributionItem,
    TestConversationLogResponse,
    ConversationLogCheckResponse,
    ConversationLogCheckRecord,
)
from app.models.common import StatusEnum

logger = logging.getLogger(__name__)

# Create routers
health_router = APIRouter()
chat_router = APIRouter()
analytics_router = APIRouter()
debug_router = APIRouter()

# Legacy: Keep orchestrator reference for backward compatibility
# New code should use Depends(get_orchestrator) instead
def _get_legacy_orchestrator() -> ChatOrchestrator:
    """Get orchestrator from DI container (for backward compatibility)."""
    return get_container().orchestrator

# For backward compatibility with code that imports 'orchestrator' directly
# This is a lazy property that will be resolved when accessed
class _OrchestratorProxy:
    """Proxy object that lazily gets orchestrator from DI container."""
    def __getattr__(self, name):
        return getattr(get_container().orchestrator, name)

orchestrator = _OrchestratorProxy()

# Export orchestrator for shutdown hook
__all__ = ['orchestrator', 'health_router', 'chat_router', 'analytics_router', 'debug_router', 'get_container']


# Health Check Routes
@health_router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status=StatusEnum.HEALTHY,
        service="Bank Chatbot API"
    )


@health_router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(
    lightrag_client: LightRAGClient = Depends(get_lightrag_client),
    redis_cache: RedisCache = Depends(get_redis_cache),
):
    """
    Detailed health check with component status.
    
    Uses injected dependencies instead of creating new instances.
    Runs health checks in PARALLEL for faster response time.
    """
    components: Dict[str, ComponentHealth] = {}
    
    # ============================================================
    # PARALLEL HEALTH CHECKS - Run LightRAG and Redis in parallel
    # ============================================================
    async def check_lightrag() -> ComponentHealth:
        """Check LightRAG health."""
        try:
            health = await lightrag_client.health_check()
            return ComponentHealth(
                status=StatusEnum.HEALTHY if health.get("status") != "error" else StatusEnum.UNHEALTHY,
                details=health
            )
        except asyncio.CancelledError:
            return ComponentHealth(
                status=StatusEnum.UNHEALTHY,
                error="Connection cancelled/timeout"
            )
        except Exception as e:
            return ComponentHealth(
                status=StatusEnum.UNHEALTHY,
                error=str(e)
            )
    
    async def check_redis() -> ComponentHealth:
        """Check Redis health."""
        try:
            await redis_cache.set("health_check", "ok", ttl=10)
            await redis_cache.get("health_check")
            return ComponentHealth(status=StatusEnum.HEALTHY)
        except asyncio.CancelledError:
            return ComponentHealth(
                status=StatusEnum.UNHEALTHY,
                error="Connection cancelled/timeout"
            )
        except Exception as e:
            return ComponentHealth(
                status=StatusEnum.UNHEALTHY,
                error=str(e)
            )
    
    # Run LightRAG and Redis checks in parallel (performance optimization)
    lightrag_result, redis_result = await asyncio.gather(
        check_lightrag(),
        check_redis(),
        return_exceptions=False
    )
    
    components["lightrag"] = lightrag_result
    components["redis"] = redis_result
    
    # Check PostgreSQL (synchronous - run after parallel checks)
    try:
        from app.database.postgres import engine
        from sqlalchemy import text
        if engine:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            components["postgresql"] = ComponentHealth(status=StatusEnum.HEALTHY)
        else:
            components["postgresql"] = ComponentHealth(
                status=StatusEnum.UNHEALTHY,
                error="Engine not initialized"
            )
    except asyncio.CancelledError:
        components["postgresql"] = ComponentHealth(
            status=StatusEnum.UNHEALTHY,
            error="Connection cancelled/timeout"
        )
    except Exception as e:
        components["postgresql"] = ComponentHealth(
            status=StatusEnum.UNHEALTHY,
            error=str(e)
        )
    
    # Overall status
    all_healthy = all(
        comp.status == StatusEnum.HEALTHY
        for comp in components.values()
    )
    overall_status = StatusEnum.HEALTHY if all_healthy else StatusEnum.DEGRADED
    
    return DetailedHealthResponse(
        status=overall_status,
        service="Bank Chatbot API",
        components=components
    )


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
async def chat(
    request: ChatRequest,
    http_request: FastAPIRequest,
    chat_orchestrator: ChatOrchestrator = Depends(get_orchestrator),
):
    """
    Chat endpoint - Process user query and return response.
    
    Supports both streaming and non-streaming responses.
    Uses injected ChatOrchestrator via dependency injection.
    """
    try:
        client_ip = get_client_ip(http_request)
        
        if request.stream:
            # Streaming response
            async def generate():
                async for chunk in chat_orchestrator.process_chat(
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
            result = await chat_orchestrator.process_chat_sync(
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
async def chat_stream(
    request: ChatRequest,
    http_request: FastAPIRequest,
    chat_orchestrator: ChatOrchestrator = Depends(get_orchestrator),
):
    """
    Streaming chat endpoint - Stream response chunks.
    Uses injected ChatOrchestrator via dependency injection.
    """
    try:
        client_ip = get_client_ip(http_request) if http_request else "unknown"
        
        async def generate():
            try:
                async for chunk in chat_orchestrator.process_chat(
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


@chat_router.get("/chat/history/{session_id}", response_model=ChatHistoryResponse)
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
            messages = [
                ChatMessage(
                    id=msg.id,
                    role=msg.role,
                    message=msg.message,
                    created_at=msg.created_at.isoformat()
                )
                for msg in history
            ]
            return ChatHistoryResponse(
                session_id=session_id,
                messages=messages
            )
        finally:
            memory.close()
            db.close()
    except Exception as e:
        logger.error(f"Get history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@chat_router.delete("/chat/history/{session_id}", response_model=ClearHistoryResponse)
async def clear_chat_history(session_id: str):
    """Clear conversation history for a session"""
    try:
        from app.database.postgres import PostgresChatMemory, get_db
        
        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            success = memory.clear_session(session_id)
            return ClearHistoryResponse(
                session_id=session_id,
                cleared=success
            )
        finally:
            memory.close()
            db.close()
    except Exception as e:
        logger.error(f"Clear history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Analytics Routes
@analytics_router.get("/analytics/performance", response_model=PerformanceMetricsResponse)
async def get_performance(days: int = Query(30, ge=1, le=365)):
    """Get performance metrics for the last N days"""
    try:
        from app.services.analytics import get_performance_metrics
        data = get_performance_metrics(days=days)
        
        # Convert to DTOs
        daily_metrics = [
            DailyMetric(**metric) for metric in data.get('daily_metrics', [])
        ]
        overall = OverallMetrics(**data.get('overall', {
            'total_conversations': 0,
            'total_answered': 0,
            'total_unanswered': 0,
            'overall_answer_rate': 0,
            'avg_response_time_ms': 0
        }))
        
        return PerformanceMetricsResponse(
            period_days=data.get('period_days', days),
            overall=overall,
            daily_metrics=daily_metrics
        )
    except Exception as e:
        logger.error(f"Analytics performance error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@analytics_router.get("/analytics/most-asked", response_model=MostAskedQuestionsResponse)
async def get_most_asked(limit: int = Query(20, ge=1, le=100)):
    """Get most frequently asked questions"""
    try:
        from app.services.analytics import get_most_asked_questions
        data = get_most_asked_questions(limit=limit)
        
        questions = [MostAskedQuestion(**q) for q in data]
        return MostAskedQuestionsResponse(questions=questions)
    except Exception as e:
        logger.error(f"Analytics most-asked error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@analytics_router.get("/analytics/unanswered", response_model=UnansweredQuestionsResponse)
async def get_unanswered(limit: int = Query(50, ge=1, le=200)):
    """Get questions that were not answered"""
    try:
        from app.services.analytics import get_unanswered_questions
        data = get_unanswered_questions(limit=limit)
        
        questions = [UnansweredQuestion(**q) for q in data]
        return UnansweredQuestionsResponse(questions=questions)
    except Exception as e:
        logger.error(f"Analytics unanswered error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@analytics_router.get("/analytics/history", response_model=ConversationHistoryResponse)
async def get_history(
    session_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    routing_target: Optional[str] = Query(None)
):
    """Get conversation history with optional filters"""
    try:
        from app.services.analytics import get_conversation_history
        data = get_conversation_history(
            session_id=session_id, 
            limit=limit,
            search=search,
            routing_target=routing_target
        )
        
        conversations = [ConversationRecord(**conv) for conv in data]
        return ConversationHistoryResponse(conversations=conversations)
    except Exception as e:
        logger.error(f"Analytics history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@analytics_router.get("/analytics/routing-distribution", response_model=RoutingDistributionResponse)
async def get_routing_dist(days: int = Query(30, ge=1, le=365)):
    """Get routing distribution statistics for the last N days"""
    try:
        from app.services.analytics import get_routing_distribution
        data = get_routing_distribution(days=days)
        
        distribution = [
            RoutingDistributionItem(**item) for item in data.get('distribution', [])
        ]
        
        return RoutingDistributionResponse(
            period_days=data.get('period_days', days),
            distribution=distribution,
            total=data.get('total', 0)
        )
    except Exception as e:
        logger.error(f"Analytics routing distribution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@analytics_router.get("/analytics/export-csv")
async def export_conversations_csv(
    days: int = Query(30, ge=1, le=365),
    search: Optional[str] = Query(None)
):
    """Export conversations as CSV"""
    try:
        from app.services.analytics import get_conversations_csv
        import csv
        import io
        from fastapi.responses import StreamingResponse
        
        conversations = get_conversations_csv(days=days, search=search)
        
        # Create CSV in memory
        output = io.StringIO()
        if conversations:
            fieldnames = conversations[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(conversations)
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=conversations_export_{days}days.csv"}
        )
    except Exception as e:
        logger.error(f"Analytics CSV export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Debug Routes
@debug_router.post("/debug/test-conversation-log", response_model=TestConversationLogResponse)
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
        
        return TestConversationLogResponse(
            status="success",
            message="Test ConversationLog record created successfully"
        )
    except Exception as e:
        logger.error(f"Error creating test ConversationLog: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@debug_router.get("/debug/check-conversation-log", response_model=ConversationLogCheckResponse)
async def check_conversation_log():
    """Debug endpoint to directly query ConversationLog table"""
    try:
        from app.database.postgres import get_db
        from app.services.analytics import ConversationLog
        from sqlalchemy import inspect
        
        db = get_db()
        if not db:
            return ConversationLogCheckResponse(
                status="error",
                table_exists=False,
                record_count=0,
                recent_records=[],
                available_tables=[],
                message="Database not available"
            )
        
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
                recent = [
                    ConversationLogCheckRecord(
                        id=r.id,
                        session_id=r.session_id,
                        client_ip=r.client_ip,
                        created_at=r.created_at.isoformat() if r.created_at else None
                    )
                    for r in recent_records
                ]
            
            return ConversationLogCheckResponse(
                status="success",
                table_exists=table_exists,
                record_count=count,
                recent_records=recent,
                available_tables=tables
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error checking ConversationLog: {e}", exc_info=True)
        return ConversationLogCheckResponse(
            status="error",
            table_exists=False,
            record_count=0,
            recent_records=[],
            available_tables=[],
            message=str(e)
        )


@debug_router.get("/debug/lightrag")
async def debug_lightrag(
    lightrag_client: LightRAGClient = Depends(get_lightrag_client),
):
    """Debug endpoint for LightRAG status and last query (uses DI)."""
    try:
        health = await lightrag_client.health_check()
        
        # Get last query info if available
        last_query_info = getattr(lightrag_client, '_last_query', None)
        
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


@debug_router.get("/debug/route", response_model=RouteDebugResponse)
async def debug_route(
    query: str,
    session_id: Optional[str] = None,
    knowledge_base: Optional[str] = None,
    http_request: FastAPIRequest = None,
    chat_orchestrator: ChatOrchestrator = Depends(get_orchestrator),
):
    """
    Debug endpoint to show routing decision for a query (uses DI).
    No OpenAI calls are made; safe for troubleshooting and regression tests.
    """
    try:
        client_ip = get_client_ip(http_request) if http_request else "unknown"
        decision = await chat_orchestrator.diagnose_routing(
            query=query,
            session_id=session_id,
            knowledge_base=knowledge_base,
            client_ip=client_ip,
        )
        return decision
    except Exception as e:
        logger.error(f"Route debug error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@debug_router.get("/debug/response-cache-stats")
async def get_response_cache_stats(
    redis_cache: RedisCache = Depends(get_redis_cache),
):
    """
    Get OpenAI response cache statistics.
    
    Returns cache hit/miss counts and hit rate percentage.
    Used to monitor token optimization effectiveness.
    """
    try:
        stats = await redis_cache.get_response_cache_stats()
        return {
            "status": "success",
            "cache_stats": stats,
            "description": {
                "hits": "Number of queries served from cache (no OpenAI call)",
                "misses": "Number of queries that required OpenAI API call",
                "hit_rate": "Percentage of queries served from cache",
                "available": "Whether Redis cache is available"
            }
        }
    except Exception as e:
        logger.error(f"Response cache stats error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "cache_stats": {"hits": 0, "misses": 0, "hit_rate": 0.0, "available": False}
        }


@debug_router.delete("/debug/response-cache")
async def clear_response_cache(
    redis_cache: RedisCache = Depends(get_redis_cache),
):
    """
    Clear all cached OpenAI responses.
    
    Use this when you need to force fresh responses from OpenAI.
    """
    try:
        deleted_count = await redis_cache.clear_response_cache()
        return {
            "status": "success",
            "message": f"Cleared {deleted_count} cached responses",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Clear response cache error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "deleted_count": 0
        }

