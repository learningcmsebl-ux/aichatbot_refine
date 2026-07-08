"""Semantic intent router built directly on local ONNX embeddings (fastembed).

Design goals:
- On-prem, CPU-only, no LLM, no external API calls, no GPU.
- Expose raw similarity *scores* so callers can run in shadow mode, log
  agreement against the legacy regex classifier, and tune a threshold.
- Lazy, fault-tolerant loading: if the model or fastembed is unavailable, the
  router degrades to "no confident decision" instead of raising, so the caller
  always falls back to the existing regex classifier.

Classification method: embed every route's example utterances once at startup,
L2-normalize them, and at query time embed the query and take, per route, the
maximum cosine similarity to that route's utterances. The best-scoring route
wins if its score clears ``threshold``; otherwise the result is not confident.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .routes import ROUTE_UTTERANCES

logger = logging.getLogger(__name__)


@dataclass
class SemanticClassification:
    """Result of a semantic classification."""

    target: Optional[str]
    score: float
    is_confident: bool
    scores_by_route: Dict[str, float] = field(default_factory=dict)

    @property
    def runner_up(self) -> Optional[str]:
        """Second-best route target (useful for margin/ambiguity analysis)."""
        ranked = sorted(self.scores_by_route.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[1][0] if len(ranked) > 1 else None

    @property
    def margin(self) -> float:
        """Score gap between best and second-best route."""
        ranked = sorted(self.scores_by_route.values(), reverse=True)
        return float(ranked[0] - ranked[1]) if len(ranked) > 1 else float(ranked[0]) if ranked else 0.0


class SemanticIntentRouter:
    """Embedding-based intent router. Thread-safe, lazy-loading singleton-friendly."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        cache_dir: Optional[str] = None,
        threshold: float = 0.62,
        route_utterances: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.threshold = threshold
        self._route_utterances = route_utterances or ROUTE_UTTERANCES

        self._lock = threading.Lock()
        self._loaded = False
        self._load_failed = False
        self._model = None
        self._np = None
        # Flat utterance vectors + parallel route-label list.
        self._utt_vecs = None  # np.ndarray (N, D), L2-normalized
        self._utt_routes: List[str] = []
        self._route_slices: Dict[str, List[int]] = {}

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #
    def _ensure_loaded(self) -> bool:
        """Load the embedding model and precompute utterance vectors once."""
        if self._loaded:
            return True
        if self._load_failed:
            return False
        with self._lock:
            if self._loaded:
                return True
            if self._load_failed:
                return False
            try:
                import numpy as np
                from fastembed import TextEmbedding

                self._np = np
                logger.info(
                    "[SEMANTIC_ROUTER] Loading embedding model '%s' (cache_dir=%s)",
                    self.model_name,
                    self.cache_dir,
                )
                self._model = TextEmbedding(
                    model_name=self.model_name,
                    cache_dir=self.cache_dir,
                )

                utterances: List[str] = []
                routes: List[str] = []
                for target, examples in self._route_utterances.items():
                    for example in examples:
                        utterances.append(example)
                        routes.append(target)

                vectors = np.array(list(self._model.embed(utterances)), dtype=np.float32)
                norms = np.linalg.norm(vectors, axis=1, keepdims=True)
                self._utt_vecs = vectors / np.clip(norms, 1e-12, None)
                self._utt_routes = routes

                slices: Dict[str, List[int]] = {}
                for idx, target in enumerate(routes):
                    slices.setdefault(target, []).append(idx)
                self._route_slices = slices

                self._loaded = True
                logger.info(
                    "[SEMANTIC_ROUTER] Ready: %s routes, %s utterances, dim=%s",
                    len(self._route_slices),
                    len(utterances),
                    self._utt_vecs.shape[1] if self._utt_vecs is not None else "?",
                )
                return True
            except Exception as exc:  # noqa: BLE001 - degrade gracefully
                self._load_failed = True
                logger.error(
                    "[SEMANTIC_ROUTER] Failed to load (falling back to regex classifier): %s",
                    exc,
                    exc_info=True,
                )
                return False

    @property
    def available(self) -> bool:
        """True if the router is ready or can be loaded."""
        return self._ensure_loaded()

    def warmup(self) -> bool:
        """Eagerly load the model (e.g., at app startup). Returns success."""
        return self._ensure_loaded()

    # ------------------------------------------------------------------ #
    # Classification
    # ------------------------------------------------------------------ #
    def classify(self, query: str) -> SemanticClassification:
        """Classify a query into a routing target with a confidence score."""
        query = (query or "").strip()
        if not query or not self._ensure_loaded():
            return SemanticClassification(target=None, score=0.0, is_confident=False)

        try:
            np = self._np
            qv = next(iter(self._model.embed([query])))
            qv = np.asarray(qv, dtype=np.float32)
            qv = qv / max(float(np.linalg.norm(qv)), 1e-12)

            sims = self._utt_vecs @ qv  # (N,)

            scores_by_route: Dict[str, float] = {}
            for target, idxs in self._route_slices.items():
                scores_by_route[target] = float(sims[idxs].max())

            best_target = max(scores_by_route, key=scores_by_route.get)
            best_score = scores_by_route[best_target]
            is_confident = best_score >= self.threshold

            return SemanticClassification(
                target=best_target if is_confident else None,
                score=best_score,
                is_confident=is_confident,
                scores_by_route=scores_by_route,
            )
        except Exception as exc:  # noqa: BLE001 - never break routing
            logger.error("[SEMANTIC_ROUTER] classify() error: %s", exc, exc_info=True)
            return SemanticClassification(target=None, score=0.0, is_confident=False)


# ---------------------------------------------------------------------- #
# Singleton accessor
# ---------------------------------------------------------------------- #
_router_instance: Optional[SemanticIntentRouter] = None
_router_lock = threading.Lock()


def get_semantic_router() -> SemanticIntentRouter:
    """Return the process-wide SemanticIntentRouter, built from settings."""
    global _router_instance
    if _router_instance is not None:
        return _router_instance
    with _router_lock:
        if _router_instance is None:
            try:
                from app.core.config import settings

                model_name = getattr(settings, "SEMANTIC_ROUTER_MODEL", "BAAI/bge-small-en-v1.5")
                cache_dir = getattr(settings, "FASTEMBED_CACHE_DIR", None) or None
                threshold = float(getattr(settings, "SEMANTIC_ROUTER_THRESHOLD", 0.62))
            except Exception:  # noqa: BLE001 - allow standalone use without settings
                model_name, cache_dir, threshold = "BAAI/bge-small-en-v1.5", None, 0.62
            _router_instance = SemanticIntentRouter(
                model_name=model_name,
                cache_dir=cache_dir,
                threshold=threshold,
            )
    return _router_instance
