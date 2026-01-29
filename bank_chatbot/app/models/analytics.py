"""
Analytics DTOs.
"""

from typing import Optional, List, Any
from pydantic import BaseModel, Field
from datetime import date


class DailyMetric(BaseModel):
    """Daily performance metric."""
    date: str = Field(..., description="Date (ISO format)")
    total_conversations: int = Field(..., description="Total conversations on this day")
    answered_count: int = Field(..., description="Number of answered questions")
    unanswered_count: int = Field(..., description="Number of unanswered questions")
    avg_response_time_ms: Optional[float] = Field(None, description="Average response time in milliseconds")
    answer_rate: float = Field(..., description="Answer rate percentage")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "date": "2024-01-15",
                "total_conversations": 150,
                "answered_count": 140,
                "unanswered_count": 10,
                "avg_response_time_ms": 450.5,
                "answer_rate": 93.33
            }
        }
    }


class OverallMetrics(BaseModel):
    """Overall performance metrics summary."""
    total_conversations: int = Field(..., description="Total conversations in period")
    total_answered: int = Field(..., description="Total answered questions")
    total_unanswered: int = Field(..., description="Total unanswered questions")
    overall_answer_rate: float = Field(..., description="Overall answer rate percentage")
    avg_response_time_ms: float = Field(..., description="Average response time in milliseconds")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "total_conversations": 4500,
                "total_answered": 4200,
                "total_unanswered": 300,
                "overall_answer_rate": 93.33,
                "avg_response_time_ms": 425.0
            }
        }
    }


class PerformanceMetricsResponse(BaseModel):
    """Performance metrics response."""
    period_days: int = Field(..., description="Number of days in the reporting period")
    overall: OverallMetrics = Field(..., description="Overall metrics summary")
    daily_metrics: List[DailyMetric] = Field(default=[], description="Daily breakdown of metrics")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "period_days": 30,
                "overall": {
                    "total_conversations": 4500,
                    "total_answered": 4200,
                    "total_unanswered": 300,
                    "overall_answer_rate": 93.33,
                    "avg_response_time_ms": 425.0
                },
                "daily_metrics": []
            }
        }
    }


class MostAskedQuestion(BaseModel):
    """Most frequently asked question statistics."""
    question: str = Field(..., description="The question text")
    normalized: Optional[str] = Field(None, description="Normalized question for grouping")
    total_asked: int = Field(..., description="Total times this question was asked")
    answered_count: int = Field(..., description="Times it was answered")
    unanswered_count: int = Field(..., description="Times it was not answered")
    answer_rate: float = Field(..., description="Answer rate percentage")
    last_asked: Optional[str] = Field(None, description="Last time this question was asked (ISO format)")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "What are your business hours?",
                "normalized": "what are your business hours",
                "total_asked": 150,
                "answered_count": 148,
                "unanswered_count": 2,
                "answer_rate": 98.67,
                "last_asked": "2024-01-15T10:30:00Z"
            }
        }
    }


class MostAskedQuestionsResponse(BaseModel):
    """Response containing most asked questions."""
    questions: List[MostAskedQuestion] = Field(default=[], description="List of most asked questions")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "questions": [
                    {
                        "question": "What are your business hours?",
                        "total_asked": 150,
                        "answered_count": 148,
                        "unanswered_count": 2,
                        "answer_rate": 98.67,
                        "last_asked": "2024-01-15T10:30:00Z"
                    }
                ]
            }
        }
    }


class UnansweredQuestion(BaseModel):
    """Unanswered question statistics."""
    question: str = Field(..., description="The question text")
    normalized: Optional[str] = Field(None, description="Normalized question for grouping")
    unanswered_count: int = Field(..., description="Number of times unanswered")
    total_asked: int = Field(..., description="Total times asked")
    last_asked: Optional[str] = Field(None, description="Last time asked (ISO format)")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "Do you offer cryptocurrency accounts?",
                "normalized": "do you offer cryptocurrency accounts",
                "unanswered_count": 25,
                "total_asked": 30,
                "last_asked": "2024-01-15T14:20:00Z"
            }
        }
    }


class UnansweredQuestionsResponse(BaseModel):
    """Response containing unanswered questions."""
    questions: List[UnansweredQuestion] = Field(default=[], description="List of unanswered questions")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "questions": [
                    {
                        "question": "Do you offer cryptocurrency accounts?",
                        "unanswered_count": 25,
                        "total_asked": 30,
                        "last_asked": "2024-01-15T14:20:00Z"
                    }
                ]
            }
        }
    }


