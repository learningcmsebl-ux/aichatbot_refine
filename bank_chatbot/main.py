"""
Bank Chatbot - FastAPI Orchestrator
Main application entry point for the bank chatbot system.

Uses Dependency Injection for service lifecycle management.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.api.routes import chat_router, health_router, analytics_router, debug_router, get_container
from app.api.phonebook_routes import phonebook_router
from app.api.forms_routes import forms_router
from app.api.apps_routes import apps_router
from app.api.leadership_routes import leadership_router
from app.api.soc_routes import soc_router
from app.api.proposals_routes import proposals_router
from app.api.circulars_routes import circulars_router
from app.api.auth_routes import auth_router
from app.api.chat_session_routes import sessions_router
from app.api.lead_routes import lead_router
from app.api.portal_user_routes import portal_user_router
from app.database.postgres import init_db, close_db
from app.database.redis_client import init_redis, close_redis
from app.core.dependencies import startup_services, shutdown_services

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown.
    
    Uses Dependency Injection container for service lifecycle management.
    """
    # Startup
    logger.info("Starting Bank Chatbot application...")
    await init_db()
    await init_redis()
    await startup_services()  # Initialize DI container services

    # Warm up the semantic intent router (loads local embedding model on CPU)
    # so the first shadow/active request isn't slowed by lazy loading.
    try:
        from app.core.config import settings
        if getattr(settings, "ENABLE_SEMANTIC_ROUTER", False):
            from app.services.semantic_router import get_semantic_router
            ok = get_semantic_router().warmup()
            logger.info("Semantic router warmup: %s", "ready" if ok else "unavailable")
    except Exception as exc:  # noqa: BLE001 - never block startup
        logger.warning("Semantic router warmup skipped: %s", exc)

    logger.info("Application started successfully")
    yield
    # Shutdown
    logger.info("Shutting down Bank Chatbot application...")
    await shutdown_services()  # Cleanup DI container services
    await close_db()
    await close_redis()
    logger.info("Application shut down successfully")


# Create FastAPI app
app = FastAPI(
    title="Bank Chatbot API",
    description="AI-powered chatbot for banking services using FastAPI, PostgreSQL, Redis, and LightRAG",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/api", tags=["Health"])
app.include_router(auth_router, prefix="/api", tags=["Auth"])
app.include_router(sessions_router, prefix="/api", tags=["Chat Sessions"])
app.include_router(lead_router, prefix="/api", tags=["Leads"])
app.include_router(portal_user_router, prefix="/api", tags=["Portal Users"])
app.include_router(chat_router, prefix="/api", tags=["Chat"])
app.include_router(analytics_router, prefix="/api", tags=["Analytics"])
app.include_router(debug_router, prefix="/api", tags=["Debug"])
app.include_router(phonebook_router, prefix="/api", tags=["Phonebook"])
app.include_router(forms_router, prefix="/api", tags=["Forms"])
app.include_router(apps_router, prefix="/api", tags=["Apps"])
app.include_router(leadership_router, prefix="/api", tags=["Leadership"])
app.include_router(soc_router, prefix="/api", tags=["SOC"])
app.include_router(proposals_router, prefix="/api", tags=["Proposals"])
app.include_router(circulars_router, prefix="/api", tags=["Circulars"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Bank Chatbot API",
        "version": "1.0.0",
        "status": "running"
    }

