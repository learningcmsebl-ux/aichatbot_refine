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
app.include_router(chat_router, prefix="/api", tags=["Chat"])
app.include_router(analytics_router, prefix="/api", tags=["Analytics"])
app.include_router(debug_router, prefix="/api", tags=["Debug"])
app.include_router(phonebook_router, prefix="/api", tags=["Phonebook"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Bank Chatbot API",
        "version": "1.0.0",
        "status": "running"
    }

