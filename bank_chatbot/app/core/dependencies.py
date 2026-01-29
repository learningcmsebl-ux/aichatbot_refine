"""
Dependency Injection Container for Bank Chatbot.

This module provides FastAPI-compatible dependency injection for all services.
Benefits:
- Loose coupling between components
- Easier testing (mock dependencies)
- Centralized service lifecycle management
- Clear dependency graph

Usage in routes:
    from app.core.dependencies import get_orchestrator, get_lightrag_client
    
    @router.post("/chat")
    async def chat(
        request: ChatRequest,
        orchestrator: ChatOrchestrator = Depends(get_orchestrator)
    ):
        ...
"""

from typing import Optional, AsyncGenerator
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Service Instances (Singletons)
# ============================================================================

class ServiceContainer:
    """
    Container for managing service instances.
    Uses lazy initialization for services.
    """
    _instance: Optional["ServiceContainer"] = None
    
    def __init__(self):
        self._orchestrator = None
        self._lightrag_client = None
        self._fee_engine_client = None
        self._location_client = None
        self._redis_cache = None
        self._phonebook_db = None
        self._initialized = False
    
    @classmethod
    def get_instance(cls) -> "ServiceContainer":
        """Get singleton instance of ServiceContainer."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset the container (useful for testing)."""
        if cls._instance:
            cls._instance._initialized = False
            cls._instance._orchestrator = None
            cls._instance._lightrag_client = None
            cls._instance._fee_engine_client = None
            cls._instance._location_client = None
            cls._instance._redis_cache = None
            cls._instance._phonebook_db = None
        cls._instance = None
    
    # -------------------------------------------------------------------------
    # LightRAG Client
    # -------------------------------------------------------------------------
    @property
    def lightrag_client(self):
        """Lazy initialization of LightRAG client."""
        if self._lightrag_client is None:
            from app.services.lightrag_client import LightRAGClient
            self._lightrag_client = LightRAGClient()
            logger.info("LightRAG client initialized via DI container")
        return self._lightrag_client
    
    # -------------------------------------------------------------------------
    # Fee Engine Client
    # -------------------------------------------------------------------------
    @property
    def fee_engine_client(self):
        """Lazy initialization of Fee Engine client."""
        if self._fee_engine_client is None:
            from app.services.fee_engine_client import FeeEngineClient
            self._fee_engine_client = FeeEngineClient()
            logger.info("Fee Engine client initialized via DI container")
        return self._fee_engine_client
    
    # -------------------------------------------------------------------------
    # Location Client
    # -------------------------------------------------------------------------
    @property
    def location_client(self):
        """Lazy initialization of Location client."""
        if self._location_client is None:
            from app.services.location_client import LocationClient
            self._location_client = LocationClient()
            logger.info("Location client initialized via DI container")
        return self._location_client
    
    # -------------------------------------------------------------------------
    # Redis Cache
    # -------------------------------------------------------------------------
    @property
    def redis_cache(self):
        """Lazy initialization of Redis cache."""
        if self._redis_cache is None:
            from app.database.redis_client import RedisCache
            self._redis_cache = RedisCache()
            logger.info("Redis cache initialized via DI container")
        return self._redis_cache
    
    # -------------------------------------------------------------------------
    # Phonebook DB
    # -------------------------------------------------------------------------
    @property
    def phonebook_db(self):
        """Lazy initialization of Phonebook database."""
        if self._phonebook_db is None:
            try:
                from app.services.phonebook_postgres import get_phonebook_db
                self._phonebook_db = get_phonebook_db()
                logger.info("Phonebook DB initialized via DI container")
            except ImportError as e:
                logger.warning(f"Phonebook DB not available: {e}")
                self._phonebook_db = None
        return self._phonebook_db
    
    # -------------------------------------------------------------------------
    # Chat Orchestrator (main service)
    # -------------------------------------------------------------------------
    @property
    def orchestrator(self):
        """
        Lazy initialization of Chat Orchestrator.
        Orchestrator receives its dependencies from this container.
        """
        if self._orchestrator is None:
            from app.services.chat_orchestrator import ChatOrchestrator
            # Create orchestrator with injected dependencies
            self._orchestrator = ChatOrchestrator(
                lightrag_client=self.lightrag_client,
                fee_engine_client=self.fee_engine_client,
                location_client=self.location_client,
                redis_cache=self.redis_cache,
                phonebook_db=self.phonebook_db
            )
            logger.info("Chat Orchestrator initialized via DI container")
        return self._orchestrator
    
    # -------------------------------------------------------------------------
    # Shutdown / Cleanup
    # -------------------------------------------------------------------------
    async def shutdown(self):
        """
        Clean up all service instances.
        
        Properly closes HTTP clients to release connection pools.
        This is important for clean shutdown and resource management.
        """
        logger.info("Shutting down service container...")
        
        # Close LightRAG client (has persistent HTTP client)
        if self._lightrag_client:
            try:
                await self._lightrag_client.close()
                logger.info("LightRAG client closed")
            except Exception as e:
                logger.warning(f"Error closing LightRAG client: {e}")
        
        # Close Fee Engine client (has persistent HTTP client)
        if self._fee_engine_client:
            try:
                await self._fee_engine_client.close()
                logger.info("Fee Engine client closed")
            except Exception as e:
                logger.warning(f"Error closing Fee Engine client: {e}")
        
        # Close Location client (has persistent HTTP client)
        if self._location_client:
            try:
                await self._location_client.close()
                logger.info("Location client closed")
            except Exception as e:
                logger.warning(f"Error closing Location client: {e}")
        
        # Close orchestrator
        if self._orchestrator:
            try:
                await self._orchestrator.close()
                logger.info("Chat Orchestrator closed")
            except Exception as e:
                logger.warning(f"Error closing orchestrator: {e}")
        
        logger.info("Service container shutdown complete - all HTTP clients closed")


