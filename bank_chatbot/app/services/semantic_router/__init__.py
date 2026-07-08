"""Semantic (embedding-based) intent router.

Provides a lightweight, on-prem alternative to the large regex/keyword
QueryClassifier. Uses local ONNX embeddings (fastembed) on CPU — no LLM,
no GPU, no external API calls.

Feature-flagged via settings.ENABLE_SEMANTIC_ROUTER. When disabled, importing
this package has no effect on routing behaviour.
"""

from .router import (
    SemanticIntentRouter,
    SemanticClassification,
    get_semantic_router,
)
from .routes import ROUTE_UTTERANCES, ROUTE_TARGETS

__all__ = [
    "SemanticIntentRouter",
    "SemanticClassification",
    "get_semantic_router",
    "ROUTE_UTTERANCES",
    "ROUTE_TARGETS",
]
