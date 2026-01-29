"""
Data Transfer Objects (DTOs) for the Bank Chatbot API.

These Pydantic models define clear contracts for API requests/responses,
enabling automatic validation, documentation, and type safety.
"""

from app.models.common import (
    BaseResponse,
    ErrorResponse,
    PaginatedResponse,
    StatusEnum,
)
from app.models.health import (
    HealthResponse,
    ComponentHealth,
    DetailedHealthResponse,
    LightRAGHealth,
)
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    ChatHistoryResponse,
    ClearHistoryResponse,
    RouteDebugResponse,
    RoutingSignals,
)
from app.models.analytics import (
    DailyMetric,
    OverallMetrics,
    PerformanceMetricsResponse,
    MostAskedQuestion,
    MostAskedQuestionsResponse,
    UnansweredQuestion,
    UnansweredQuestionsResponse,
    ConversationRecord,
    ConversationHistoryResponse,
    RoutingDistributionItem,
    RoutingDistributionResponse,
    TestConversationLogResponse,
    ConversationLogCheckResponse,
)
from app.models.location import (
    LocationAddress,
    Location,
    LocationFilters,
    LocationQueryResponse,
)
from app.models.fee_engine import (
    FeeCalculationRequest,
    FeeDetail,
    FeeCalculationResponse,
    SkybankingFeeResponse,
    RetailAssetChargeResponse,
)

__all__ = [
    # Common
    "BaseResponse",
    "ErrorResponse",
    "PaginatedResponse",
    "StatusEnum",
    # Health
    "HealthResponse",
    "ComponentHealth",
    "DetailedHealthResponse",
    "LightRAGHealth",
    # Chat
    "ChatRequest",
    "ChatResponse",
    "ChatMessage",
    "ChatHistoryResponse",
    "ClearHistoryResponse",
    "RouteDebugResponse",
    "RoutingSignals",
    # Analytics
    "DailyMetric",
    "OverallMetrics",
    "PerformanceMetricsResponse",
    "MostAskedQuestion",
    "MostAskedQuestionsResponse",
    "UnansweredQuestion",
    "UnansweredQuestionsResponse",
    "ConversationRecord",
    "ConversationHistoryResponse",
    "RoutingDistributionItem",
    "RoutingDistributionResponse",
    "TestConversationLogResponse",
    "ConversationLogCheckResponse",
    # Location
    "LocationAddress",
    "Location",
    "LocationFilters",
    "LocationQueryResponse",
    # Fee Engine
    "FeeCalculationRequest",
    "FeeDetail",
    "FeeCalculationResponse",
    "SkybankingFeeResponse",
    "RetailAssetChargeResponse",
]