# ============================================================================
# FastAPI Dependency Functions
# ============================================================================

def get_container() -> ServiceContainer:
    """Get the service container instance."""
    return ServiceContainer.get_instance()


def get_orchestrator():
    """
    Dependency provider for ChatOrchestrator.
    
    Usage:
        @router.post("/chat")
        async def chat(orchestrator: ChatOrchestrator = Depends(get_orchestrator)):
            ...
    """
    return get_container().orchestrator


def get_lightrag_client():
    """
    Dependency provider for LightRAGClient.
    
    Usage:
        @router.get("/health/lightrag")
        async def check_lightrag(client: LightRAGClient = Depends(get_lightrag_client)):
            ...
    """
    return get_container().lightrag_client


def get_fee_engine_client():
    """
    Dependency provider for FeeEngineClient.
    
    Usage:
        @router.post("/fees/calculate")
        async def calculate(client: FeeEngineClient = Depends(get_fee_engine_client)):
            ...
    """
    return get_container().fee_engine_client


def get_location_client():
    """
    Dependency provider for LocationClient.
    
    Usage:
        @router.get("/locations")
        async def get_locations(client: LocationClient = Depends(get_location_client)):
            ...
    """
    return get_container().location_client


def get_redis_cache():
    """
    Dependency provider for RedisCache.
    
    Usage:
        @router.get("/cache/{key}")
        async def get_cached(key: str, cache: RedisCache = Depends(get_redis_cache)):
            ...
    """
    return get_container().redis_cache


def get_phonebook_db():
    """
    Dependency provider for PhoneBookDB.
    
    Usage:
        @router.get("/phonebook/search")
        async def search(db: PhoneBookDB = Depends(get_phonebook_db)):
            ...
    """
    return get_container().phonebook_db


# ============================================================================
# Database Session Dependency
# ============================================================================

def get_db_session():
    """
    Dependency provider for database session.
    Yields a session and ensures cleanup.
    
    Usage:
        @router.get("/users")
        async def get_users(db: Session = Depends(get_db_session)):
            ...
    """
    from app.database.postgres import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# Startup/Shutdown Hooks
# ============================================================================

async def startup_services():
    """Initialize services on application startup."""
    logger.info("Starting up services...")
    container = get_container()
    # Eagerly initialize critical services
    _ = container.orchestrator
    logger.info("Services started")


async def shutdown_services():
    """Cleanup services on application shutdown."""
    container = get_container()
    await container.shutdown()
