"""
Service Interfaces (Protocols) for Dependency Injection.

These protocols define the expected interface for each service,
enabling type-safe dependency injection and easier mocking.

Benefits:
- Type safety with static type checkers (mypy, pyright)
- Clear API contracts for services
- Easier mocking in tests
- Loose coupling between components

Usage:
    # Type hint function parameters with protocols
    def process_query(client: LightRAGClientProtocol) -> str:
        return client.query("...")
    
    # Create mock implementations
    class MockLightRAG(LightRAGClientProtocol):
        async def query(self, query: str, **kwargs) -> Dict[str, Any]:
            return {"response": "mock"}
"""

from typing import Protocol, Optional, Dict, Any, List, runtime_checkable
from datetime import date
from decimal import Decimal


@runtime_checkable
class LightRAGClientProtocol(Protocol):
    """Protocol for LightRAG client implementations."""
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if LightRAG service is healthy."""
        ...
    
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
        """Query the LightRAG knowledge base."""
        ...
    
    async def query_data(
        self,
        query: str,
        knowledge_base: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Query LightRAG with detailed data."""
        ...
    
    async def close(self) -> None:
        """Close the client connection."""
        ...


@runtime_checkable
class FeeEngineClientProtocol(Protocol):
    """Protocol for Fee Engine client implementations."""
    
    async def calculate_fee(
        self,
        query: str,
        amount: Optional[Decimal] = None,
        currency: Optional[str] = None,
        usage_index: Optional[int] = None,
        outstanding_balance: Optional[Decimal] = None
    ) -> Optional[Dict[str, Any]]:
        """Calculate fee for a query."""
        ...
    
    def format_fee_response(
        self,
        fee_result: Dict[str, Any],
        query: Optional[str] = None
    ) -> str:
        """Format fee calculation result into readable text."""
        ...


@runtime_checkable
class LocationClientProtocol(Protocol):
    """Protocol for Location service client implementations."""
    
    async def search_locations(
        self,
        query: str,
        location_type: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Search for locations matching query."""
        ...
    
    async def get_nearest_branch(
        self,
        latitude: float,
        longitude: float
    ) -> Optional[Dict[str, Any]]:
        """Get nearest branch to coordinates."""
        ...


@runtime_checkable
class RedisCacheProtocol(Protocol):
    """Protocol for Redis cache implementations."""
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        ...
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 300
    ) -> bool:
        """Set value with optional TTL."""
        ...
    
    async def delete(self, key: str) -> bool:
        """Delete key."""
        ...
    
    async def get_disambiguation_state(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get disambiguation state for session."""
        ...
    
    async def set_disambiguation_state(
        self,
        key: str,
        state: Dict[str, Any],
        ttl: int = 300
    ) -> bool:
        """Set disambiguation state."""
        ...
    
    async def store_disambiguation_state(
        self,
        session_id: str,
        product_line: str,
        charge_type: str,
        as_of_date: str,
        options: List[Dict[str, Any]],
        disambiguation_type: str,
        prompt_message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Store structured disambiguation state."""
        ...


@runtime_checkable
class PhonebookDBProtocol(Protocol):
    """Protocol for Phonebook database implementations."""
    
    def search_employees(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search employees by name or department."""
        ...
    
    def get_employee_by_id(
        self,
        employee_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get employee by ID."""
        ...


@runtime_checkable
class ChatOrchestratorProtocol(Protocol):
    """Protocol for Chat Orchestrator implementations."""
    
    async def process_chat(
        self,
        query: str,
        session_id: Optional[str] = None,
        knowledge_base: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> Any:  # AsyncGenerator
        """Process chat query with streaming response."""
        ...
    
    async def process_chat_sync(
        self,
        query: str,
        session_id: Optional[str] = None,
        knowledge_base: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process chat query with synchronous response."""
        ...
    
    async def diagnose_routing(
        self,
        query: str,
        session_id: Optional[str] = None,
        knowledge_base: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Diagnose routing decision for query."""
        ...
    
    async def close(self) -> None:
        """Close all client connections."""
        ...