class ConversationRecord(BaseModel):
    """Individual conversation record."""
    id: int = Field(..., description="Record ID")
    session_id: str = Field(..., description="Session ID")
    user_message: str = Field(..., description="User's message")
    assistant_response: str = Field(..., description="Assistant's response")
    is_answered: bool = Field(..., description="Whether the question was answered")
    knowledge_base: Optional[str] = Field(None, description="Knowledge base used")
    routing_target: Optional[str] = Field(None, description="Routing target (FEE_ENGINE, LIGHTRAG, etc.)")
    response_time_ms: Optional[int] = Field(None, description="Response time in milliseconds")
    client_ip: Optional[str] = Field(None, description="Client IP address")
    created_at: Optional[str] = Field(None, description="Creation timestamp (ISO format)")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "session_id": "sess_abc123",
                "user_message": "What is the wire transfer fee?",
                "assistant_response": "The wire transfer fee is $25.",
                "is_answered": True,
                "knowledge_base": "fee_schedule",
                "routing_target": "FEE_ENGINE",
                "response_time_ms": 350,
                "client_ip": "192.168.1.100",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    }


class ConversationHistoryResponse(BaseModel):
    """Response containing conversation history."""
    conversations: List[ConversationRecord] = Field(
        default=[],
        description="List of conversation records"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "conversations": [
                    {
                        "id": 1,
                        "session_id": "sess_abc123",
                        "user_message": "What is the wire transfer fee?",
                        "assistant_response": "The wire transfer fee is $25.",
                        "is_answered": True,
                        "routing_target": "FEE_ENGINE",
                        "created_at": "2024-01-15T10:30:00Z"
                    }
                ]
            }
        }
    }


class RoutingDistributionItem(BaseModel):
    """Routing distribution for a specific target."""
    routing_target: str = Field(..., description="Routing target name")
    count: int = Field(..., description="Number of queries routed to this target")
    percentage: float = Field(..., description="Percentage of total queries")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "routing_target": "FEE_ENGINE",
                "count": 1200,
                "percentage": 35.5
            }
        }
    }


class RoutingDistributionResponse(BaseModel):
    """Routing distribution statistics response."""
    period_days: int = Field(..., description="Number of days in the reporting period")
    distribution: List[RoutingDistributionItem] = Field(
        default=[],
        description="Distribution of queries across routing targets"
    )
    total: int = Field(..., description="Total number of queries")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "period_days": 30,
                "distribution": [
                    {"routing_target": "LIGHTRAG", "count": 2000, "percentage": 44.4},
                    {"routing_target": "FEE_ENGINE", "count": 1500, "percentage": 33.3},
                    {"routing_target": "LOCATION", "count": 500, "percentage": 11.1},
                    {"routing_target": "PHONEBOOK", "count": 300, "percentage": 6.7},
                    {"routing_target": "SMALL_TALK", "count": 200, "percentage": 4.5}
                ],
                "total": 4500
            }
        }
    }


class TestConversationLogResponse(BaseModel):
    """Response for test conversation log endpoint."""
    status: str = Field(..., description="Operation status")
    message: str = Field(..., description="Status message")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "success",
                "message": "Test ConversationLog record created successfully"
            }
        }
    }


class ConversationLogCheckRecord(BaseModel):
    """Individual record in conversation log check."""
    id: int = Field(..., description="Record ID")
    session_id: str = Field(..., description="Session ID")
    client_ip: Optional[str] = Field(None, description="Client IP")
    created_at: Optional[str] = Field(None, description="Creation timestamp")


class ConversationLogCheckResponse(BaseModel):
    """Response for checking conversation log table."""
    status: str = Field(..., description="Check status")
    table_exists: bool = Field(..., description="Whether the table exists")
    record_count: int = Field(..., description="Number of records in table")
    recent_records: List[ConversationLogCheckRecord] = Field(
        default=[],
        description="Recent records"
    )
    available_tables: List[str] = Field(default=[], description="Available database tables")
    message: Optional[str] = Field(None, description="Error message if applicable")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "success",
                "table_exists": True,
                "record_count": 4500,
                "recent_records": [
                    {
                        "id": 4500,
                        "session_id": "sess_xyz789",
                        "client_ip": "192.168.1.100",
                        "created_at": "2024-01-15T10:30:00Z"
                    }
                ],
                "available_tables": ["analytics_conversations", "analytics_questions"]
            }
        }
    }
