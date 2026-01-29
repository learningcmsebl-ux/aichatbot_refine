"""
Common/shared DTOs used across multiple modules.
"""

from enum import Enum
from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel, Field
from datetime import datetime


class StatusEnum(str, Enum):
    """Standard status values."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    SUCCESS = "success"
    ERROR = "error"


class BaseResponse(BaseModel):
    """Base response model with common fields."""
    status: StatusEnum = Field(..., description="Response status")
    message: Optional[str] = Field(None, description="Optional status message")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "success",
                "message": "Operation completed successfully"
            }
        }
    }


class ErrorResponse(BaseModel):
    """Standard error response."""
    status: StatusEnum = Field(default=StatusEnum.ERROR, description="Error status")
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    code: Optional[str] = Field(None, description="Error code for programmatic handling")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "error",
                "error": "Resource not found",
                "detail": "The requested session ID does not exist",
                "code": "SESSION_NOT_FOUND"
            }
        }
    }


T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=20, description="Items per page")
    has_more: bool = Field(default=False, description="Whether there are more items")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "has_more": True
            }
        }
    }


class TimestampMixin(BaseModel):
    """Mixin for models with timestamp fields."""
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
