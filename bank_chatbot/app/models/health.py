"""
Health check DTOs.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from app.models.common import StatusEnum


class HealthResponse(BaseModel):
    """Basic health check response."""
    status: StatusEnum = Field(..., description="Service health status")
    service: str = Field(..., description="Service name")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "service": "Bank Chatbot API"
            }
        }
    }


class ComponentHealth(BaseModel):
    """Health status for an individual component."""
    status: StatusEnum = Field(..., description="Component health status")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional health details")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "error": None,
                "details": None
            }
        }
    }


class LightRAGHealth(BaseModel):
    """LightRAG component health details."""
    status: StatusEnum = Field(..., description="LightRAG status")
    working_directory: Optional[str] = Field(None, description="RAG working directory")
    input_directory: Optional[str] = Field(None, description="Input documents directory")
    configuration: Optional[Dict[str, Any]] = Field(None, description="RAG configuration")
    auth_mode: Optional[str] = Field(None, description="Authentication mode")
    pipeline_busy: Optional[bool] = Field(None, description="Whether pipeline is busy")
    keyed_locks: Optional[Dict[str, Any]] = Field(None, description="Lock status")
    core_version: Optional[str] = Field(None, description="LightRAG core version")
    api_version: Optional[str] = Field(None, description="API version")
    webui_title: Optional[str] = Field(None, description="WebUI title")
    webui_description: Optional[str] = Field(None, description="WebUI description")


class DetailedHealthResponse(BaseModel):
    """Detailed health check response with component status."""
    status: StatusEnum = Field(..., description="Overall service health status")
    service: str = Field(..., description="Service name")
    components: Dict[str, ComponentHealth] = Field(
        default_factory=dict,
        description="Health status of individual components"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "service": "Bank Chatbot API",
                "components": {
                    "lightrag": {
                        "status": "healthy",
                        "details": {"core_version": "v1.4.9"}
                    },
                    "redis": {"status": "healthy"},
                    "postgresql": {"status": "healthy"}
                }
            }
        }
    }
