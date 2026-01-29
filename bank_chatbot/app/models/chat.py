"""
Chat-related DTOs.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ChatRequest(BaseModel):
    """Chat request model."""
    query: str = Field(..., description="User's query or message", min_length=1, max_length=10000)
    session_id: Optional[str] = Field(None, description="Session ID for conversation history")
    knowledge_base: Optional[str] = Field(None, description="LightRAG knowledge base name")
    stream: bool = Field(True, description="Whether to stream the response")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "What are the fees for international wire transfer?",
                "session_id": "sess_abc123",
                "knowledge_base": None,
                "stream": True
            }
        }
    }


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str = Field(..., description="Assistant's response")
    session_id: str = Field(..., description="Session ID for the conversation")
    sources: Optional[List[str]] = Field(default=[], description="Knowledge base sources used")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "response": "The international wire transfer fee is $25 for outgoing transfers.",
                "session_id": "sess_abc123",
                "sources": ["banking_policies.pdf"]
            }
        }
    }


class ChatMessage(BaseModel):
    """Individual chat message in history."""
    id: int = Field(..., description="Message ID")
    role: str = Field(..., description="Message role (user/assistant)")
    message: str = Field(..., description="Message content")
    created_at: str = Field(..., description="Message timestamp (ISO format)")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "role": "user",
                "message": "What are your business hours?",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    }


class ChatHistoryResponse(BaseModel):
    """Chat history response."""
    session_id: str = Field(..., description="Session ID")
    messages: List[ChatMessage] = Field(default=[], description="List of messages in the conversation")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "sess_abc123",
                "messages": [
                    {
                        "id": 1,
                        "role": "user",
                        "message": "Hello",
                        "created_at": "2024-01-15T10:30:00Z"
                    },
                    {
                        "id": 2,
                        "role": "assistant",
                        "message": "Hello! How can I help you today?",
                        "created_at": "2024-01-15T10:30:01Z"
                    }
                ]
            }
        }
    }


class ClearHistoryResponse(BaseModel):
    """Response for clearing chat history."""
    session_id: str = Field(..., description="Session ID that was cleared")
    cleared: bool = Field(..., description="Whether the history was successfully cleared")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "sess_abc123",
                "cleared": True
            }
        }
    }


class RoutingSignals(BaseModel):
    """Routing decision signals/factors."""
    is_small_talk: bool = Field(default=False, description="Query is small talk")
    is_datetime_query: bool = Field(default=False, description="Query asks for date/time")
    is_fee_schedule_query: bool = Field(default=False, description="Query is about fees")
    is_location_query: bool = Field(default=False, description="Query is about locations")
    is_phonebook_query: bool = Field(default=False, description="Query is about phonebook")
    has_disambiguation: bool = Field(default=False, description="Has pending disambiguation")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "is_small_talk": False,
                "is_datetime_query": False,
                "is_fee_schedule_query": True,
                "is_location_query": False,
                "is_phonebook_query": False,
                "has_disambiguation": False
            }
        }
    }


class RouteDebugResponse(BaseModel):
    """Routing debug response model."""
    query: str = Field(..., description="The query being routed")
    target: str = Field(..., description="Routing target (e.g., FEE_ENGINE, LIGHTRAG)")
    knowledge_base: str = Field(..., description="Selected knowledge base")
    pending_disambiguation: bool = Field(..., description="Whether disambiguation is pending")
    signals: Dict[str, Any] = Field(default_factory=dict, description="Routing decision signals")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "wire transfer fee",
                "target": "FEE_ENGINE",
                "knowledge_base": "fee_schedule",
                "pending_disambiguation": False,
                "signals": {
                    "is_fee_schedule_query": True,
                    "is_location_query": False
                }
            }
        }
    }
