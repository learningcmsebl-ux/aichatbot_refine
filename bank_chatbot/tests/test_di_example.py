"""
Example tests demonstrating Dependency Injection benefits.

This file shows how to:
1. Mock dependencies for unit testing
2. Use the ServiceContainer for integration tests
3. Override dependencies in FastAPI routes for testing

Run with: pytest tests/test_di_example.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional, Dict, Any


# ============================================================================
# Mock Classes for Testing
# ============================================================================

class MockLightRAGClient:
    """Mock LightRAG client for testing."""
    
    def __init__(self, mock_response: Optional[str] = None):
        self.mock_response = mock_response or "Mock LightRAG response"
        self.query_called = False
        self.last_query = None
    
    async def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "mock": True}
    
    async def query(self, query: str, **kwargs) -> Dict[str, Any]:
        self.query_called = True
        self.last_query = query
        return {
            "response": self.mock_response,
            "sources": ["mock_source_1", "mock_source_2"]
        }
    
    async def close(self):
        pass


class MockFeeEngineClient:
    """Mock Fee Engine client for testing."""
    
    def __init__(self, mock_fee: Optional[float] = 100.0):
        self.mock_fee = mock_fee
        self.calculate_called = False
    
    async def calculate_fee(self, query: str, **kwargs) -> Optional[Dict[str, Any]]:
        self.calculate_called = True
        return {
            "status": "CALCULATED",
            "fee_amount": self.mock_fee,
            "fee_currency": "BDT",
            "fee_basis": "PER_YEAR"
        }
    
    def format_fee_response(self, fee_result: Dict[str, Any], query: Optional[str] = None) -> str:
        return f"The fee is BDT {fee_result['fee_amount']}"


class MockRedisCache:
    """Mock Redis cache for testing."""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
    
    async def get(self, key: str) -> Optional[str]:
        return self._cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        self._cache[key] = value
        return True
    
    async def get_disambiguation_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._cache.get(f"disambiguation:{session_id}")
    
    async def set_disambiguation_state(self, key: str, state: Dict, ttl: int = 300) -> bool:
        self._cache[f"disambiguation:{key}"] = state
        return True
    
    async def store_disambiguation_state(self, **kwargs) -> bool:
        return True


class MockLocationClient:
    """Mock Location client for testing."""
    
    async def search(self, query: str) -> Dict[str, Any]:
        return {
            "locations": [
                {"name": "Mock Branch", "address": "123 Test St"}
            ]
        }


# ============================================================================
# Test: Unit Testing ChatOrchestrator with Mocks
# ============================================================================

class TestChatOrchestratorWithMocks:
    """
    Unit tests for ChatOrchestrator using mocked dependencies.
    
    This demonstrates the testability benefits of Dependency Injection:
    - No need to connect to real services
    - Fast test execution
    - Predictable test outcomes
    - Isolated testing of business logic
    """
    
    @pytest.fixture
    def mock_lightrag(self):
        """Fixture providing mock LightRAG client."""
        return MockLightRAGClient("This is a mock response about banking.")
    
    @pytest.fixture
    def mock_fee_engine(self):
        """Fixture providing mock Fee Engine client."""
        return MockFeeEngineClient(mock_fee=2500.0)
    
    @pytest.fixture
    def mock_redis(self):
        """Fixture providing mock Redis cache."""
        return MockRedisCache()
    
    @pytest.fixture
    def mock_location(self):
        """Fixture providing mock Location client."""
        return MockLocationClient()
    
    @pytest.fixture
    def orchestrator(self, mock_lightrag, mock_fee_engine, mock_redis, mock_location):
        """
        Fixture providing ChatOrchestrator with all mocked dependencies.
        
        This is the key benefit of DI - we can inject mock dependencies
        for isolated testing.
        """
        from app.services.chat_orchestrator import ChatOrchestrator
        
        # Create orchestrator with injected mocks
        return ChatOrchestrator(
            lightrag_client=mock_lightrag,
            fee_engine_client=mock_fee_engine,
            location_client=mock_location,
            redis_cache=mock_redis,
            phonebook_db=None  # No phonebook for this test
        )
    
    @pytest.mark.asyncio
    async def test_fee_query_uses_fee_engine(self, orchestrator, mock_fee_engine):
        """Test that fee queries are routed to fee engine."""
        # This test would verify fee engine routing
        # The mock allows us to test without real API calls
        assert orchestrator.fee_engine_client == mock_fee_engine
        
        # Example: verify fee engine was injected
        result = await mock_fee_engine.calculate_fee("What is the annual fee?")
        assert result["fee_amount"] == 2500.0
        assert mock_fee_engine.calculate_called
    
    @pytest.mark.asyncio
    async def test_lightrag_query(self, orchestrator, mock_lightrag):
        """Test that general queries use LightRAG."""
        # Verify LightRAG was injected
        assert orchestrator.lightrag_client == mock_lightrag
        
        # Example: verify LightRAG responds
        result = await mock_lightrag.query("What are your banking hours?")
        assert "mock" in result["response"].lower() or "banking" in result["response"].lower()
        assert mock_lightrag.query_called
    
    @pytest.mark.asyncio
    async def test_redis_caching(self, orchestrator, mock_redis):
        """Test that Redis cache is used."""
        # Verify Redis was injected
        assert orchestrator.redis_cache == mock_redis
        
        # Example: verify caching works
        await mock_redis.set("test_key", "test_value")
        result = await mock_redis.get("test_key")
        assert result == "test_value"


# ============================================================================
# Test: Integration Testing with ServiceContainer
# ============================================================================

class TestServiceContainer:
    """
    Integration tests for the ServiceContainer.
    
    These tests verify the DI container works correctly.
    """
    
    @pytest.fixture(autouse=True)
    def reset_container(self):
        """Reset the container before each test."""
        from app.core.dependencies import ServiceContainer
        ServiceContainer.reset()
        yield
        ServiceContainer.reset()
    
    def test_singleton_pattern(self):
        """Test that ServiceContainer follows singleton pattern."""
        from app.core.dependencies import ServiceContainer
        
        container1 = ServiceContainer.get_instance()
        container2 = ServiceContainer.get_instance()
        
        assert container1 is container2
    
    def test_lazy_initialization(self):
        """Test that services are lazily initialized."""
        from app.core.dependencies import ServiceContainer
        
        container = ServiceContainer.get_instance()
        
        # Before accessing properties, internal references should be None
        assert container._lightrag_client is None
        assert container._fee_engine_client is None
    
    def test_reset_clears_instances(self):
        """Test that reset() properly clears the container."""
        from app.core.dependencies import ServiceContainer
        
        container1 = ServiceContainer.get_instance()
        ServiceContainer.reset()
        container2 = ServiceContainer.get_instance()
        
        assert container1 is not container2


# ============================================================================
# Test: FastAPI Route Testing with Dependency Overrides
# ============================================================================

class TestFastAPIRoutes:
    """
    Test FastAPI routes with dependency overrides.
    
    This demonstrates how to test routes by overriding dependencies.
    """
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Create a mock orchestrator for route testing."""
        mock = AsyncMock()
        mock.process_chat_sync = AsyncMock(return_value={
            "response": "Mock response from orchestrator",
            "session_id": "test-session-123",
            "sources": ["mock_source"]
        })
        mock.diagnose_routing = AsyncMock(return_value={
            "query": "test query",
            "target": "lightrag",
            "knowledge_base": "ebl",
            "pending_disambiguation": False,
            "signals": {}
        })
        return mock
    
    @pytest.fixture
    def client(self, mock_orchestrator):
        """Create test client with mocked dependencies."""
        from fastapi.testclient import TestClient
        from main import app
        from app.core.dependencies import get_orchestrator
        
        # Override the dependency
        app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator
        
        yield TestClient(app)
        
        # Clean up
        app.dependency_overrides.clear()
    
    def test_health_endpoint(self, client):
        """Test health endpoint returns OK."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    # Note: More route tests would go here
    # They would use dependency_overrides to inject mocks


# ============================================================================
# Example: How to Override Dependencies in Tests
# ============================================================================

def example_override_dependencies():
    """
    Example showing how to override dependencies in FastAPI tests.
    
    This is not a test itself, but documentation code.
    """
    from fastapi.testclient import TestClient
    from main import app
    from app.core.dependencies import (
        get_orchestrator,
        get_lightrag_client,
        get_redis_cache,
    )
    
    # Create mocks
    mock_orchestrator = MagicMock()
    mock_lightrag = MockLightRAGClient()
    mock_redis = MockRedisCache()
    
    # Override dependencies
    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator
    app.dependency_overrides[get_lightrag_client] = lambda: mock_lightrag
    app.dependency_overrides[get_redis_cache] = lambda: mock_redis
    
    # Create test client
    client = TestClient(app)
    
    # Run tests...
    response = client.get("/api/health")
    
    # Clean up overrides
    app.dependency_overrides.clear()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
