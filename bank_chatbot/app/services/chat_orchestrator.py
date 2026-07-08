"""
Chat Orchestrator - Coordinates all components for chat processing.

Supports Dependency Injection for loose coupling and testability.

Refactored to use handler classes (addressing God Object anti-pattern):
- QueryClassifier: Query type detection (_is_*_query methods)
- ResponseFormatter: Response formatting and text transformations
- DisambiguationHandler: Disambiguation state management
"""

from __future__ import annotations  # Enable forward references for type hints

import uuid
import logging
import re
import contextvars
from typing import Optional, AsyncGenerator, List, Dict, Any, TYPE_CHECKING
from datetime import datetime
import pytz

from openai import AsyncOpenAI
import httpx

from app.core.config import settings
from app.database.postgres import PostgresChatMemory, get_db
from app.database.redis_client import RedisCache, get_cache_key

# Import extracted handlers (God Object refactoring)
from app.services.handlers import (
    QueryClassifier,
    ResponseFormatter,
    DisambiguationHandler,
    LeadCaptureHandler,
    PhonebookHandler,
    FormsHandler,
    AppLinksHandler,
    LeadershipHandler,
    SocHandler,
    ProposalsHandler,
    CircularsHandler,
)
from app.services.handlers.fee_query_utils import normalize_fee_query_for_matching

# Type hints for dependency injection (avoid circular imports)
if TYPE_CHECKING:
    from app.services.fee_engine_client import FeeEngineClient
    from app.models.auth import EmployeeUser

logger = logging.getLogger(__name__)

# Request-scoped authenticated identity for the current chat turn.
#
# The orchestrator is a shared singleton, so we use a ContextVar (async-safe,
# isolated per request/task) to carry the AD-authenticated identity from the
# public entrypoints down to the persistence layer without threading it through
# every internal call site. It is ALWAYS populated from the backend EmployeeUser
# (JWT/session), never from client-supplied data.
_current_identity: contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar(
    "current_chat_identity", default=None
)

# Analytics logging (optional - will fail gracefully if not available)
try:
    from app.services.analytics import log_conversation
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False
    def log_conversation(*args, **kwargs):
        pass  # No-op if analytics not available
from app.services.lightrag_client import LightRAGClient
from app.services.location_client import LocationClient
from app.services.location_intent import get_location_intent_flags
from app.services.routing_engine import RoutingEngine

# Import phonebook + EBL Home forms indexes (PostgreSQL)
try:
    import sys
    import os
    services_dir = os.path.dirname(os.path.abspath(__file__))
    if services_dir not in sys.path:
        sys.path.insert(0, services_dir)
    from phonebook_postgres import get_phonebook_db
    from ebl_forms_postgres import get_ebl_forms_db
    from ebl_apps_postgres import get_ebl_apps_db
    from ebl_leadership_postgres import get_ebl_leadership_db
    from ebl_soc_postgres import get_ebl_soc_db
    from ebl_proposals_postgres import get_ebl_proposals_db
    from ebl_circulars_postgres import get_ebl_circulars_db
    PHONEBOOK_DB_AVAILABLE = True
    EBL_FORMS_DB_AVAILABLE = True
    EBL_APPS_DB_AVAILABLE = True
    EBL_LEADERSHIP_DB_AVAILABLE = True
    EBL_SOC_DB_AVAILABLE = True
    EBL_PROPOSALS_DB_AVAILABLE = True
    EBL_CIRCULARS_DB_AVAILABLE = True
except ImportError as e:
    PHONEBOOK_DB_AVAILABLE = False
    EBL_FORMS_DB_AVAILABLE = False
    EBL_APPS_DB_AVAILABLE = False
    EBL_LEADERSHIP_DB_AVAILABLE = False
    EBL_SOC_DB_AVAILABLE = False
    EBL_PROPOSALS_DB_AVAILABLE = False
    EBL_CIRCULARS_DB_AVAILABLE = False
    logger.warning(f"[WARN] Phonebook/EBL Home database modules not available: {e}")


class ChatOrchestrator:
    """
    Orchestrates chat processing with PostgreSQL, Redis, and LightRAG.
    
    Supports Dependency Injection for better testability and loose coupling.
    Dependencies can be injected via constructor or will be created with defaults.
    
    Example with DI:
        orchestrator = ChatOrchestrator(
            lightrag_client=mock_lightrag,
            fee_engine_client=mock_fee_engine,
            location_client=mock_location,
            redis_cache=mock_redis
        )
    
    Example without DI (backward compatible):
        orchestrator = ChatOrchestrator()  # Creates all dependencies internally
    """
    
    # Constants for repeated strings
    OFFICIAL_CARD_RATES_HEADER = "OFFICIAL CARD RATES AND FEES INFORMATION"
    OFFICIAL_RETAIL_ASSET_HEADER = "OFFICIAL RETAIL ASSET CHARGES INFORMATION"
    OFFICIAL_SKYBANKING_HEADER = "OFFICIAL SKYBANKING FEES INFORMATION"
    FEE_ENGINE_SOURCE = "Source: Fee Engine (Card Charges and Fees Schedule - Effective from 01st January, 2026)"
    FEE_ENGINE_SOURCE_RETAIL = "Source: Fee Engine (Retail Asset Charges Schedule)"
    FEE_ENGINE_SOURCE_SKYBANKING = "Source: Fee Engine (Skybanking Fees Schedule)"

    # Prompt sizing guards (Phase 5)
    # These are intentionally generous; they only activate when prompt add-ons become excessively large.
    MAX_SINGLE_REMINDER_CHARS = 4000
    MAX_TOTAL_PROMPT_ADDONS_CHARS = 12000
    SOURCES_MARKER_PREFIX = "\n\n__SOURCES__"
    SOURCES_MARKER_SUFFIX = "__SOURCES__"
    UNGROUNDED_RESPONSE = (
        "I could not find reliable information in the knowledge base for that question. "
        "Please rephrase your question, provide more detail (such as the product, account, or policy name), "
        "or contact the related department or unit for this specific detail if needed."
    )
    
    def __init__(
        self,
        *,
        lightrag_client: Optional["LightRAGClient"] = None,
        fee_engine_client: Optional["FeeEngineClient"] = None,
        location_client: Optional["LocationClient"] = None,
        redis_cache: Optional["RedisCache"] = None,
        phonebook_db: Optional[Any] = None,
        forms_db: Optional[Any] = None,
        apps_db: Optional[Any] = None,
        leadership_db: Optional[Any] = None,
        soc_db: Optional[Any] = None,
        proposals_db: Optional[Any] = None,
        circulars_db: Optional[Any] = None,
        openai_client: Optional[AsyncOpenAI] = None,
    ):
        """
        Initialize ChatOrchestrator with optional dependency injection.
        
        Args:
            lightrag_client: LightRAG client instance (optional, creates default if not provided)
            fee_engine_client: Fee Engine client instance (optional, creates default if not provided)
            location_client: Location service client instance (optional, creates default if not provided)
            redis_cache: Redis cache instance (optional, creates default if not provided)
            phonebook_db: Phonebook database instance (optional, uses global if not provided)
            forms_db: EBL Home forms index instance (optional, uses global if not provided)
            openai_client: OpenAI async client instance (optional, creates default if not provided)
        """
        # OpenAI client (for LLM responses)
        self.openai_client = openai_client or AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Inject dependencies or create defaults
        self.lightrag_client = lightrag_client or LightRAGClient()
        self.redis_cache = redis_cache or RedisCache()
        self.location_client = location_client or LocationClient()
        
        # Fee engine client - lazy import to avoid circular dependency
        if fee_engine_client is not None:
            self.fee_engine_client = fee_engine_client
        else:
            from app.services.fee_engine_client import FeeEngineClient
            self.fee_engine_client = FeeEngineClient()
        
        # Phonebook database
        self._phonebook_db = phonebook_db  # Can be None, will use global instance
        self._forms_db = forms_db
        self._apps_db = apps_db
        self._leadership_db = leadership_db
        self._soc_db = soc_db
        self._proposals_db = proposals_db
        self._circulars_db = circulars_db

        # Other initialization
        self.system_message = self._get_system_message()

        # Determine phonebook availability
        phonebook_available = PHONEBOOK_DB_AVAILABLE
        if phonebook_db is not None:
            phonebook_available = True

        forms_available = EBL_FORMS_DB_AVAILABLE and settings.ENABLE_EBLHOME_FORMS
        if forms_db is not None:
            forms_available = True

        apps_available = EBL_APPS_DB_AVAILABLE and settings.ENABLE_EBLHOME_APPS
        if apps_db is not None:
            apps_available = True

        leadership_available = EBL_LEADERSHIP_DB_AVAILABLE and settings.ENABLE_EBLHOME_LEADERSHIP
        if leadership_db is not None:
            leadership_available = True

        soc_available = EBL_SOC_DB_AVAILABLE and settings.ENABLE_EBLHOME_SOC
        if soc_db is not None:
            soc_available = True

        proposals_available = EBL_PROPOSALS_DB_AVAILABLE and settings.ENABLE_EBLHOME_PROPOSALS
        if proposals_db is not None:
            proposals_available = True

        circulars_available = EBL_CIRCULARS_DB_AVAILABLE and settings.ENABLE_EBLHOME_CIRCULARS
        if circulars_db is not None:
            circulars_available = True

        self.routing_engine = RoutingEngine(
            self,
            phonebook_db_available=phonebook_available,
            forms_db_available=forms_available,
            apps_db_available=apps_available,
            leadership_db_available=leadership_available,
            soc_db_available=soc_available,
            proposals_db_available=proposals_available,
            circulars_db_available=circulars_available,
        )
        
        # Initialize extracted handler classes (God Object refactoring)
        # These handlers delegate specific responsibilities for cleaner code
        self.query_classifier = QueryClassifier(
            location_intent_getter=get_location_intent_flags
        )
        self.response_formatter = ResponseFormatter(timezone="Asia/Dhaka")
        self.disambiguation_handler = DisambiguationHandler(redis_cache=self.redis_cache)
        self.lead_capture_handler = LeadCaptureHandler(redis_cache=self.redis_cache)
        self.phonebook_handler = PhonebookHandler()
        self.forms_handler = FormsHandler()
        self.app_links_handler = AppLinksHandler()
        self.leadership_handler = LeadershipHandler()
        self.soc_handler = SocHandler()
        self.proposals_handler = ProposalsHandler()
        self.circulars_handler = CircularsHandler()
        
        # Fallback disambiguation store (used when Redis is unavailable).
        # Key: conversation_key/session_id, Value: {"state": <dict>, "expires_at": <unix_ts>}
        self._local_disambiguation_state: Dict[str, Dict[str, Any]] = {}
        
        logger.info(
            f"ChatOrchestrator initialized - "
            f"LightRAG: {'injected' if lightrag_client else 'default'}, "
            f"FeeEngine: {'injected' if fee_engine_client else 'default'}, "
            f"Location: {'injected' if location_client else 'default'}, "
            f"Redis: {'injected' if redis_cache else 'default'}, "
            f"Phonebook: {'injected' if phonebook_db else 'global'}, "
            f"Forms: {'injected' if forms_db else ('enabled' if forms_available else 'disabled')}, "
            f"Apps: {'injected' if apps_db else ('enabled' if apps_available else 'disabled')}, "
            f"Leadership: {'injected' if leadership_db else ('enabled' if leadership_available else 'disabled')}, "
            f"SOC: {'injected' if soc_db else ('enabled' if soc_available else 'disabled')}, "
            f"Proposals: {'injected' if proposals_db else ('enabled' if proposals_available else 'disabled')}, "
            f"Circulars: {'injected' if circulars_db else ('enabled' if circulars_available else 'disabled')}, "
            f"Handlers: QueryClassifier, ResponseFormatter, DisambiguationHandler"
        )
    
    @property
    def phonebook_db(self):
        """Get phonebook database instance (injected or global)."""
        if self._phonebook_db is not None:
            return self._phonebook_db
        # Fallback to global instance
        if PHONEBOOK_DB_AVAILABLE:
            return get_phonebook_db()
        return None

    @property
    def forms_db(self):
        """Get EBL Home forms index instance (injected or global)."""
        if self._forms_db is not None:
            return self._forms_db
        if EBL_FORMS_DB_AVAILABLE and settings.ENABLE_EBLHOME_FORMS:
            return get_ebl_forms_db()
        return None

    @property
    def apps_db(self):
        """Get EBL Home applications index instance (injected or global)."""
        if self._apps_db is not None:
            return self._apps_db
        if EBL_APPS_DB_AVAILABLE and settings.ENABLE_EBLHOME_APPS:
            return get_ebl_apps_db()
        return None

    @property
    def leadership_db(self):
        """Get EBL Home leadership index instance (injected or global)."""
        if self._leadership_db is not None:
            return self._leadership_db
        if EBL_LEADERSHIP_DB_AVAILABLE and settings.ENABLE_EBLHOME_LEADERSHIP:
            return get_ebl_leadership_db()
        return None

    @property
    def soc_db(self):
        if self._soc_db is not None:
            return self._soc_db
        if EBL_SOC_DB_AVAILABLE and settings.ENABLE_EBLHOME_SOC:
            return get_ebl_soc_db()
        return None

    @property
    def proposals_db(self):
        if self._proposals_db is not None:
            return self._proposals_db
        if EBL_PROPOSALS_DB_AVAILABLE and settings.ENABLE_EBLHOME_PROPOSALS:
            return get_ebl_proposals_db()
        return None

    @property
    def circulars_db(self):
        if self._circulars_db is not None:
            return self._circulars_db
        if EBL_CIRCULARS_DB_AVAILABLE and settings.ENABLE_EBLHOME_CIRCULARS:
            return get_ebl_circulars_db()
        return None

    def _local_disambiguation_cleanup(self) -> None:
        """Remove expired local disambiguation entries."""
        try:
            import time
            now_ts = time.time()
            expired = [k for k, v in self._local_disambiguation_state.items() if v.get("expires_at", 0) <= now_ts]
            for k in expired:
                self._local_disambiguation_state.pop(k, None)
        except Exception:
            return

    async def _store_disambiguation_state_fallback(
        self,
        state_key: str,
        state: Dict[str, Any],
        ttl_seconds: int = 300,
    ) -> None:
        """Store disambiguation state locally when Redis is unavailable."""
        import time
        self._local_disambiguation_cleanup()
        self._local_disambiguation_state[state_key] = {
            "state": state,
            "expires_at": time.time() + ttl_seconds,
        }

    async def _set_disambiguation_state_any(
        self,
        state_key: str,
        state: Dict[str, Any],
        ttl_seconds: int = 300,
    ) -> None:
        """Set disambiguation state in Redis if available; fall back to local store on error."""
        try:
            await self.redis_cache.set_disambiguation_state(state_key, state, ttl=ttl_seconds)
        except Exception as e:
            logger.warning(f"[DISAMBIGUATION] Redis set failed for key='{state_key}', using local fallback: {e}")
            await self._store_disambiguation_state_fallback(state_key, state, ttl_seconds=ttl_seconds)

    async def _store_disambiguation_state_any(
        self,
        *,
        state_key: str,
        product_line: str,
        charge_type: str,
        as_of_date: str,
        options: List[Dict[str, Any]],
        disambiguation_type: str,
        prompt_message: str,
        extra: Optional[Dict[str, Any]] = None,
        ttl_seconds: int = 300,
    ) -> None:
        """
        Store disambiguation state in Redis when possible; fall back to local in-process state on error.
        """
        try:
            stored = await self.redis_cache.store_disambiguation_state(
                session_id=state_key,
                product_line=product_line,
                charge_type=charge_type,
                as_of_date=as_of_date,
                options=options,
                disambiguation_type=disambiguation_type,
                prompt_message=prompt_message,
                extra=extra,
            )
        except Exception as e:
            stored = False
            logger.warning(f"[DISAMBIGUATION] Redis store failed for conversation_key {state_key}; using local fallback: {e}")

        if stored:
            return

        await self._store_disambiguation_state_fallback(
            state_key=state_key,
            state={
                "product_line": product_line,
                "charge_type": charge_type,
                "as_of_date": as_of_date,
                "options": options,
                "disambiguation_type": disambiguation_type,
                "prompt_message": prompt_message,
                **({"extra": extra} if extra is not None else {}),
            },
            ttl_seconds=ttl_seconds,
        )

    def _format_sources_marker(self, sources: List[str]) -> str:
        """Format sources as a trailing marker chunk (frontend parses this)."""
        try:
            import json
            sources_json = json.dumps({"type": "sources", "sources": sources})
            return f"{self.SOURCES_MARKER_PREFIX}{sources_json}{self.SOURCES_MARKER_SUFFIX}"
        except Exception:
            return ""

    def _has_sufficient_grounding(self, context: str) -> bool:
        """True when LightRAG context is long enough to ground an LLM answer."""
        threshold = getattr(settings, "MIN_GROUNDING_CONTEXT_CHARS", 100)
        return bool(context and len(context.strip()) >= threshold)

    def _build_ungrounded_response(self, query: str) -> str:
        """Deterministic message when LightRAG returns no usable context."""
        return self.UNGROUNDED_RESPONSE

    def _build_datetime_response(self, query: str) -> str:
        """Build a deterministic date/time answer (no LightRAG / LLM)."""
        current = self._get_current_datetime()
        query_lower = (query or "").lower()
        if any(term in query_lower for term in ("time", "clock", "hour")):
            return f"The current date and time is: {current}"
        if any(term in query_lower for term in ("date", "day", "today")):
            return f"Today's date and time is: {current}"
        return f"The current date and time is: {current}"

    def _extract_last_routing_target(
        self,
        conversation_history: List[Dict[str, str]],
    ) -> Optional[str]:
        """Return the routing target from the most recent assistant turn."""
        for msg in reversed(conversation_history):
            if msg.get("role") != "assistant":
                continue
            target = msg.get("routing_target") or msg.get("source_module")
            if target:
                return str(target)
        return None

    async def _stream_deterministic_response(
        self,
        text: str,
        sources: Optional[List[str]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream deterministic text plus optional __SOURCES__ marker."""
        async for chunk in self._stream_text(text):
            yield chunk
        if sources:
            marker = self._format_sources_marker(sources)
            if marker:
                yield marker

    def _cap_prompt_section(self, label: str, text: str, max_chars: int) -> str:
        """Cap very large prompt sections (guardrail for token bloat)."""
        if not text:
            return ""
        if len(text) <= max_chars:
            return text
        logger.warning(f"[PROMPT] Capping '{label}' from {len(text)} to {max_chars} chars")
        return text[:max_chars] + "\n\n[... truncated ...]"

    # ============================================================
    # Response Caching (Token Optimization)
    # ============================================================
    
    async def _get_cached_openai_response(
        self,
        query: str,
        context: str,
        knowledge_base: Optional[str] = None,
        route_scope: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if we have a cached OpenAI response for this query+context.
        
        Args:
            query: User's query
            context: Combined context (LightRAG + Fee Engine)
            knowledge_base: KB name/version for cache key scoping
            route_scope: Routing target used to isolate cache entries per route
        
        Returns:
            Dict with 'response' and 'sources' if cached, None otherwise
        """
        try:
            cached = await self.redis_cache.get_cached_response(
                query,
                context,
                knowledge_base=knowledge_base,
                route_scope=route_scope,
            )
            if cached:
                logger.info(f"[RESPONSE_CACHE] Using cached response for query: '{query[:50]}...'")
                return cached
            return None
        except Exception as e:
            logger.debug(f"[RESPONSE_CACHE] Cache check failed: {e}")
            return None
    
    async def _cache_openai_response(
        self,
        query: str,
        context: str,
        response: str,
        sources: Optional[List[str]] = None,
        routing_target: Optional[str] = None,
        knowledge_base: Optional[str] = None,
        route_scope: Optional[str] = None,
    ) -> None:
        """
        Cache an OpenAI response for future identical queries.
        
        Args:
            query: User's query
            context: Combined context used for the response
            response: The OpenAI response to cache
            sources: Optional list of sources
            routing_target: The routing target (for analytics)
            knowledge_base: KB name/version for cache key scoping
            route_scope: Routing target used to isolate cache entries per route
        """
        try:
            await self.redis_cache.cache_response(
                query=query,
                context=context,
                response=response,
                sources=sources,
                routing_target=routing_target,
                knowledge_base=knowledge_base,
                route_scope=route_scope,
            )
        except Exception as e:
            logger.debug(f"[RESPONSE_CACHE] Failed to cache response: {e}")

    async def _stream_cached_response(
        self,
        cached_response: str,
        chunk_size: int = 20,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a cached response in chunks to maintain consistent UX.
        
        Args:
            cached_response: The cached response text
            chunk_size: Number of characters per chunk
        
        Yields:
            Response chunks
        """
        import asyncio
        
        # Stream the response in small chunks to simulate streaming
        for i in range(0, len(cached_response), chunk_size):
            chunk = cached_response[i:i + chunk_size]
            yield chunk
            # Small delay to make streaming feel natural (but much faster than OpenAI)
            await asyncio.sleep(0.01)

    def _select_model(self, query: str, decision: Optional[Any] = None) -> str:
        """
        Select the appropriate OpenAI model based on query complexity.
        
        Uses gpt-4o-mini (fast, cheap) for simple queries and gpt-4o (powerful) for complex ones.
        
        Args:
            query: The user's query
            decision: Optional RoutingDecision with signal flags
            
        Returns:
            Model name to use for this query
        """
        # Simple queries → use fast model (gpt-4o-mini)
        simple_indicators = [
            # Small talk
            self._is_small_talk(query),
            # Date/time queries
            self._is_datetime_query(query),
        ]
        
        if any(simple_indicators):
            logger.debug(f"[MODEL] Selected fast model for simple query: {settings.OPENAI_MODEL}")
            return settings.OPENAI_MODEL  # gpt-4o-mini
        
        # Complex queries → use powerful model (gpt-4o)
        complex_indicators = []
        
        if decision:
            complex_indicators = [
                decision.is_compliance_query,
                decision.is_financial_query,
                decision.is_management_query,
                decision.is_org_overview_query,
            ]
        else:
            # Fallback: check using methods directly
            complex_indicators = [
                self._is_compliance_query(query),
                self._is_financial_report_query(query),
                self._is_management_query(query),
                self._is_organizational_overview_query(query),
            ]
        
        if any(complex_indicators):
            logger.debug(f"[MODEL] Selected complex model for advanced query: {settings.OPENAI_MODEL_COMPLEX}")
            return settings.OPENAI_MODEL_COMPLEX  # gpt-4o
        
        # Default: use fast model for cost efficiency
        logger.debug(f"[MODEL] Selected default model: {settings.OPENAI_MODEL}")
        return settings.OPENAI_MODEL

    def _trim_conversation_history(
        self,
        conversation_history: List[Dict[str, str]],
        max_messages: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Trim conversation history to the last N messages for prompt compression.
        
        Args:
            conversation_history: Full conversation history
            max_messages: Maximum messages to keep (defaults to settings.MAX_HISTORY_IN_PROMPT)
            
        Returns:
            Trimmed conversation history
        """
        if not conversation_history:
            return []
        
        limit = max_messages if max_messages is not None else settings.MAX_HISTORY_IN_PROMPT
        
        if len(conversation_history) <= limit:
            return conversation_history
        
        # Keep only the last N messages
        trimmed = conversation_history[-limit:]
        logger.debug(f"[PROMPT] Trimmed conversation history from {len(conversation_history)} to {len(trimmed)} messages")
        return trimmed

    def _build_prompt_addons(
        self,
        query: str,
        context: str,
        conversation_history: List[Dict[str, str]],
    ) -> str:
        """
        Build the additional guidance blocks appended to the user message when context exists.

        Note: This is intentionally behavior-preserving; it reorganizes existing logic and adds size caps.
        """
        if not context:
            return ""

        query_lower = (query or "").lower()
        context_lower = (context or "").lower()

        org_overview_reminder = ""
        partial_info_reminder = ""
        currency_reminder = ""
        bank_name_reminder = ""
        conciseness_reminder = ""
        semantic_reminder = ""
        followup_reminder = ""
        supplementary_card_reminder = ""

        # Supplementary card reminder (only when fee-engine data is present)
        is_supplementary_query = "supplementary" in query_lower and ("fee" in query_lower or "annual" in query_lower)
        if is_supplementary_query and (self.OFFICIAL_CARD_RATES_HEADER in context or "Card Rates and Fees Information" in context):
            supplementary_card_reminder = "\n\n" + "="*70 + "\n💳 CRITICAL: SUPPLEMENTARY CARD FEES 💳\n" + "="*70 + "\n**MANDATORY**: Include BOTH: (1) First 2 cards FREE (BDT 0/year), (2) 3rd+ cards BDT 2,300/year.\n**FORBIDDEN**: Do NOT say only 'BDT 0' without mentioning 3rd+ card fee.\n**CORRECT**: 'First 2 supplementary cards are free (BDT 0/year). Starting from 3rd card, annual fee is BDT 2,300/year.'\n" + "="*70

        # Organizational overview reminder
        if self._is_organizational_overview_query(query):
            org_overview_reminder = "\n\n" + "="*70 + "\n🏦 ORGANIZATIONAL OVERVIEW QUERY - CRITICAL FILTERING RULES 🏦\n" + "="*70 + "\n**MANDATORY**: This is a GENERAL/CUSTOMER-FACING overview query about Eastern Bank PLC.\n\n**INCLUDE ONLY:**\n- Establishment year\n- Country of operation\n- Core banking services (accounts, loans, cards, etc.)\n- Major customer-facing platforms (e.g., EBLConnect)\n\n**EXCLUDE (DO NOT USE):**\n- Annual report details\n- Accounting, valuation, fair value discussions\n- Subsidiaries' financial treatments\n- Management/board-level analysis\n- Investor, audit, or regulatory document content\n\n**IF MIXED CONTENT IS RETRIEVED:**\n- Prefer customer-facing content\n- Discard investor/financial-statement-only information\n- Keep tone neutral, concise, and informational (NOT marketing, NOT investor-focused)\n\n**EXAMPLE CORRECT RESPONSE:**\n'Eastern Bank PLC. was established in [year] and operates in Bangladesh. It offers core banking services including savings accounts, current accounts, loans, credit cards, and digital banking platforms like EBLConnect.'\n\n**EXAMPLE WRONG RESPONSE:**\n'Eastern Bank PLC. reported total assets of BDT X in the annual report... [financial details]... The bank's subsidiaries are accounted for using... [accounting details]'\n" + "="*70

        # Partial information handling reminder
        specific_detail_indicators = ['minimum', 'balance', 'interest', 'rate', 'fee', 'charge', 'amount', 'requirement', 'eligibility', 'process', 'procedure', 'settlement', 'how to', 'steps', 'method']
        if any(indicator in query_lower for indicator in specific_detail_indicators):
            product_indicators = ['super hpa', 'hpa account', 'account', 'card', 'loan', 'product', 'service', 'easycredit', 'easy credit', 'want2buy', 'want 2 buy']
            if any(indicator in context_lower for indicator in product_indicators):
                is_easycredit_query = 'easycredit' in query_lower or 'easy credit' in query_lower
                if is_easycredit_query:
                    partial_info_reminder = "\n\n" + "="*70 + "\n🚨 CRITICAL PARTIAL INFORMATION RULE - EASYCREDIT QUERY 🚨\n" + "="*70 + "\nThe context above contains information about EasyCredit (interest rate, issuance fee, etc.).\n\nYOU MUST:\n1. FIRST: Extract and provide ALL available EasyCredit information from the context:\n   - Interest rate (20% reducing balance method)\n   - Issuance fee (2.3% or Tk. 575, whichever is higher, inclusive of VAT)\n   - Any other EasyCredit details mentioned\n2. If the exact detail is missing, DO NOT add a missing-info sentence.\n3. End with: \"Please contact the related department or unit for this specific detail if needed.\"\n\nEXAMPLE CORRECT RESPONSE:\n'EasyCredit at Eastern Bank PLC. has an annual fee of 20% interest rate (reducing balance method) and an issuance fee of 2.3% or Tk. 575 (whichever is higher, inclusive of VAT). Please contact the related department or unit for this specific detail if needed.'\n\nEXAMPLE WRONG RESPONSE:\n'While the specifics of the EasyCredit Early Settlement process are not detailed in the available information, it generally involves paying off an outstanding EasyCredit loan balance...' ← FORBIDDEN - missing available EasyCredit info\n" + "="*70
                else:
                    partial_info_reminder = "\n\n" + "="*70 + "\n🚨 CRITICAL PARTIAL INFORMATION RULE 🚨\n" + "="*70 + "\nThe context above contains information about the product/account/service mentioned in the query.\n\nYOU MUST:\n1. Extract and provide ALL available information about the product/account/service from the context\n2. If the exact detail is missing, DO NOT add a missing-info sentence.\n3. End with: \"Please contact the related department or unit for this specific detail if needed.\"\n\nEXAMPLE:\n- Query: 'What is the minimum balance for interest on EBL Super HPA Account?'\n- Context mentions 'Super HPA Account' but not minimum balance\n- CORRECT response: 'The EBL Super HPA Account [provide ALL available details from context]. Please contact the related department or unit for this specific detail if needed.'\n- WRONG response: 'I'm sorry, but the context does not provide information...'\n" + "="*70

        # Currency preservation reminder (only when card rates context is present)
        if self.OFFICIAL_CARD_RATES_HEADER in context or "Card Rates and Fees Information" in context:
            currency_reminder = "\n\n" + "="*70 + "\n🚨 CRITICAL CURRENCY RULE 🚨\n" + "="*70 + "\nThe context above contains currency codes like 'BDT' and 'USD'. You MUST use the EXACT currency code from the context.\n\nEXAMPLES:\n- If context shows 'BDT 287.5', you MUST output 'BDT 287.5' (NOT ₹287.5)\n- If context shows 'BDT 1,725', you MUST output 'BDT 1,725' (NOT ₹1,725)\n- If context shows 'USD 57.5', you MUST output 'USD 57.5'\n\nNEVER replace BDT with ₹ or any other currency symbol. BDT = Bangladeshi Taka.\n\n**CONCISENESS RULE**: For monetary values in Bangladesh, use ONE format only (BDT + Lakhs) and state it ONCE. Do NOT repeat the amount in different formats or in explanation text.\n" + "="*70

        # Bank name reminder
        if "Eastern Bank Limited" in context or "Eastern Bank Ltd" in context or "Eastern Bank PLC" in context:
            bank_name_reminder = "\n\n" + "="*70 + "\n🏦 CRITICAL BANK NAME RULE 🏦\n" + "="*70 + "\n**MANDATORY**: The bank name is ALWAYS 'Eastern Bank PLC.' (with a period, NOT 'Eastern Bank Limited' or 'Eastern Bank Ltd.').\n\nIf the context mentions 'Eastern Bank Limited' or 'Eastern Bank Ltd.', you MUST replace it with 'Eastern Bank PLC.' in your response.\n\nAlways use 'Eastern Bank PLC.' (with period) or 'EBL' when referring to the bank.\n" + "="*70

        # Conciseness reminder
        has_monetary_terms = any(term in context_lower for term in ['bdt', 'lakh', 'lakhs', 'crore', 'taka', 'tk'])
        is_general_query = any(phrase in query_lower for phrase in ['tell me more', 'tell me about', 'what is', 'explain', 'describe'])
        if has_monetary_terms or is_general_query:
            conciseness_reminder = "\n\n" + "="*70 + "\n📝 CRITICAL CONCISENESS RULES - READ CAREFULLY 📝\n" + "="*70 + "\n**MANDATORY RULES - VIOLATIONS ARE FORBIDDEN:**\n\n1. **Product/Account Names**:\n   - Mention the name ONCE at the beginning (e.g., 'Special Notice Deposit (SND) accounts')\n   - Then use ONLY: 'it', 'this account', 'this product', 'the account', 'they' (for plural)\n   - FORBIDDEN: Repeating the full product name in subsequent sentences\n\n2. **FORBIDDEN FILLER PHRASES - NEVER USE THESE:**\n   - 'making them an excellent choice'\n   - 'demonstrate EBL's commitment'\n   - 'form an integral part'\n   - 'making them a critical part'\n   - 'In essence', 'As per'\n   - 'These accounts are a testament to'\n   - 'substantial popularity'\n   - 'considerable balances'\n   - 'wide range'\n   - 'diverse needs'\n   - 'commitment to providing'\n\n3. **FORBIDDEN MARKETING LANGUAGE - NEVER USE:**\n   - 'excellent choice', 'substantial', 'considerable', 'wide range', 'diverse', 'commitment', 'demonstrate', 'testament to'\n\n4. **Response Style**:\n   - Be direct: State what it IS and what it DOES\n   - Keep it to 2-4 sentences for 'tell me more' queries\n   - Focus on key features and facts, not marketing language\n   - Do NOT restate the same information in different sentences\n\n5. **Monetary Values (if applicable)**:\n   - Use ONE format: 'BDT X lakhs'\n   - State ONCE only\n\n**EXAMPLE CORRECT (2 sentences):**\n'Special Notice Deposit (SND) accounts are short-term deposit accounts for businesses requiring limited notice for withdrawals. They help manage liquidity while earning interest on short-term savings.'\n\n**EXAMPLE WRONG (repetitive, filler phrases, marketing language):**\n'Special Notice Deposit (SND) accounts are a type of savings account... These accounts have gained substantial popularity... SND accounts are part of EBL's wide range... These accounts demonstrate EBL's commitment... making them a critical part...'\n" + "="*70

        # Semantic matching reminder
        if any(term in query_lower for term in ['credited', 'paid', 'deposited', 'fee', 'charge', 'rate', 'frequency', 'schedule']):
            semantic_reminder = "\n\n" + "="*70 + "\n🔍 SEMANTIC MATCHING REMINDER 🔍\n" + "="*70 + "\nThe user's question may use different words than the context. Recognize semantic equivalents:\n- 'credited' = 'paid' = 'deposited' (all mean interest added to account)\n- 'fee' = 'charge' = 'cost'\n- 'rate' = 'interest rate'\n- 'frequency' = 'schedule' = 'how often' = 'when'\n\nIf the context uses 'paid' but user asks about 'credited', they mean the same thing. Use the information from context.\n" + "="*70

        # Follow-up reminder (uses recent conversation history + last routing target)
        last_routing_target = self._extract_last_routing_target(conversation_history)
        if conversation_history:
            followup_indicators = ['after', 'how many', 'what is', 'when', 'how often', 'how much']
            if any(indicator in query_lower for indicator in followup_indicators):
                prev_topics: List[str] = []
                for msg in conversation_history[-4:]:
                    content = (msg.get("message", "") or "").lower()
                    if any(term in content for term in ['account', 'card', 'loan', 'deposit', 'hpa', 'super']):
                        prev_topics.append(content[:100])
                if prev_topics or last_routing_target:
                    routing_hint = (
                        f"\nPrevious turn routing: {last_routing_target}."
                        if last_routing_target
                        else ""
                    )
                    topic_hint = (
                        f"\nPrevious conversation mentioned:\n{chr(10).join(prev_topics[:2])}"
                        if prev_topics
                        else ""
                    )
                    followup_reminder = (
                        "\n\n" + "=" * 70
                        + "\n📝 FOLLOW-UP QUESTION CONTEXT 📝\n"
                        + "=" * 70
                        + f"{routing_hint}{topic_hint}\n\n"
                        "Treat the current question as related to the same topic unless the user clearly changed subject.\n"
                        + "=" * 70
                    )

        # Apply per-section caps
        org_overview_reminder = self._cap_prompt_section("org_overview_reminder", org_overview_reminder, self.MAX_SINGLE_REMINDER_CHARS)
        partial_info_reminder = self._cap_prompt_section("partial_info_reminder", partial_info_reminder, self.MAX_SINGLE_REMINDER_CHARS)
        currency_reminder = self._cap_prompt_section("currency_reminder", currency_reminder, self.MAX_SINGLE_REMINDER_CHARS)
        bank_name_reminder = self._cap_prompt_section("bank_name_reminder", bank_name_reminder, self.MAX_SINGLE_REMINDER_CHARS)
        conciseness_reminder = self._cap_prompt_section("conciseness_reminder", conciseness_reminder, self.MAX_SINGLE_REMINDER_CHARS)
        semantic_reminder = self._cap_prompt_section("semantic_reminder", semantic_reminder, self.MAX_SINGLE_REMINDER_CHARS)
        followup_reminder = self._cap_prompt_section("followup_reminder", followup_reminder, self.MAX_SINGLE_REMINDER_CHARS)
        supplementary_card_reminder = self._cap_prompt_section("supplementary_card_reminder", supplementary_card_reminder, self.MAX_SINGLE_REMINDER_CHARS)

        addons = (
            org_overview_reminder
            + partial_info_reminder
            + currency_reminder
            + bank_name_reminder
            + conciseness_reminder
            + semantic_reminder
            + followup_reminder
            + supplementary_card_reminder
        )
        return self._cap_prompt_section("prompt_addons", addons, self.MAX_TOTAL_PROMPT_ADDONS_CHARS)

    async def _get_disambiguation_state_any(self, state_key: str) -> Optional[Dict[str, Any]]:
        """Get disambiguation state from Redis if available, else local fallback."""
        self._local_disambiguation_cleanup()
        try:
            state = await self.redis_cache.get_disambiguation_state(state_key)
            if state:
                return state
        except Exception as e:
            # Redis unavailable/timeout - fall back to local in-process state
            logger.warning(f"[DISAMBIGUATION] Redis get failed for key='{state_key}', using local fallback: {e}")
        local = self._local_disambiguation_state.get(state_key)
        return local.get("state") if local else None

    async def _clear_disambiguation_state_any(self, state_key: str) -> None:
        """Clear disambiguation state in Redis (if any) and local fallback."""
        try:
            try:
                await self.redis_cache.clear_disambiguation_state(state_key)
            except Exception as e:
                logger.warning(f"[DISAMBIGUATION] Redis clear failed for key='{state_key}', continuing with local cleanup: {e}")
        finally:
            self._local_disambiguation_state.pop(state_key, None)

    async def _handle_lead_generation(
        self,
        query: str,
        conversation_key: str,
        session_id: str,
        employee: Optional["EmployeeUser"] = None,
    ) -> Optional[str]:
        """Run lead capture / status flow when enabled. Returns response text or None."""
        if not settings.ENABLE_LEAD_GENERATION:
            return None
        try:
            return await self.lead_capture_handler.handle_turn(
                query, conversation_key, session_id, employee
            )
        except Exception as exc:
            logger.error("[LEAD] Flow error: %s", exc, exc_info=True)
            return "Sorry, the lead service encountered an error. Please try again."
    
    def _bind_identity(
        self,
        employee: Optional["EmployeeUser"],
        user_id: Optional[str],
    ) -> None:
        """
        Record the AD-authenticated identity for the current request in a
        ContextVar. `user_id` passed by the route is already the stable AD id; the
        EmployeeUser (when present) supplies metadata + legacy keys for reconciling
        older history. Never uses any client-supplied field.
        """
        try:
            from app.services.chat_session_service import identity_from_employee

            self._identity_ctx = _current_identity  # keep a handle for clarity
            _current_identity.set(identity_from_employee(employee, fallback_user_id=user_id))
        except Exception as exc:
            logger.debug("[SESSION] Could not bind identity context: %s", exc)
            _current_identity.set(None)

    async def _persist_turn(
        self,
        session_id: str,
        user_text: str,
        assistant_text: str,
        knowledge_base: Optional[str] = None,
        client_ip: Optional[str] = None,
        routing_target: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Persist user and assistant messages and maintain chat_sessions metadata.

        Authorization: writes are scoped to the AD-authenticated identity bound for
        this request. Message content is redacted (and optionally encrypted) inside
        the persistence layer before it touches the database.
        """
        # Resolve the full identity (metadata + legacy keys) bound at entry; fall
        # back to a bare stable id if the context is unavailable.
        identity = _current_identity.get()
        if identity is None and user_id:
            from app.services.chat_session_service import ChatIdentity

            identity = ChatIdentity(user_id=user_id)

        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            if memory._available:
                # --- user-scoped session bookkeeping ---
                if user_id:
                    try:
                        from app.services.chat_session_service import (
                            ensure_session,
                            add_message,
                            touch_session,
                            SessionOwnershipError,
                            mint_user_scoped_reference,
                        )
                        sess = ensure_session(db, session_id, user_id, identity=identity)
                        add_message(db, sess, "user", user_text, source_module=routing_target)
                        add_message(db, sess, "assistant", assistant_text, source_module=routing_target)
                        touch_session(db, sess, first_user_message=user_text, last_message_preview=assistant_text)
                    except SessionOwnershipError as ownership_err:
                        logger.warning(
                            "[SESSION] Ownership conflict for %s: %s — minting user-scoped reference",
                            session_id,
                            ownership_err,
                        )
                        scoped_ref = mint_user_scoped_reference(user_id, session_id)
                        try:
                            sess = ensure_session(db, scoped_ref, user_id, identity=identity)
                            add_message(db, sess, "user", user_text, source_module=routing_target)
                            add_message(db, sess, "assistant", assistant_text, source_module=routing_target)
                            touch_session(
                                db,
                                sess,
                                first_user_message=user_text,
                                last_message_preview=assistant_text,
                            )
                        except Exception as retry_err:
                            logger.warning(
                                "[SESSION] Could not persist to scoped reference %s: %s",
                                scoped_ref,
                                retry_err,
                            )
                    except Exception as sess_err:
                        logger.warning(
                            "[SESSION] Session bookkeeping failed; turn not persisted: %s",
                            sess_err,
                        )
                else:
                    # No user_id — fall back to legacy direct insert (redaction and
                    # encryption still applied inside PostgresChatMemory.add_message).
                    memory.add_message(session_id, "user", user_text)
                    memory.add_message(session_id, "assistant", assistant_text)

                if ANALYTICS_AVAILABLE:
                    # Redact the analytics copy too so secrets never reach any table.
                    log_conversation(
                        session_id=session_id,
                        user_message=self._redact_for_storage(user_text),
                        assistant_response=self._redact_for_storage(assistant_text),
                        knowledge_base=knowledge_base,
                        client_ip=client_ip,
                        routing_target=routing_target
                    )
        finally:
            memory.close()
            if db:
                db.close()

    @staticmethod
    def _redact_for_storage(text: str) -> str:
        """Best-effort PII redaction for analytics/log copies of messages."""
        try:
            if settings.CHAT_HISTORY_REDACTION_ENABLED:
                from app.services.pii_redaction import redact_sensitive

                return redact_sensitive(text or "")
        except Exception:
            pass
        return text or ""
    
    async def _stream_text(self, text: str, chunk_size: int = 100) -> AsyncGenerator[str, None]:
        """Stream text in chunks."""
        for i in range(0, len(text), chunk_size):
            yield text[i:i + chunk_size]
    
    async def _handle_disambiguation_resolution(
        self,
        query: str,
        conversation_key: str,
        session_id: str,
        pending_disambiguation: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle disambiguation state resolution.
        
        Args:
            query: User's query
            conversation_key: Stable conversation key
            session_id: Session ID for memory operations
            pending_disambiguation: Disambiguation state dict
        Returns:
            Dict with "response" (and optional "sources"), or None if not in disambiguation
        """
        product_line = pending_disambiguation.get("product_line")
        charge_type = pending_disambiguation.get("charge_type")
        options = pending_disambiguation.get("options", [])
        disambiguation_type = pending_disambiguation.get("disambiguation_type")
        prompt_message = pending_disambiguation.get("prompt_message")
        extra = pending_disambiguation.get("extra") or {}
        sources: List[str] = []
        if product_line == "CREDIT_CARDS":
            sources = ["Card Charges and Fees Schedule (Effective from 01st January, 2026)"]
        elif product_line == "RETAIL_ASSETS":
            sources = ["Retail Asset Charges Schedule"]
        
        logger.info(f"[DISAMBIGUATION] Found pending disambiguation for session {session_id}: product_line={product_line}, charge_type={charge_type}, type={disambiguation_type}")
        
        # Try to resolve selection from query
        selected_option = self._resolve_selection(query, options)
        
        if selected_option and product_line == "RETAIL_ASSETS":
            # 🚨 TERMINAL RESOLUTION STATE: Disambiguation resolved - NOTHING ELSE RUNS
            await self._clear_disambiguation_state_any(conversation_key)
            loan_product = selected_option.get("loan_product")
            option_charge_type = selected_option.get("charge_type", charge_type)
            charge_context = selected_option.get("charge_context")
            description_keywords = selected_option.get("description_keywords")
            if not description_keywords and disambiguation_type == "DESCRIPTION":
                chosen = selected_option.get("answer_text") or selected_option.get("charge_description")
                if chosen and str(chosen).strip():
                    description_keywords = [str(chosen).strip()]
            
            logger.info(f"[DISAMBIGUATION] 🚨 TERMINAL RESOLUTION: loan_product={loan_product}, charge_type={option_charge_type}, charge_context={charge_context}. EXITING after fee engine call - NO RAG, NO CARDS, NO PRODUCT KB.")
            
            # HARD GUARD: Only call fee engine, no RAG, no cards, no product KB
            fee_client = self.fee_engine_client
            
            fee_result = await fee_client._query_retail_asset_charges(
                query=query,
                charge_type=option_charge_type,
                loan_product=loan_product,
                description_keywords=description_keywords
            )
            
            if fee_result and fee_result.get("status") == "FOUND":
                formatted = fee_client.format_fee_response(fee_result, query=query)
                fee_context = f"{self.OFFICIAL_RETAIL_ASSET_HEADER}\n{formatted}\n\nThis information is from the Retail Asset Charges Schedule and is authoritative."
                
                # Save to memory
                await self._persist_turn(session_id, query, fee_context, user_id=user_id)
                return {"response": fee_context, "sources": sources}
            else:
                error_msg = "I apologize, but I couldn't find the fee information for the selected loan product. Please try again or contact the related department or unit for this specific detail if needed."
                await self._persist_turn(session_id, query, error_msg, user_id=user_id)
                return {"response": error_msg, "sources": sources}
        
        elif selected_option and product_line == "CREDIT_CARDS" and disambiguation_type == "CARD_PRODUCT":
            # Do NOT clear disambiguation yet. Users often reply with another option
            # number right after a successful pick (e.g. "11" then "9"). Keeping the
            # card-product options alive lets those follow-ups stay on the fee engine
            # instead of falling through to LightRAG with an ungrounded "9".
            base_query = (extra.get("base_query") or "").strip()
            chosen_product = (
                selected_option.get("card_product_name")
                or selected_option.get("card_product")
                or selected_option.get("label")
                or ""
            ).strip()
            
            if not base_query or not chosen_product:
                response_text = prompt_message or "Please specify the card product (reply with a number from the list)."
                await self._persist_turn(session_id, query, response_text, user_id=user_id)
                return {"response": response_text, "sources": sources}
            
            resolved_query = f"{base_query} {chosen_product}".strip()
            fee_context = await self._get_card_rates_context(
                resolved_query,
                session_id=session_id,
                conversation_key=conversation_key,
            )
            
            if not fee_context:
                fee_context = (
                    f"{self.OFFICIAL_CARD_RATES_HEADER}\n"
                    f"{self.FEE_ENGINE_SOURCE}\n\n"
                    "The requested fee information is not available in the Card Charges and Fees Schedule (effective 01 Jan 2026)."
                )
            
            # Refresh TTL so another numbered selection within a few minutes still
            # resolves as CARD_PRODUCT. A real new question still clears state via
            # _looks_like_new_query_during_disambiguation (fee/how-to/etc. keywords).
            try:
                from datetime import date

                await self._store_disambiguation_state_any(
                    state_key=conversation_key,
                    product_line=product_line,
                    charge_type=charge_type or "INTEREST_RATE",
                    as_of_date=str(date.today()),
                    options=options,
                    disambiguation_type="CARD_PRODUCT",
                    prompt_message=prompt_message or "",
                    extra={"base_query": base_query},
                    ttl_seconds=300,
                )
                logger.info(
                    "[DISAMBIGUATION] Kept CARD_PRODUCT options active after selecting %s "
                    "(follow-up option numbers still allowed)",
                    chosen_product,
                )
            except Exception as refresh_err:
                logger.warning(
                    "[DISAMBIGUATION] Failed to refresh CARD_PRODUCT state after selection: %s",
                    refresh_err,
                )

            await self._persist_turn(session_id, query, fee_context, user_id=user_id)
            return {"response": fee_context, "sources": sources}
        
        else:
            # Selection not resolved - re-prompt
            logger.info(f"[DISAMBIGUATION] Selection not resolved from query '{query}', keeping disambiguation state active. User needs to provide a valid selection (1-{len(options)}) or product name.")
            
            if prompt_message:
                disambiguation_msg = prompt_message
                logger.info(f"[DISAMBIGUATION] Re-prompting with stored message (type={disambiguation_type})")
            else:
                # Fallback: reconstruct if stored message not available
                fee_client = self.fee_engine_client
                if product_line == "CREDIT_CARDS" and disambiguation_type == "CARD_PRODUCT":
                    result_dict = {
                        "status": "NEEDS_DISAMBIGUATION",
                        "charge_type": charge_type,
                        "options": options,
                    }
                    disambiguation_msg = "\n".join([
                        self.OFFICIAL_CARD_RATES_HEADER,
                        self.FEE_ENGINE_SOURCE,
                        "",
                        fee_client._format_card_fee_disambiguation_response(result_dict, query),
                    ])
                else:
                    charges = [
                        {
                            "loan_product": opt.get("loan_product"),
                            "loan_product_name": opt.get("loan_product_name", opt.get("loan_product")),
                            "charge_type": opt.get("charge_type", charge_type),
                            "charge_context": opt.get("charge_context"),
                            "charge_description": opt.get("charge_description"),
                            "answer_text": opt.get("answer_text"),
                        }
                        for opt in options
                    ]
                    result_dict = {
                        "status": "NEEDS_DISAMBIGUATION",
                        "charges": charges,
                        "message": f"Multiple loan products have {charge_type.replace('_', ' ').title()} available. Please specify which loan product you're interested in."
                    }
                    disambiguation_msg = fee_client._format_retail_asset_disambiguation_response(result_dict, query)
            
            await self._persist_turn(session_id, query, disambiguation_msg, user_id=user_id)
            return {"response": disambiguation_msg, "sources": sources}
    
    async def close(self):
        """Close all async clients and resources in parallel."""
        import asyncio
        
        # Close all HTTP clients in parallel for faster shutdown
        close_tasks = []
        
        if self.lightrag_client:
            close_tasks.append(self._safe_close(self.lightrag_client, "LightRAG"))
        if self.fee_engine_client:
            close_tasks.append(self._safe_close(self.fee_engine_client, "FeeEngine"))
        if self.location_client:
            close_tasks.append(self._safe_close(self.location_client, "Location"))
        
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
            logger.info(f"All {len(close_tasks)} async clients closed")
    
    async def _safe_close(self, client, name: str):
        """Safely close a client, logging any errors."""
        try:
            await client.close()
            logger.info(f"{name} client closed")
        except Exception as e:
            logger.warning(f"Error closing {name} client: {e}")
    
    def _get_system_message(self) -> str:
        """Get system message for the chatbot (compressed core rules; details in prompt add-ons)."""
        return """You are Eastern Bank PLC.'s internal knowledge assistant for EBL employees supporting customers.

Core rules:
1. Use provided knowledge-base context when present; never invent rates, fees, limits, or policy details.
2. Bank name is always "Eastern Bank PLC." (replace "Eastern Bank Limited" or "Eastern Bank Ltd." if seen).
3. Preserve currency codes exactly (BDT, USD); never substitute other symbols.
4. Location data marked "EBL Location Database" is authoritative—use it directly.
5. Fee data marked with OFFICIAL fee-engine headers is authoritative—use only that for fee answers.
6. If context has partial product info, share all available details first, then note the missing specific detail and suggest contacting the related department.
7. Only say you lack information when context is empty or wholly irrelevant.
8. Be concise: name the product once, then use pronouns; avoid marketing filler.
9. For date/time questions, use the current date/time supplied in the user message when present.

Additional targeted reminders may be appended to the user message when relevant."""
    
    # =========================================================================
    # Query Classification Methods (delegated to QueryClassifier)
    # These methods delegate to self.query_classifier for backward compatibility
    # The actual logic is now in app/services/handlers/query_classifier.py
    # =========================================================================
    
    def _is_small_talk(self, query: str) -> bool:
        """Detect if query is small talk. Delegates to QueryClassifier."""
        return self.query_classifier.is_small_talk(query)
    
    def _is_datetime_query(self, query: str) -> bool:
        """Detect if query is about date/time. Delegates to QueryClassifier."""
        return self.query_classifier.is_datetime_query(query)
    
    def _is_contact_info_query(self, query: str) -> bool:
        """Detect contact info query. Delegates to QueryClassifier."""
        return self.query_classifier.is_contact_info_query(query)
    
    def _is_phonebook_query(self, query: str) -> bool:
        """Detect phonebook query. Delegates to QueryClassifier."""
        return self.query_classifier.is_phonebook_query(query)
    
    def _is_employee_query(self, query: str) -> bool:
        """Detect employee query. Delegates to QueryClassifier."""
        return self.query_classifier.is_employee_query(query)
    
    def _is_financial_report_query(self, query: str) -> bool:
        """Detect financial report query. Delegates to QueryClassifier."""
        return self.query_classifier.is_financial_report_query(query)
    
    def _is_user_document_query(self, query: str) -> bool:
        """Detect user document query. Delegates to QueryClassifier."""
        return self.query_classifier.is_user_document_query(query)

    def _is_eblhome_form_query(self, query: str) -> bool:
        """Detect EBL Home form lookup. Delegates to QueryClassifier."""
        return self.query_classifier.is_eblhome_form_query(query)

    def _is_eblhome_app_link_query(self, query: str) -> bool:
        """Detect EBL Home application link lookup. Delegates to QueryClassifier."""
        return self.query_classifier.is_eblhome_app_link_query(query)

    def _is_eblhome_leadership_query(self, query: str) -> bool:
        """Detect EBL Home leadership lookup. Delegates to QueryClassifier."""
        return self.query_classifier.is_eblhome_leadership_query(query)

    def _is_eblhome_soc_query(self, query: str) -> bool:
        return self.query_classifier.is_eblhome_soc_query(query)

    def _is_eblhome_proposal_query(self, query: str) -> bool:
        return self.query_classifier.is_eblhome_proposal_query(query)

    def _is_eblhome_circular_query(self, query: str) -> bool:
        return self.query_classifier.is_eblhome_circular_query(query)
    
    def _is_organizational_overview_query(self, query: str) -> bool:
        """Detect organizational overview query. Delegates to QueryClassifier."""
        return self.query_classifier.is_organizational_overview_query(query)
    
    def _is_management_query(self, query: str) -> bool:
        """Detect management query. Delegates to QueryClassifier."""
        return self.query_classifier.is_management_query(query)
    
    def _is_milestone_query(self, query: str) -> bool:
        """Detect milestone query. Delegates to QueryClassifier."""
        return self.query_classifier.is_milestone_query(query)
    
    def _is_fee_schedule_query(self, query: str) -> bool:
        """Detect fee schedule query. Delegates to QueryClassifier."""
        return self.query_classifier.is_fee_schedule_query(query)
    
    def _is_retail_asset_fee_query(self, query: str) -> bool:
        """Detect retail asset fee query. Delegates to QueryClassifier."""
        return self.query_classifier.is_retail_asset_fee_query(query)
    
    def _is_skybanking_fee_query(self, query: str) -> bool:
        """Detect Skybanking fee query. Delegates to QueryClassifier."""
        return self.query_classifier.is_skybanking_fee_query(query)
    
    def _is_generic_skybanking_fee_query(self, query: str) -> bool:
        """Detect generic Skybanking fee query. Delegates to QueryClassifier."""
        return self.query_classifier.is_generic_skybanking_fee_query(query)

    def _is_location_query(self, query: str) -> bool:
        """Detect location query. Delegates to QueryClassifier."""
        return self.query_classifier.is_location_query(query)
    
    def _is_compliance_query(self, query: str) -> bool:
        """Detect compliance query. Delegates to QueryClassifier."""
        return self.query_classifier.is_compliance_query(query)
    
    def _is_banking_product_query(self, query: str) -> bool:
        """Detect banking product query. Delegates to QueryClassifier."""
        return self.query_classifier.is_banking_product_query(query)
    
    def _is_broad_loan_product_line_query(self, query: str) -> bool:
        """Detect broad loan product line query. Delegates to QueryClassifier."""
        return self.query_classifier.is_broad_loan_product_line_query(query)
    
    # =========================================================================
    # Response Formatting Methods (delegated to ResponseFormatter)
    # =========================================================================
    
    def _clean_markdown_formatting(self, text: str) -> str:
        """Clean markdown from text. Delegates to ResponseFormatter."""
        return self.response_formatter.clean_markdown(text)
    
    def _fix_currency_symbols(self, text: str, context: str = "") -> str:
        """Fix currency symbols. Delegates to ResponseFormatter."""
        return self.response_formatter.fix_currency_symbols(text, context)
    
    def _fix_bank_name(self, text: str) -> str:
        """Fix bank name consistency. Delegates to ResponseFormatter."""
        return self.response_formatter.fix_bank_name(text)
    
    def _get_current_datetime(self) -> str:
        """Get current datetime. Delegates to ResponseFormatter."""
        return self.response_formatter.get_current_datetime()
    
    # =========================================================================
    # Disambiguation Methods (delegated to DisambiguationHandler)
    # =========================================================================
    
    def _resolve_selection(self, query: str, options: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Resolve user selection. Delegates to DisambiguationHandler."""
        return self.disambiguation_handler.resolve_selection(query, options)
    
    def _looks_like_new_query_during_disambiguation(self, query: str, options: List[Dict[str, Any]]) -> bool:
        """Check if query is new during disambiguation. Delegates to DisambiguationHandler."""
        return self.disambiguation_handler.looks_like_new_query(query, options)

    def _is_bare_option_number(self, query: str) -> bool:
        """True when the user replied with only an option number like '9' or '11.'."""
        return bool(re.match(r"^\s*\d{1,2}\s*[\.\)]?\s*$", (query or "").strip()))

    def _extract_card_products_from_disambiguation_text(self, text: str) -> List[str]:
        """
        Parse numbered card-product lines from a prior fee-engine disambiguation reply
        into a dense 1-based list (index 0 = option 1).

        Example lines:
          1. Army/Air Force/ Navy Platinum
          9. Titanium
          11. World
        """
        numbered = self._extract_numbered_card_products(text)
        if not numbered:
            return []
        max_n = max(numbered)
        # Prefer contiguous fee-engine lists (1..N). Fill gaps with empty strings
        # so option number N still maps to list index N-1 when the list is dense.
        return [numbered.get(i, "") for i in range(1, max_n + 1)]

    def _extract_numbered_card_products(self, text: str) -> Dict[int, str]:
        """Return {display_number: product_name} from a card disambiguation reply."""
        numbered: Dict[int, str] = {}
        for match in re.finditer(
            r"(?m)^\s*(\d{1,2})\s*[\.\)]\s+(.+?)\s*$",
            text or "",
        ):
            try:
                num = int(match.group(1))
            except ValueError:
                continue
            name = match.group(2).strip()
            lower = name.lower()
            if lower.startswith("reply with") or "specify which" in lower:
                break
            if name:
                numbered[num] = name
        return numbered

    def _recover_card_product_options_from_history(
        self,
        conversation_history: List[Dict[str, Any]],
        query: str,
    ) -> Optional[Dict[str, Any]]:
        """
        When Redis disambiguation state is gone but the user sends another bare
        option number, rebuild CARD_PRODUCT options from the last fee-engine
        assistant turn that listed numbered card products.
        """
        if not self._is_bare_option_number(query) or not conversation_history:
            return None

        try:
            selection_num = int(re.match(r"^\s*(\d{1,2})", (query or "").strip()).group(1))
        except (AttributeError, ValueError):
            return None

        # Walk recent messages newest-first. Collect the card list from the latest
        # fee-engine disambiguation reply, and the nearest prior non-numeric user
        # question as the fee base_query (needed after Redis state is cleared).
        base_query = ""
        numbered: Dict[int, str] = {}
        for msg in reversed(conversation_history[-12:]):
            role = (msg.get("role") or "").lower()
            content = msg.get("message") or ""
            if role == "user":
                if not base_query and not self._is_bare_option_number(content):
                    base_query = content.strip()
                continue
            if role != "assistant" or numbered:
                continue
            if "which card" not in content.lower() and "card product" not in content.lower():
                continue
            extracted = self._extract_numbered_card_products(content)
            if extracted:
                numbered = extracted
            # Keep scanning older user turns for base_query even after finding products.

        if not numbered or not base_query:
            return None

        chosen = (numbered.get(selection_num) or "").strip()
        if not chosen:
            return None

        max_n = max(numbered)
        options = [
            {
                "card_product": numbered.get(i, ""),
                "card_product_name": numbered.get(i, ""),
                "label": numbered.get(i, ""),
            }
            for i in range(1, max_n + 1)
        ]

        logger.info(
            "[DISAMBIGUATION] Recovered CARD_PRODUCT selection %r from chat history "
            "(Redis state missing; bare option %r)",
            chosen,
            query,
        )
        return {
            "base_query": base_query,
            "chosen_product": chosen,
            "options": options,
        }

    async def _try_recover_card_disambiguation_from_history(
        self,
        *,
        query: str,
        conversation_history: List[Dict[str, Any]],
        session_id: str,
        conversation_key: str,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        If Redis state was cleared but the user sent another bare option number,
        recover the card list from history, answer via the fee engine, and restore
        disambiguation state for further follow-up numbers.
        """
        recovered = self._recover_card_product_options_from_history(conversation_history, query)
        if not recovered:
            return None

        base_query = recovered["base_query"]
        chosen_product = recovered["chosen_product"]
        options = recovered["options"]
        resolved_query = f"{base_query} {chosen_product}".strip()

        fee_context = await self._get_card_rates_context(
            resolved_query,
            session_id=session_id,
            conversation_key=conversation_key,
        )
        if not fee_context:
            fee_context = (
                f"{self.OFFICIAL_CARD_RATES_HEADER}\n"
                f"{self.FEE_ENGINE_SOURCE}\n\n"
                "The requested fee information is not available in the Card Charges and Fees Schedule (effective 01 Jan 2026)."
            )

        try:
            from datetime import date

            await self._store_disambiguation_state_any(
                state_key=conversation_key,
                product_line="CREDIT_CARDS",
                charge_type="INTEREST_RATE",
                as_of_date=str(date.today()),
                options=options,
                disambiguation_type="CARD_PRODUCT",
                prompt_message="",
                extra={"base_query": base_query},
                ttl_seconds=300,
            )
        except Exception as refresh_err:
            logger.warning(
                "[DISAMBIGUATION] Failed to restore CARD_PRODUCT state after history recovery: %s",
                refresh_err,
            )

        sources = ["Card Charges and Fees Schedule (Effective from 01st January, 2026)"]
        await self._persist_turn(
            session_id,
            query,
            fee_context,
            routing_target="FEE_ENGINE_CARDS",
            user_id=user_id,
        )
        return {"response": fee_context, "sources": sources}
    
    def _has_process_intent(self, query: str) -> bool:
        """Check for process intent. Delegates to DisambiguationHandler."""
        return self.disambiguation_handler.has_process_intent(query)
    
    def _should_prompt_routing_disambiguation(self, query: str, decision: Any) -> bool:
        """Check if routing disambiguation needed. Delegates to DisambiguationHandler."""
        return self.disambiguation_handler.should_prompt_routing_disambiguation(query, decision)
    
    def _build_routing_disambiguation_prompt(self) -> str:
        """Build routing disambiguation prompt. Delegates to DisambiguationHandler."""
        return self.disambiguation_handler.build_routing_disambiguation_prompt()
    
    def _build_routing_disambiguation_options(self) -> List[Dict[str, Any]]:
        """Build routing disambiguation options. Delegates to DisambiguationHandler."""
        return self.disambiguation_handler.build_routing_disambiguation_options()
    
    def _build_fee_type_disambiguation_prompt(self, fee_candidates: List[str]) -> str:
        """Build fee type disambiguation prompt. Delegates to DisambiguationHandler."""
        return self.disambiguation_handler.build_fee_type_disambiguation_prompt(fee_candidates)
    
    def _build_fee_type_disambiguation_options(self, fee_candidates: List[str]) -> List[Dict[str, Any]]:
        """Build fee type disambiguation options. Delegates to DisambiguationHandler."""
        return self.disambiguation_handler.build_fee_type_disambiguation_options(fee_candidates)
    
    # =========================================================================
    # NOTE: Original _is_*_query implementations have been moved to:
    # app/services/handlers/query_classifier.py
    # 
    # The delegation methods above forward calls to the QueryClassifier.
    # Original implementations are preserved in the handler for reference.
    # =========================================================================
    
    # Non-delegated methods (location context, policy checks, etc.) continue below...

    async def _prepare_lightrag_turn(
        self,
        query: str,
        decision: Any,
        knowledge_base: Optional[str],
    ) -> tuple[str, List[str], str, Optional[str]]:
        """
        Load LightRAG context for a non-fee, non-phonebook turn.

        Returns:
            (context, sources, knowledge_base, clarification_message)
            When clarification_message is set, caller should return it and skip LightRAG.
        """
        if decision.is_compliance_query:
            has_entities, clarification = self._check_policy_entities(query)
            if not has_entities and clarification:
                return "", [], knowledge_base or "", clarification

        chosen_kb = knowledge_base or self._get_knowledge_base(query)
        filter_financial = self._is_organizational_overview_query(query)
        logger.info(
            "[ROUTING] Calling LightRAG with knowledge_base='%s' for query: '%s'",
            chosen_kb,
            query[:100],
        )
        context, sources = await self._get_lightrag_context(
            query,
            chosen_kb,
            filter_financial_docs=filter_financial,
        )
        if context:
            logger.info(
                "[ROUTING] LightRAG returned context (length: %s chars, sources: %s, filtered_financial=%s)",
                len(context),
                len(sources),
                filter_financial,
            )
        else:
            logger.warning("[ROUTING] LightRAG returned empty context")

        if not sources and context and chosen_kb:
            sources.append(f"Knowledge Base: {chosen_kb}")
            logger.info("[SOURCES] Added knowledge base name as fallback source: %s", chosen_kb)

        return context, sources, chosen_kb, None

    async def _stream_phonebook_response(
        self,
        query: str,
        session_id: str,
        client_ip: Optional[str],
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Run phonebook lookup and stream the deterministic response."""
        result = self.phonebook_handler.lookup(query, self.phonebook_db)
        sources = ["EBL Phonebook / Employee Directory"]
        phonebook_meta = (
            f"phonebook:term={result.search_term};found={result.found}"
            if result.search_term
            else ("phonebook:found=false" if not result.found else None)
        )
        async for chunk in self._stream_deterministic_response(result.response_text, sources):
            yield chunk
        await self._persist_turn(
            session_id,
            query,
            result.response_text,
            knowledge_base=phonebook_meta,
            client_ip=client_ip,
            routing_target="PHONEBOOK",
            user_id=user_id,
        )

    async def _stream_forms_response(
        self,
        query: str,
        session_id: str,
        client_ip: Optional[str],
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Run EBL Home forms lookup and stream the deterministic response."""
        result = self.forms_handler.lookup(query, self.forms_db)
        sources = ["EBL Home Forms"]
        forms_meta = (
            f"forms:term={result.search_term};found={result.found}"
            if result.search_term
            else ("forms:found=false" if not result.found else None)
        )
        async for chunk in self._stream_deterministic_response(result.response_text, sources):
            yield chunk
        await self._persist_turn(
            session_id,
            query,
            result.response_text,
            knowledge_base=forms_meta,
            client_ip=client_ip,
            routing_target="EBLHOME_FORMS",
            user_id=user_id,
        )

    async def _stream_app_links_response(
        self,
        query: str,
        session_id: str,
        client_ip: Optional[str],
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Run EBL Home application link lookup and stream the deterministic response."""
        result = self.app_links_handler.lookup(query, self.apps_db)
        sources = ["EBL Home Applications"]
        apps_meta = (
            f"apps:term={result.search_term};found={result.found}"
            if result.search_term
            else ("apps:found=false" if not result.found else None)
        )
        async for chunk in self._stream_deterministic_response(result.response_text, sources):
            yield chunk
        await self._persist_turn(
            session_id,
            query,
            result.response_text,
            knowledge_base=apps_meta,
            client_ip=client_ip,
            routing_target="EBLHOME_APPS",
            user_id=user_id,
        )

    async def _stream_leadership_response(
        self,
        query: str,
        session_id: str,
        client_ip: Optional[str],
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Run EBL Home leadership lookup and stream the deterministic response."""
        result = self.leadership_handler.lookup(query, self.leadership_db)
        sources = ["EBL Home Leadership"]
        leadership_meta = (
            f"leadership:term={result.search_term};found={result.found}"
            if result.search_term
            else ("leadership:found=false" if not result.found else None)
        )
        async for chunk in self._stream_deterministic_response(result.response_text, sources):
            yield chunk
        await self._persist_turn(
            session_id,
            query,
            result.response_text,
            knowledge_base=leadership_meta,
            client_ip=client_ip,
            routing_target="EBLHOME_LEADERSHIP",
            user_id=user_id,
        )

    async def _stream_soc_response(
        self, query: str, session_id: str, client_ip: Optional[str], user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        result = self.soc_handler.lookup(query, self.soc_db)
        sources = ["EBL Home Schedule of Charges"]
        meta = f"soc:term={result.search_term};found={result.found}" if result.search_term else None
        async for chunk in self._stream_deterministic_response(result.response_text, sources):
            yield chunk
        await self._persist_turn(
            session_id, query, result.response_text, knowledge_base=meta,
            client_ip=client_ip, routing_target="EBLHOME_SOC", user_id=user_id,
        )

    async def _stream_proposals_response(
        self, query: str, session_id: str, client_ip: Optional[str], user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        result = self.proposals_handler.lookup(query, self.proposals_db)
        sources = ["EBL Home Proposal Updates"]
        meta = f"proposals:term={result.search_term};found={result.found}" if result.search_term else None
        async for chunk in self._stream_deterministic_response(result.response_text, sources):
            yield chunk
        await self._persist_turn(
            session_id, query, result.response_text, knowledge_base=meta,
            client_ip=client_ip, routing_target="EBLHOME_PROPOSALS", user_id=user_id,
        )

    async def _stream_circulars_response(
        self, query: str, session_id: str, client_ip: Optional[str], user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        result = self.circulars_handler.lookup(query, self.circulars_db)
        sources = ["EBL Home Circulars"]
        meta = f"circulars:term={result.search_term};found={result.found}" if result.search_term else None
        async for chunk in self._stream_deterministic_response(result.response_text, sources):
            yield chunk
        await self._persist_turn(
            session_id, query, result.response_text, knowledge_base=meta,
            client_ip=client_ip, routing_target="EBLHOME_CIRCULARS", user_id=user_id,
        )

    async def _get_location_context(self, query: str) -> str:
        """
        Get location context from location service.
        
        Args:
            query: Natural language query about locations
        
        Returns:
            Formatted location information string
        """
        try:
            # Use a higher limit so "area" queries can return the full set (or close to it),
            # enabling accurate "and X more" messaging.
            location_result = await self.location_client.get_locations(query, limit=200)
            
            if location_result:
                formatted = self.location_client.format_location_response(location_result, query)
                logger.info(f"[LOCATION_SERVICE] Location context retrieved: {location_result.get('total', 0)} locations")
                return formatted
            else:
                logger.warning(f"[LOCATION_SERVICE] Location service returned no results for query: '{query}'")
                return "Location information is not available at the moment. Please try again later."
                
        except Exception as e:
            logger.error(f"[LOCATION_SERVICE] Error getting location context: {e}")
            return "Location information is not available at the moment. Please try again later."
    
    def _check_policy_entities(self, query: str) -> tuple[bool, Optional[str]]:
        """
        Check if a policy query has required entities.
        Returns: (has_required_entities, clarification_question_if_missing)
        """
        query_lower = query.lower().strip()
        
        # Common policy names/identifiers that might be mentioned
        policy_identifiers = [
            'aml', 'kyc', 'cdd', 'ofac', 'pep', 'sanctions',
            'anti money laundering', 'know your customer', 'customer due diligence',
            'money laundering', 'politically exposed person',
            'credit policy', 'lending policy', 'loan policy', 'card policy',
            'account policy', 'deposit policy', 'withdrawal policy',
            'transaction policy', 'compliance policy', 'risk policy',
            'fraud policy', 'operational policy', 'internal policy',
            'gap policy', 'code of conduct', 'dress code', 'employee policy'
        ]
        
        # Account types that might be relevant
        account_types = [
            'savings', 'current', 'fixed deposit', 'fd', 'rd', 'recurring deposit',
            'corporate', 'commercial', 'retail', 'personal', 'business',
            'super saver', 'stellar', 'platinum', 'gold', 'silver'
        ]
        
        # Customer types
        customer_types = [
            'corporate', 'commercial', 'retail', 'personal', 'individual',
            'business', 'sme', 'small medium enterprise', 'enterprise'
        ]
        
        # Check if query mentions a specific policy name using patterns:
        # - "X policy" (e.g., "GAP policy", "AML policy")
        # - "policy X" (e.g., "policy regarding socks")
        # - Known policy identifiers
        has_policy_name = False
        
        # Pattern 1: Check known policy identifiers first (most reliable)
        if any(identifier in query_lower for identifier in policy_identifiers):
            has_policy_name = True
        
        # Pattern 2: "X policy" - look for any word/phrase before "policy" that's not generic
        # This handles: "GAP policy", "the GAP policy", "AML policy", "what does the GAP policy say"
        generic_words = {'the', 'a', 'an', 'this', 'that', 'what', 'which', 'some', 'any', 'does', 'say', 'is', 'are', 'was', 'were'}
        
        # Find all instances of "X policy" pattern
        policy_before_pattern = r'\b([a-z]+(?:\s+[a-z]+)?)\s+policy\b'
        matches = re.findall(policy_before_pattern, query_lower)
        if matches:
            for match in matches:
                match_clean = match.strip().lower()
                # If it's not a generic word, consider it a policy name
                if match_clean and match_clean not in generic_words:
                    has_policy_name = True
                    break
        
        # Pattern 3: "policy regarding/about/for X" - indicates a specific policy is being discussed
        if re.search(r'\bpolicy\s+(?:regarding|about|for|on|concerning|in|of|say|state|mention|specify|require|allow|prohibit)', query_lower):
            has_policy_name = True
        
        # Pattern 4: If query has "policy" and asks about a specific topic, assume policy name is present
        # e.g., "what does the GAP policy say about socks" - has "policy" and "socks" (specific topic)
        # e.g., "what does the policy say about X" - has "policy" and topic X
        if 'policy' in query_lower:
            # Check if there's a specific topic/subject mentioned (not just "policy" alone)
            # Look for words after "policy" that suggest a specific question
            has_specific_topic = re.search(
                r'policy\s+(?:say|state|mention|specify|require|allow|prohibit|regarding|about|for|on|concerning|in|of)\s+[a-z]+',
                query_lower
            )
            if has_specific_topic:
                has_policy_name = True
        
        # If a specific policy is mentioned, allow it to proceed (don't ask for clarification)
        if has_policy_name:
            return (True, None)
        
        # Safety check: If query has "policy" and mentions a specific topic/subject, allow it through
        # This catches cases like "what does the GAP policy say about socks" where the policy name
        # might not have been detected but there's clearly a specific question being asked
        if 'policy' in query_lower:
            # Check if there's substantive content beyond just "what is the policy?"
            # Look for: specific topics, action verbs, or content after "policy"
            has_substantive_content = (
                # Has a topic/subject mentioned (more than just "policy")
                len(query_lower.split()) > 4 or
                # Has action verbs that suggest a specific question
                any(word in query_lower for word in ['say', 'state', 'mention', 'specify', 'require', 'allow', 'prohibit', 'regarding', 'about', 'for', 'on', 'concerning']) or
                # Has "does" or "do" which suggests asking about something specific
                'does' in query_lower or 'do ' in query_lower
            )
            
            # Only ask for clarification if it's truly vague (like "what is the policy?")
            is_truly_vague = (
                query_lower in ['what is the policy?', 'what is policy?', 'tell me about policy', 'explain policy'] or
                (len(query_lower.split()) <= 4 and 'policy' in query_lower and not has_substantive_content)
            )
            
            if not is_truly_vague:
                # Has enough context, allow it through
                return (True, None)
        
        # Check if query is asking about policy in general (e.g., "what is the policy?")
        # Only trigger if it's truly general without any specific policy mentioned
        is_general_policy_query = (
            ('what' in query_lower and 'policy' in query_lower and not has_policy_name) or
            ('tell me' in query_lower and 'policy' in query_lower and not has_policy_name) or
            ('explain' in query_lower and 'policy' in query_lower and not has_policy_name)
        )
        
        # If it's a general policy query without context, we need clarification
        if is_general_policy_query:
            # Check if account type or customer type is mentioned
            has_account_type = any(acc_type in query_lower for acc_type in account_types)
            has_customer_type = any(cust_type in query_lower for cust_type in customer_types)
            
            if not has_account_type and not has_customer_type:
                return (False, "I'd be happy to help you with policy information. Could you please specify which policy you're asking about? For example:\n- AML (Anti-Money Laundering) policy\n- KYC (Know Your Customer) policy\n- Credit/Lending policy\n- GAP policy\n- Code of Conduct policy\n- Or any other specific policy name")
        
        # Check for queries that need account type context
        # e.g., "what is the policy for account?" - needs account type
        # But only if no specific policy is mentioned
        if 'policy' in query_lower and ('account' in query_lower or 'deposit' in query_lower) and not has_policy_name:
            if not any(acc_type in query_lower for acc_type in account_types):
                return (False, "To provide accurate policy information, could you please specify the account type? For example:\n- Savings account\n- Current account\n- Fixed Deposit (FD)\n- Recurring Deposit (RD)\n- Corporate account\n- Or any other specific account type")
        
        # Check for queries that need customer type context
        # e.g., "what is the policy for customer?" - needs customer type
        # But only if no specific policy is mentioned
        if 'policy' in query_lower and ('customer' in query_lower or 'client' in query_lower) and not has_policy_name:
            if not any(cust_type in query_lower for cust_type in customer_types):
                return (False, "To provide accurate policy information, could you please specify the customer type? For example:\n- Corporate customer\n- Retail/Personal customer\n- Business/SME customer\n- Or any other specific customer category")
        
        # All required entities are present
        return (True, None)
    
    def _build_loan_product_line_list_response(self) -> str:
        """
        Deterministic product-line list response for broad loan-product queries.
        Keep it high-level and ask the user which product they want details for next.
        """
        lines = [
            "Here are Eastern Bank PLC.'s loan product lines (at a glance):",
            "",
            "- Home Loan (property purchase/construction/renovation)",
            "- Auto/Car Loan",
            "- Personal/Executive Loan (unsecured consumer loan)",
            "- Education Loan",
            "- Business/SME financing (working capital/term loan types)",
            "- Secured borrowing against deposits/securities (e.g., Fast Loan / Fast Cash facilities)",
            "",
            "Which one do you want details on? (e.g., eligibility, required documents, rate/fees, repayment/tenor, or how to apply)",
        ]
        return "\n".join(lines)
    
    def _get_knowledge_base(self, user_input: str, session_id: Optional[str] = None) -> str:
        """
        Determine which knowledge base to use based on query content.
        Implements 4-tier KB strategy: Overview / Product / Policy / Investor
        
        Priority order (most specific first):
        1. Organizational Overview → ebl_website (customer-facing, filtered)
        2. Banking Products → ebl_products (if exists, else ebl_website)
        3. Policies/Compliance → ebl_policies (if exists, else ebl_website)
        4. Financial/Investor → ebl_financial_reports (investor content)
        5. Other specialized KBs (milestones, user docs, employees)
        
        Note: This method should NOT be called when disambiguation state exists (handled at process_chat level).
        Disambiguation resolution is a TERMINAL conversational state - once resolved, orchestrator exits immediately.
        """
        # Priority order (most specific first):
        
        # 0. CRITICAL: Organizational overview queries FIRST (before financial reports)
        # These need customer-facing content, NOT investor/financial content
        # Route to ebl_website with explicit filtering
        if self._is_organizational_overview_query(user_input):
            logger.info(f"[ROUTING] Query detected as organizational overview → using 'ebl_website' with customer-facing filter")
            return "ebl_website"  # Will be filtered by prompt instructions + post-retrieval filtering
        
        # 1. Banking product queries → ebl_products knowledge base (if exists)
        # Fallback to ebl_website if ebl_products doesn't exist
        if self._is_banking_product_query(user_input):
            # Check if ebl_products KB exists (could be enhanced with KB existence check)
            # For now, route to ebl_products - LightRAG will handle if it doesn't exist
            logger.info(f"[ROUTING] Query detected as banking product → using 'ebl_products'")
            return "ebl_products"  # Dedicated products KB
        
        # 2. Compliance/Policy queries → ebl_policies knowledge base (if exists)
        # Fallback to ebl_website if ebl_policies doesn't exist
        if self._is_compliance_query(user_input):
            logger.info(f"[ROUTING] Query detected as compliance/policy → using 'ebl_policies'")
            return "ebl_policies"  # Dedicated policies KB
        
        # 3. Financial reports/investor queries → ebl_financial_reports knowledge base
        # This is the investor-tier KB
        if self._is_financial_report_query(user_input):
            logger.info(f"[ROUTING] Query detected as financial report/investor → using 'ebl_financial_reports'")
            return "ebl_financial_reports"  # Investor content KB
        
        # 4. Management queries → ebl_website (contains management info)
        if self._is_management_query(user_input):
            logger.info(f"[ROUTING] Query detected as management → using 'ebl_website'")
            return "ebl_website"  # Management info is in ebl_website knowledge base
        
        # 5. Milestone queries → ebl_milestones knowledge base
        if self._is_milestone_query(user_input):
            logger.info(f"[ROUTING] Query detected as milestone → using 'ebl_milestones'")
            return "ebl_milestones"
        
        # 6. User document queries → user documents knowledge base
        if self._is_user_document_query(user_input):
            logger.info(f"[ROUTING] Query detected as user document → using 'ebl_user_documents'")
            return "ebl_user_documents"
        
        # 7. Employee queries → employees knowledge base (if exists)
        if self._is_employee_query(user_input):
            logger.info(f"[ROUTING] Query detected as employee → using 'ebl_employees'")
            return "ebl_employees"
        
        # 8. Default to configured knowledge base (usually ebl_website)
        default_kb = self.lightrag_client.knowledge_base or "ebl_website"
        logger.info(f"[ROUTING] Query using default knowledge base: '{default_kb}'")
        return default_kb

    async def diagnose_routing(
        self,
        query: str,
        session_id: Optional[str] = None,
        knowledge_base: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return a structured routing decision for debugging/regression tests.

        This method is designed to be:
        - Safe (no OpenAI calls)
        - Explainable (returns matched booleans + final target)
        """
        decision = await self.routing_engine.decide(
            query=query,
            session_id=session_id,
            knowledge_base=knowledge_base,
            client_ip=client_ip,
        )

        return {
            "query": decision.query,
            "session_id": session_id,
            "effective_session_id": decision.effective_session_id,
            "conversation_key": decision.conversation_key,
            "pending_disambiguation": decision.pending_disambiguation,
            "target": decision.target,
            "knowledge_base": decision.knowledge_base,
            "signals": decision.signals,
        }
    

    async def _handle_routing_disambiguation(
        self,
        *,
        query: str,
        conversation_key: str,
        pending_disambiguation: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Resolve routing disambiguation and return either a prompt response
        or a resolved target to continue routing.
        """
        disambiguation_type = pending_disambiguation.get("disambiguation_type")
        options = pending_disambiguation.get("options", [])
        prompt_message = pending_disambiguation.get("prompt_message") or "Please reply with a valid option."
        extra = pending_disambiguation.get("extra") or {}
        base_query = (extra.get("base_query") or query).strip()

        selected_option = self._resolve_selection(query, options)
        if not selected_option:
            return {"response": prompt_message}

        target = selected_option.get("route_target")
        if disambiguation_type == "ROUTING":
            if target == "FEE_ENGINE":
                fee_candidates = extra.get("fee_candidates") or [
                    "FEE_ENGINE_CARDS",
                    "FEE_ENGINE_RETAIL_ASSETS",
                    "FEE_ENGINE_SKYBANKING",
                ]
                if len(fee_candidates) == 1:
                    await self._clear_disambiguation_state_any(conversation_key)
                    return {"resolved_target": fee_candidates[0], "resolved_query": base_query}

                fee_options = self._build_fee_type_disambiguation_options(fee_candidates)
                fee_prompt = self._build_fee_type_disambiguation_prompt(fee_candidates)
                state = {
                    "product_line": "ROUTING",
                    "charge_type": "ROUTING_FEE_TYPE",
                    "disambiguation_type": "ROUTING_FEE_TYPE",
                    "options": fee_options,
                    "prompt_message": fee_prompt,
                    "extra": {"base_query": base_query},
                }
                await self._set_disambiguation_state_any(conversation_key, state)
                return {"response": fee_prompt}

            await self._clear_disambiguation_state_any(conversation_key)
            return {"resolved_target": target, "resolved_query": base_query}

        if disambiguation_type == "ROUTING_FEE_TYPE":
            if target in {"FEE_ENGINE_CARDS", "FEE_ENGINE_RETAIL_ASSETS", "FEE_ENGINE_SKYBANKING"}:
                await self._clear_disambiguation_state_any(conversation_key)
                return {"resolved_target": target, "resolved_query": base_query}
            return {"response": prompt_message}

        return {"response": prompt_message}
    
    async def _get_card_rates_context(self, query: str, session_id: Optional[str] = None, conversation_key: Optional[str] = None) -> str:
        """
        Call fee-engine microservice to get deterministic fee/rate data for card queries.
        Uses the new fee-engine service (port 8003) instead of old card_rates_service (port 8002).
        Returns a formatted text block to include before LightRAG context.
        
        Args:
            query: User query
            session_id: Session ID (for backward compatibility, but conversation_key should be used for disambiguation state)
            conversation_key: Stable conversation key for disambiguation state (FIX #1: session continuity)
        """
        try:
            fee_client = self.fee_engine_client
            logger.info(f"[FEE_ENGINE] Attempting to calculate fee for query: '{query}'")
            # Try to calculate fee using fee engine
            fee_result = await fee_client.calculate_fee(query)
            
            if fee_result:
                logger.info(f"[FEE_ENGINE] Fee engine returned status: {fee_result.get('status')}, charge_type: {fee_result.get('charge_type')}")
            
            # Handle retail asset charges NEEDS_DISAMBIGUATION (multiple charges found without loan_product)
            if fee_result and fee_result.get("status") == "NEEDS_DISAMBIGUATION" and "charges" in fee_result:
                formatted = fee_client.format_fee_response(fee_result, query=query)
                context = f"{self.OFFICIAL_RETAIL_ASSET_HEADER}\n{formatted}\n\nPlease specify which loan product you're interested in to get the exact processing fee details."
                logger.info(f"[FEE_ENGINE] Retail asset charge needs disambiguation for query: '{query}'")
                
                # Store disambiguation state for session
                # FIX #3: Use deduped_options from formatted response if available (matches UI exactly)
                # PHASE 2 FIX: Always use conversation_key for state storage (not session_id check)
                state_key = conversation_key if conversation_key else session_id
                if state_key:
                    # Always initialize these to avoid UnboundLocalError when using deduped_options
                    is_context_disambiguation = False
                    is_description_disambiguation = False

                    # Check if deduped_options are available (from _format_retail_asset_disambiguation_response)
                    deduped_options = fee_result.get("deduped_options")
                    if deduped_options:
                        # Use the exact same options that were displayed in the UI
                        options = deduped_options
                        logger.info(f"[DISAMBIGUATION] Using deduped_options from formatted response ({len(options)} options)")
                    else:
                        # Fallback: build options from charges (should not happen if format_fee_response is called)
                        charges = fee_result.get("charges", [])
                        if charges:
                            # Check if this is a second-level disambiguation (same loan_product, different charge_contexts)
                            loan_products = set(c.get("loan_product") for c in charges if c.get("loan_product"))
                            is_context_disambiguation = len(loan_products) == 1 and any(c.get("charge_context") for c in charges)
                            
                            # Extract charge_type from first charge (all charges should have same charge_type after filtering)
                            charge_type = charges[0].get("charge_type", "") if charges else ""
                            
                            # Extract options based on disambiguation type
                            # CRITICAL: Include charge_type in each option to ensure correct resolution
                            options = []
                            if is_context_disambiguation:
                                # Second-level: extract charge_context options (same loan_product, same charge_type, different contexts)
                                seen_contexts = set()
                                for charge in charges:
                                    charge_context = charge.get("charge_context")
                                    loan_product = charge.get("loan_product")
                                    charge_type_option = charge.get("charge_type", charge_type)  # Use charge_type from charge, fallback to stored
                                    if charge_context and charge_context not in seen_contexts:
                                        seen_contexts.add(charge_context)
                                        options.append({
                                            "loan_product": loan_product,
                                            "loan_product_name": charge.get("loan_product_name", loan_product),
                                            "charge_type": charge_type_option,  # CRITICAL: Include charge_type for each option
                                            "charge_context": charge_context,
                                        })
                            else:
                                # First-level: extract loan_product options (different loan products, same charge_type)
                                seen_products = set()
                                for charge in charges:
                                    loan_product = charge.get("loan_product")
                                    charge_type_option = charge.get("charge_type", charge_type)  # Use charge_type from charge, fallback to stored
                                    if loan_product and loan_product not in seen_products:
                                        seen_products.add(loan_product)
                                        options.append({
                                            "loan_product": loan_product,
                                            "loan_product_name": charge.get("loan_product_name", loan_product),
                                            "charge_type": charge_type_option,  # CRITICAL: Include charge_type for each option
                                            "charge_context": charge.get("charge_context"),  # Include if present
                                        })
                        else:
                            options = []
                    
                    if options:
                        # Determine disambiguation type robustly based on option fields.
                        loan_products_in_options = {
                            (opt.get("loan_product") or "").lower()
                            for opt in options
                            if opt.get("loan_product")
                        }
                        all_same_loan_product = len(loan_products_in_options) == 1 and any(opt.get("loan_product") for opt in options)
                        has_charge_context = any(opt.get("charge_context") for opt in options)
                        has_description_fields = any(opt.get("answer_text") or opt.get("charge_description") for opt in options)

                        if all_same_loan_product and has_charge_context:
                            is_context_disambiguation = True
                            is_description_disambiguation = False
                        elif all_same_loan_product and has_description_fields:
                            is_context_disambiguation = False
                            is_description_disambiguation = True

                        # Extract charge_type from first option (all options should have same charge_type)
                        charge_type = options[0].get("charge_type", "") if options else ""
                        from datetime import date
                        as_of_date = str(date.today())
                        
                        # Determine disambiguation type and build prompt message
                        if is_context_disambiguation:
                            disambiguation_type = "CHARGE_CONTEXT"
                        elif is_description_disambiguation:
                            disambiguation_type = "DESCRIPTION"
                        else:
                            disambiguation_type = "LOAN_PRODUCT"
                        # Use the formatted message as the prompt (will be stored and reused on reprompt)
                        prompt_message = formatted  # This is the exact message to reuse
                        
                        # CRITICAL: Store state BEFORE returning (ensures state is available for next message)
                        # PHASE 2 FIX: Always use conversation_key for disambiguation state (stable across turns)
                        try:
                            stored = await self.redis_cache.store_disambiguation_state(
                                session_id=state_key,
                                product_line="RETAIL_ASSETS",
                                charge_type=charge_type,
                                as_of_date=as_of_date,
                                options=options,
                                disambiguation_type=disambiguation_type,
                                prompt_message=prompt_message,
                                extra=None,
                            )
                        except Exception as e:
                            stored = False
                            logger.warning(f"[DISAMBIGUATION] Redis store failed for conversation_key {state_key}; using local fallback: {e}")
                        if stored:
                            logger.info(f"[DISAMBIGUATION] Stored disambiguation state for conversation_key {state_key} with {len(options)} options (type={disambiguation_type})")
                        else:
                            # Redis unavailable: store locally so user can still reply "1", "2", etc.
                            await self._store_disambiguation_state_fallback(
                                state_key=state_key,
                                state={
                                    "product_line": "RETAIL_ASSETS",
                                    "charge_type": charge_type,
                                    "as_of_date": as_of_date,
                                    "options": options,
                                    "disambiguation_type": disambiguation_type,
                                    "prompt_message": prompt_message,
                                },
                                ttl_seconds=300,
                            )
                            logger.info(f"[DISAMBIGUATION] Stored disambiguation state locally for conversation_key {state_key} with {len(options)} options (type={disambiguation_type})")
                
                return context

            # Handle card-fee NEEDS_DISAMBIGUATION (e.g., missing card_product)
            if fee_result and fee_result.get("status") == "NEEDS_DISAMBIGUATION":
                options = fee_result.get("options") or []
                charge_type = fee_result.get("charge_type") or ""

                if options:
                    body = fee_client._format_card_fee_disambiguation_response(fee_result, query=query)
                    prompt = "\n".join([
                        self.OFFICIAL_CARD_RATES_HEADER,
                        self.FEE_ENGINE_SOURCE,
                        "",
                        body,
                    ])

                    # Store disambiguation state for the next user message
                    from datetime import date
                    state_key = conversation_key if conversation_key else session_id
                    if state_key:
                        try:
                            stored = await self.redis_cache.store_disambiguation_state(
                                session_id=state_key,
                                product_line="CREDIT_CARDS",
                                charge_type=charge_type,
                                as_of_date=str(date.today()),
                                options=options,
                                disambiguation_type="CARD_PRODUCT",
                                prompt_message=prompt,
                                extra={"base_query": query},
                            )
                        except Exception as e:
                            stored = False
                            logger.warning(f"[DISAMBIGUATION] Redis store failed for conversation_key {state_key}; using local fallback: {e}")
                        if not stored:
                            await self._store_disambiguation_state_fallback(
                                state_key=state_key,
                                state={
                                    "product_line": "CREDIT_CARDS",
                                    "charge_type": charge_type,
                                    "as_of_date": str(date.today()),
                                    "options": options,
                                    "disambiguation_type": "CARD_PRODUCT",
                                    "prompt_message": prompt,
                                    "extra": {"base_query": query},
                                },
                                ttl_seconds=300,
                            )

                    return prompt

                message = fee_result.get("message") or "Please specify the card product to answer this fee question."
                return "\n".join([
                    self.OFFICIAL_CARD_RATES_HEADER,
                    self.FEE_ENGINE_SOURCE,
                    "",
                    message,
                ])
            
            # Handle retail asset charges (status = "FOUND")
            if fee_result and fee_result.get("status") == "FOUND" and "charges" in fee_result:
                formatted = fee_client.format_fee_response(fee_result, query=query)
                context = f"{self.OFFICIAL_RETAIL_ASSET_HEADER}\n{formatted}\n\nThis information is from the Retail Asset Charges Schedule and is authoritative."
                logger.info(f"[FEE_ENGINE] Retail asset charge found and formatted for query: '{query}'")
                return context
            
            # Handle Skybanking fees (status = "FOUND")
            if fee_result and fee_result.get("status") == "FOUND" and "fees" in fee_result:
                formatted = fee_client.format_fee_response(fee_result, query=query)
                context = f"{self.OFFICIAL_SKYBANKING_HEADER}\n{formatted}\n\nThis information is from the Skybanking Fees Schedule and is authoritative."
                logger.info(f"[FEE_ENGINE] Skybanking fee found and formatted for query: '{query}'")
                return context
            
            if fee_result and fee_result.get("status") == "CALCULATED":
                formatted = fee_client.format_fee_response(fee_result, query=query)
                charge_type = fee_result.get("charge_type", "")
                
                # Build base lines - clean format without emoji warnings
                lines = [
                    self.OFFICIAL_CARD_RATES_HEADER,
                    self.FEE_ENGINE_SOURCE,
                    "",
                    formatted,
                ]
                lines.append("")
                return "\n".join(lines)
            elif fee_result and fee_result.get("status") == "REQUIRES_NOTE_RESOLUTION":
                # Use the message from fee engine (already includes note text if available)
                message = fee_result.get("message", "")
                if not message:
                    # Fallback if message is missing
                    note_ref = fee_result.get("note_reference", "Unknown")
                    message = f"Fee depends on external note definition: Note {note_ref}. Please refer to the card charges schedule for Note {note_ref} details."
                
                # Extract note reference and text for formal formatting
                note_ref = fee_result.get("note_reference", "")
                if " — " in message:
                    note_text = message.split(" — ", 1)[1]
                else:
                    note_text = message
                
                lines = [
                    self.OFFICIAL_CARD_RATES_HEADER,
                    self.FEE_ENGINE_SOURCE,
                    "",
                    f"Note Reference: {note_ref}",
                    "",
                    note_text
                ]
                return "\n".join(lines)
            elif fee_result and fee_result.get("status") == "NO_RULE_FOUND":
                logger.warning(f"[FEE_ENGINE] No rule found for query: '{query}', charge_type: {fee_result.get('charge_type')}, message: {fee_result.get('message')}")
                
                # Check if this is a retail asset query - handle NO_RULE_FOUND for retail assets
                product_line = fee_client._detect_product_line(query)
                if product_line == "RETAIL_ASSETS" or product_line == "CREDIT_CARDS":
                    if product_line == "CREDIT_CARDS":
                        logger.info(f"[FEE_ENGINE] No card fee rule found for '{query}' — returning deterministic not-found response")
                        return self._build_card_fee_not_found_context()
                if product_line == "RETAIL_ASSETS":
                    # Format the retail asset NO_RULE_FOUND response using format_fee_response
                    formatted = fee_client.format_fee_response(fee_result, query=query)
                    context = f"OFFICIAL RETAIL ASSET CHARGES INFORMATION\n{formatted if formatted else 'The requested retail asset charge information is not found in the Retail Asset Charges Schedule.'}\n\nPlease verify the loan product details and try again, or contact Eastern Bank PLC. directly for this specific detail."
                    return context
                if product_line == "SKYBANKING":
                    formatted = fee_client.format_fee_response(fee_result, query=query)
                    if not formatted:
                        formatted = "The requested fee information is not found in the Skybanking Fees Schedule."
                    context = (
                        f"{self.OFFICIAL_SKYBANKING_HEADER}\n"
                        f"{self.FEE_ENGINE_SOURCE_SKYBANKING}\n\n"
                        f"{formatted}\n\n"
                        "Please verify the Skybanking service details and try again, or contact Eastern Bank PLC. directly for this specific detail."
                    )
                    return context
                
                # Return deterministic not-found message for card charges instead of empty string
                lines = [
                    "=" * 70,
                    self.OFFICIAL_CARD_RATES_HEADER,
                    self.FEE_ENGINE_SOURCE,
                    "=" * 70,
                    "",
                    "The requested fee information is not found in the Card Charges and Fees Schedule (effective 01 Jan 2026).",
                    "",
                    "This may be because:",
                    "- The specific card type, network, or product combination is not covered",
                    "- The charge type is not available for this card",
                    "- Additional information is required (e.g., card network, product name)",
                    "",
                    "Please verify the card details and try again, or contact the bank for assistance.",
                    "",
                    "=" * 70,
                    ""
                ]
                return "\n".join(lines)
            elif fee_result and fee_result.get("status") == "FX_RATE_REQUIRED":
                logger.info(f"[FEE_ENGINE] FX rate required for query: '{query}'")
                message = fee_result.get("message", "Fee rule exists but currency conversion required.")
                lines = [
                    "=" * 70,
                    self.OFFICIAL_CARD_RATES_HEADER,
                    self.FEE_ENGINE_SOURCE,
                    "=" * 70,
                    "",
                    f"The fee information requires currency conversion: {message}",
                    "",
                    "The requested fee information is not available in the requested currency in the Card Charges and Fees Schedule (effective 01 Jan 2026).",
                    "",
                    "Please contact the bank for current exchange rates and fee conversion.",
                    "",
                    "=" * 70,
                    ""
                ]
                return "\n".join(lines)
            else:
                status = fee_result.get('status') if fee_result else 'None'
                logger.info(f"[FEE_ENGINE] Fee engine returned status '{status}', not CALCULATED. Result: {fee_result}")
                
                # Check if this is a retail asset query - don't fall back to card fees
                product_line = fee_client._detect_product_line(query)
                if product_line == "RETAIL_ASSETS":
                    formatted = fee_client.format_fee_response(fee_result, query=query) if fee_result else "The requested retail asset charge information is not found in the Retail Asset Charges Schedule."
                    context = f"{self.OFFICIAL_RETAIL_ASSET_HEADER}\n{formatted}\n\nPlease verify the loan product details and try again, or contact Eastern Bank PLC. directly for this specific detail."
                    return context

                logger.info(f"[FEE_ENGINE] Unresolved status '{status}' for card query '{query}' — returning deterministic not-found response")
                return self._build_card_fee_not_found_context(
                    f"The requested fee information could not be retrieved (status: {status})."
                )
        except ImportError:
            logger.warning("[FEE_ENGINE] FeeEngineClient not available")
            # Return deterministic not-found message instead of falling back
            return self._build_card_fee_not_found_context("The fee engine service is not available.")
        except Exception as e:
            logger.error(f"[FEE_ENGINE] Error calling fee engine: {e}", exc_info=True)
            # If this is a retail-asset query, do NOT show card schedule headers.
            try:
                product_line = fee_client._detect_product_line(query) if 'fee_client' in locals() and fee_client else None
                if product_line == "RETAIL_ASSETS":
                    return (
                        f"{self.OFFICIAL_RETAIL_ASSET_HEADER}\n"
                        "An error occurred while retrieving retail asset charge information.\n\n"
                        "Please verify the loan product details and try again, or contact Eastern Bank PLC. directly for this specific detail."
                    )
            except Exception:
                pass

            # Default: deterministic card-fees error message (no fallback to old service)
            return self._build_card_fee_not_found_context("An error occurred while retrieving fee information.")
        
        # No fallback to old card_rates_service - fee engine is the only source
        # If we reach here, fee engine was not available or returned no result
        # Check product_line to avoid falling back to card fees for retail assets
        try:
            product_line = fee_client._detect_product_line(query)
            if product_line == "RETAIL_ASSETS":
                context = (
                    "OFFICIAL RETAIL ASSET CHARGES INFORMATION\n"
                    "The requested retail asset charge information is not found in the Retail Asset Charges Schedule.\n\n"
                    "Please verify the loan product details and try again, or contact Eastern Bank PLC. directly for this specific detail."
                )
                return context
        except:
            pass  # If detection fails, continue with default card fees message
        
        # Return deterministic not-found message for card fees (NEVER return empty string for fee queries)
        return self._build_card_fee_not_found_context("The fee engine service returned no result.")

    def _build_card_fee_not_found_context(self, detail: Optional[str] = None) -> str:
        """Build the terminal card-fee not-found response used by streaming and sync paths."""
        lines = [
            self.OFFICIAL_CARD_RATES_HEADER,
            self.FEE_ENGINE_SOURCE,
            "",
            detail or "The requested fee information is not found in the Card Charges and Fees Schedule (effective 01 Jan 2026).",
            "",
            "Please verify the card details and try again, or contact the bank for assistance.",
        ]
        return "\n".join(lines)
    
    # Filename/title markers that identify investor/financial documents. Used to
    # exclude annual reports & financial statements from organizational-overview
    # answers (which should use customer-facing website content instead).
    _FINANCIAL_DOC_MARKERS = (
        "annual report", "annual-report", "annual_report",
        "financial statement", "financial-statement", "financial_statement",
        "financial statements", "financial-statements", "financial_statements",
        "half-yearly", "half yearly", "half_yearly", "halfyearly",
        "quarterly", "balance sheet", "balance-sheet", "income statement",
        "cash flow", "audited", "auditors report", "auditor's report",
        "profit and loss", "profit & loss",
    )

    @classmethod
    def _is_financial_document(cls, name: Optional[str]) -> bool:
        """True if a source/document name looks like an annual report or
        financial statement (to be excluded from org-overview answers)."""
        if not name:
            return False
        text = str(name).lower()
        if any(marker in text for marker in cls._FINANCIAL_DOC_MARKERS):
            return True
        # Quarter tokens like "q1"/"q3" combined with a year or "report".
        if re.search(r"\bq[1-4]\b", text) and (
            re.search(r"\b20\d{2}\b", text) or "report" in text or "statement" in text
        ):
            return True
        return False

    def _format_lightrag_context(
        self, 
        lightrag_response: Dict[str, Any],
        filter_financial_docs: bool = False
    ) -> tuple[str, list[str]]:
        """
        Format LightRAG response into context string and extract sources.
        
        Args:
            lightrag_response: Response from LightRAG
            filter_financial_docs: If True, exclude chunks from annual reports/financial statements
        
        Returns: (context_string, sources_list)
        """
        context_parts = []
        sources = []
        seen_sources = set()  # To avoid duplicates
        excluded_count = 0  # Track how many chunks were excluded
        logged_missing_doc_meta = False
        payload = lightrag_response.get("data") if isinstance(lightrag_response.get("data"), dict) else lightrag_response
        import os
        import json
        def _normalize_doc_name(name: str) -> str:
            cleaned = (name or "").strip()
            if not cleaned:
                return ""
            # Normalize separators and whitespace, keep ASCII.
            cleaned = re.sub(r"[_\-]+", " ", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            return cleaned

        def _format_source_label(source: str, doc_name: str) -> str:
            source_clean = (source or "").strip()
            doc_clean = _normalize_doc_name(doc_name)

            # If doc name is missing, derive a readable name from the source path.
            if not doc_clean and source_clean:
                base = os.path.basename(source_clean)
                if base:
                    doc_clean = _normalize_doc_name(os.path.splitext(base)[0])

            if doc_clean and source_clean:
                if doc_clean.lower() in source_clean.lower():
                    return doc_clean
                return f"{doc_clean} ({source_clean})"
            if doc_clean:
                return doc_clean
            if source_clean:
                return source_clean
            return ""

        # IMPORTANT ANTI-HALLUCINATION POLICY:
        # Do NOT use LightRAG's own generated "response" text as context.
        # LightRAG's response is produced by its LLM and may hallucinate numbers/rates.
        # We only pass grounded evidence (entities/relationships/chunks) to OpenAI.
        #
        # Extract structured data (entities, relationships, chunks)
        # This is used for all queries to ensure responses are grounded in retrieved text.
        
        # Extract entities from knowledge graph
        if "entities" in payload:
            entities = payload.get("entities", [])
            if entities:
                if not context_parts:  # Only add header if we don't have response text
                    context_parts.append("Entities Data From Knowledge Graph(KG):")
                else:
                    context_parts.append("\n\nEntities Data From Knowledge Graph(KG):")
                for entity in entities[:5]:  # Limit to top 5
                    if isinstance(entity, dict):
                        name = entity.get("name", entity.get("entity_name", ""))
                        desc = entity.get("description", "")
                        if name or desc:
                            context_parts.append(f"- {name}: {desc}")
        
        # Extract relationships
        if "relationships" in payload:
            relationships = payload.get("relationships", [])
            if relationships:
                if not context_parts:
                    context_parts.append("Relationships Data From Knowledge Graph(KG):")
                else:
                    context_parts.append("\n\nRelationships Data From Knowledge Graph(KG):")
                for rel in relationships[:5]:  # Limit to top 5
                    if isinstance(rel, dict):
                        source = rel.get("source", rel.get("entity_a", ""))
                        relation = rel.get("relation", rel.get("relationship", ""))
                        target = rel.get("target", rel.get("entity_b", ""))
                        if source and relation and target:
                            context_parts.append(f"- {source} → {relation} → {target}")
        
        # Extract document chunks and their sources
        if "chunks" in payload:
            chunks = payload.get("chunks", [])
            if chunks:
                if not context_parts:
                    context_parts.append("Original Texts From Document Chunks(DC):")
                else:
                    context_parts.append("\n\nOriginal Texts From Document Chunks(DC):")
                for chunk in chunks[:10]:  # Limit to top 10
                    if isinstance(chunk, dict):
                        # Extract source from chunk metadata first (for filtering)
                        # Try multiple possible field names for source
                        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
                        source = (
                            chunk.get("source") or
                            chunk.get("file_name") or
                            chunk.get("document") or
                            chunk.get("file") or
                            chunk.get("doc_name") or
                            chunk.get("file_path") or
                            chunk.get("path") or
                            chunk.get("filename") or
                            metadata.get("source") or
                            metadata.get("file_name") or
                            metadata.get("document") or
                            metadata.get("file") or
                            metadata.get("doc_name") or
                            metadata.get("file_path") or
                            metadata.get("path") or
                            metadata.get("filename") or
                            ""
                        )
                        doc_name = (
                            chunk.get("document_name") or
                            chunk.get("doc_title") or
                            chunk.get("document_title") or
                            chunk.get("title") or
                            chunk.get("name") or
                            metadata.get("document_name") or
                            metadata.get("doc_title") or
                            metadata.get("document_title") or
                            metadata.get("title") or
                            metadata.get("name") or
                            ""
                        )
                        
                        # CRITICAL: Filter out financial documents if requested (for org overview queries)
                        filter_target = source or doc_name
                        if filter_financial_docs and filter_target and self._is_financial_document(filter_target):
                            excluded_count += 1
                            logger.info(f"[FILTER] Excluding chunk from financial document: {filter_target}")
                            continue  # Skip this chunk
                        
                        text = chunk.get("text", chunk.get("content", ""))
                        if text:
                            context_parts.append(f"- {text}")
                        
                        # Add source to sources list (only if not filtered)
                        label = _format_source_label(source, doc_name)
                        if not logged_missing_doc_meta and not doc_name and (not source or "knowledge base" in source.lower()):
                            logger.info(
                                "[SOURCES] Missing document metadata in chunk. "
                                f"chunk_keys={list(chunk.keys())}, metadata_keys={list(metadata.keys())}, "
                                f"source={json.dumps(source)}"
                            )
                            logged_missing_doc_meta = True
                        if label and label not in seen_sources:
                            seen_sources.add(label)
                            sources.append(label)
                            logger.info(f"[SOURCES] Extracted source from chunk: {label}")
                
                # Log filtering results
                if filter_financial_docs and excluded_count > 0:
                    logger.info(f"[FILTER] Excluded {excluded_count} chunks from annual reports/financial statements")
        
        # Extract references if available (separate from chunks)
        # CRITICAL: Filter out financial document references for org overview queries
        if "references" in lightrag_response:
            references = lightrag_response.get("references", [])
            for ref in references:
                if isinstance(ref, str):
                    # Filter financial documents
                    if filter_financial_docs and self._is_financial_document(ref):
                        logger.info(f"[FILTER] Excluding reference from financial document: {ref}")
                        continue
                    if ref not in seen_sources:
                        seen_sources.add(ref)
                        sources.append(ref)
                elif isinstance(ref, dict):
                    ref_source = ref.get("source", ref.get("file_name", ref.get("document", "")))
                    ref_doc_name = ref.get("document_name", ref.get("doc_title", ref.get("document_title", ref.get("title", ref.get("name", "")))))
                    ref_meta = ref.get("metadata") if isinstance(ref.get("metadata"), dict) else {}
                    source = ref_source or ref_meta.get("source") or ref_meta.get("file_name") or ref_meta.get("document") or ref_meta.get("file_path") or ref_meta.get("path") or ref_meta.get("filename") or ""
                    doc_name = (
                        ref_doc_name or
                        ref_meta.get("document_name") or
                        ref_meta.get("doc_title") or
                        ref_meta.get("document_title") or
                        ref_meta.get("title") or
                        ref_meta.get("name") or
                        ""
                    )
                    # Filter financial documents
                    filter_target = source or doc_name
                    if filter_financial_docs and filter_target and self._is_financial_document(filter_target):
                        logger.info(f"[FILTER] Excluding reference from financial document: {filter_target}")
                        continue
                    label = _format_source_label(source, doc_name)
                    if label and label not in seen_sources:
                        seen_sources.add(label)
                        sources.append(label)
        
        # Final fallback: use response text even if it looks like a prompt
        if not context_parts and "response" in lightrag_response:
            # Keep as absolute last resort to avoid empty context, but label clearly.
            # (This should be rare because we request chunks from LightRAG.)
            context_parts.append("Source Data (unverified):")
            context_parts.append(lightrag_response["response"])
        
        context_str = "\n".join(context_parts) if context_parts else ""
        return context_str, sources

    def _extract_query_anchors(self, query: str) -> list[str]:
        """
        Extract anchor tokens from user query for chunk filtering.
        Goal: keep chunks that actually mention the named product/entity, reducing
        irrelevant context that can mislead the LLM.
        """
        q = (query or "").strip()
        if not q:
            return []
        ql = q.lower()
        import re

        # Tokenize into alphanumerics only
        tokens = re.findall(r"[a-z0-9]+", ql)
        if not tokens:
            return []

        stop = {
            "what", "is", "are", "tell", "me", "about", "please", "explain", "define",
            "the", "a", "an", "of", "for", "to", "in", "on", "and", "or", "with",
            "ebl", "eastern", "bank", "plc",
        }

        anchors: list[str] = []

        # If query includes "EBL X", anchor on X (often the product name)
        if "ebl" in tokens:
            try:
                i = tokens.index("ebl")
                if i + 1 < len(tokens):
                    nxt = tokens[i + 1]
                    if nxt and nxt not in stop:
                        anchors.append(nxt)
            except Exception:
                pass

        # Add any longer tokens (likely product names) excluding stop words
        for t in tokens:
            if len(t) >= 4 and t not in stop:
                anchors.append(t)

        # De-duplicate while preserving order
        seen = set()
        uniq: list[str] = []
        for a in anchors:
            if a not in seen:
                uniq.append(a)
                seen.add(a)

        # MetLife product aliasing: users often ask with informal names that don't appear in docs.
        # Ensure we keep MetLife-specific shorthand in anchors so chunk filtering doesn't drop it.
        # Example query: "Metlife My Childs Education Program" → docs may use "MCEPP".
        is_term_question = any(t in tokens for t in ["tenure", "term"]) or ("coverage" in tokens and "period" in tokens)

        if "metlife" in tokens and ("child" in tokens or "childs" in tokens) and "education" in tokens:
            if "mcepp" not in uniq:
                uniq.append("mcepp")
            if "my" in tokens and "child" in tokens and "education" in tokens:
                # common normalized phrase fragments
                for extra in ("education", "child", "metlife"):
                    if extra not in uniq:
                        uniq.append(extra)

        # For term/tenure questions, include likely section headers used in documents so
        # anchor filtering keeps "Coverage Period: X years" chunks even if they don't mention "MetLife".
        if is_term_question:
            for extra in ("coverage", "period", "policy", "plan", "premium", "payment", "years"):
                if extra not in uniq:
                    uniq.append(extra)
        return uniq[:8]

    def _is_term_intent_query(self, query: str) -> bool:
        ql = (query or "").lower()
        return any(k in ql for k in ["tenure", "plan term", "policy term", "term", "coverage period"])

    def _is_metlife_child_education_query(self, query: str) -> bool:
        ql = (query or "").lower()
        return "metlife" in ql and ("child" in ql or "childs" in ql) and "education" in ql

    def _extract_mcepp_plan_term_answer(self, query: str, context: str) -> Optional[str]:
        """
        Deterministic extractor to prevent hallucination on MetLife tenure/term questions.
        Looks for an explicit plan term range and returns it as the answer.
        """
        if not context:
            return None
        if not (self._is_term_intent_query(query) and self._is_metlife_child_education_query(query)):
            return None

        import re
        ctx = context
        ctx_lower = ctx.lower()

        # Find plan term ranges like:
        # - "Plan Term: 12 to 20 years"
        # - "Plan terms range from 12 to 20 years"
        term_patterns = [
            r"plan\s+term\s*:\s*(\d{1,2})\s*(?:to|-)\s*(\d{1,2})\s*years",
            r"plan\s+terms?\s+range\s+from\s*(\d{1,2})\s*(?:to|-)\s*(\d{1,2})\s*years",
        ]

        candidates = []
        for pat in term_patterns:
            for m in re.finditer(pat, ctx_lower, flags=re.IGNORECASE):
                start, end = m.start(), m.end()
                # Prefer matches that are close to MCEPP/My Child in context to avoid mixing products.
                window = ctx_lower[max(0, start - 800): min(len(ctx_lower), end + 800)]
                score = 0
                if "mcepp" in window:
                    score += 2
                if "my child" in window or "education protection" in window:
                    score += 2
                if "rules and limits" in window:
                    score += 1
                candidates.append((score, m.group(1), m.group(2), start))

        if not candidates:
            return None

        # Pick best-scoring match; tiebreaker earliest occurrence
        candidates.sort(key=lambda x: (-x[0], x[3]))
        _, lo, hi, _pos = candidates[0]

        # Optional constraint: age + term cannot exceed 27 years
        constraint_27 = None
        m27 = re.search(r"cannot\s+exceed\s+27\s+years", ctx_lower)
        if m27:
            constraint_27 = "The insured child’s age plus the plan term cannot exceed 27 years."

        # Premium paying term info (optional)
        ppt = None
        mppt = re.search(r"premium\s+pay(?:ing|ment)\s+term\s*:\s*([^\n]+)", ctx, flags=re.IGNORECASE)
        if mppt:
            # Keep it short; many docs say "2 years less than the Coverage Period."
            line = mppt.group(0).strip()
            if len(line) > 180:
                line = line[:180] + "..."
            ppt = line

        answer_lines = [f"The plan term (tenure) is {lo} to {hi} years."]
        if constraint_27:
            answer_lines.append(constraint_27)
        if ppt:
            answer_lines.append(ppt)
        return " ".join(answer_lines)

    def _filter_lightrag_chunks_for_query(self, lightrag_response: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Filter LightRAG chunks to those mentioning query anchors.
        This reduces irrelevant chunks (e.g., unrelated savings/deposit text) that can
        cause wrong product-type answers.
        """
        try:
            payload = lightrag_response.get("data") if isinstance(lightrag_response.get("data"), dict) else lightrag_response
            chunks = payload.get("chunks")
            if not isinstance(chunks, list) or not chunks:
                return lightrag_response

            anchors = self._extract_query_anchors(query)
            if not anchors:
                return lightrag_response

            def _chunk_text(c: Any) -> str:
                if isinstance(c, dict):
                    return (c.get("text") or c.get("content") or "")
                if isinstance(c, str):
                    return c
                return ""

            kept = []
            for c in chunks:
                txt = _chunk_text(c)
                tl = (txt or "").lower()
                if not tl:
                    continue
                if any(a in tl for a in anchors):
                    kept.append(c)

            # If filtering became too aggressive, keep original list
            if len(kept) >= 2:
                filtered = dict(lightrag_response)
                if payload is lightrag_response:
                    filtered["chunks"] = kept
                else:
                    data_copy = dict(payload)
                    data_copy["chunks"] = kept
                    filtered["data"] = data_copy
                return filtered

            return lightrag_response
        except Exception:
            return lightrag_response
    
    def _improve_query_for_lightrag(self, query: str) -> str:
        """
        Improve query phrasing for better LightRAG results
        Converts conversational queries into more specific, search-friendly formats
        Expands synonyms to improve semantic matching
        """
        query_lower = query.lower().strip()
        improved_query = query
        
        # CRITICAL: Organizational overview queries - enhance to retrieve customer-facing content
        # Add keywords that help LightRAG find customer-facing info, not financial/investor content
        if self._is_organizational_overview_query(query):
            # Enhance query to bias retrieval toward customer-facing content
            # Add terms that are more likely in customer-facing docs vs annual reports
            customer_facing_keywords = "banking services accounts loans cards digital platforms EBLConnect customer"
            improved_query = f"{query} {customer_facing_keywords}"
            logger.info(f"[QUERY_ENHANCE] Enhanced organizational overview query with customer-facing keywords")
        
        # Note: LightRAG uses semantic search, so it should handle synonyms automatically
        # However, we log when we detect synonym-using queries for monitoring
        import re
        synonym_terms = ['credited', 'paid', 'deposited', 'fee', 'charge', 'rate', 'frequency', 'schedule']
        if any(term in query_lower for term in synonym_terms):
            logger.info(f"[QUERY_SYNONYM] Query contains synonym terms: '{query[:80]}' - LightRAG semantic search should handle this")

        # Improve Islamic Priority retrieval by adding the full card name
        if "islamic priority" in query_lower and "visa signature debit card" not in query_lower:
            improved_query = f"{query} EBL Islamic Priority Visa Signature Debit Card"
            logger.info("[QUERY_ENHANCE] Added full card name for Islamic Priority query")

        # MetLife My Child's Education Protection (MCEPP) - improve retrieval for tenure/term questions.
        # Users may ask "My Childs Education Program" but docs may use MCEPP/Protection wording.
        if "metlife" in query_lower and ("child" in query_lower or "childs" in query_lower) and "education" in query_lower:
            metlife_keywords = (
                "MCEPP MetLife My Child's Education Protection "
                "plan term policy term tenure coverage period premium payment term "
                "\"MetLife Product Details\" \"MetLife Product Details.pdf\""
            )
            improved_query = f"{improved_query} {metlife_keywords}"
            logger.info("[QUERY_ENHANCE] Expanded MetLife child education query with MCEPP keywords")
        
        # Priority center queries - NOTE: These should be routed to location service, not LightRAG
        # This improvement is only for queries that somehow reach LightRAG (shouldn't happen)
        # The location service routing happens BEFORE this function is called
        if 'priority center' in query_lower or 'priority centre' in query_lower:
            if 'sylhet' in query_lower:
                # Convert "tell me about priority center in sylhet" to more specific query
                if 'how many' not in query_lower and 'number' not in query_lower:
                    # Use a single, comprehensive query that works well with LightRAG
                    return "How many Priority centers are there in Sylhet City and what are their details?"
            elif 'how many' in query_lower or 'number' in query_lower:
                # Already specific enough
                return improved_query
        
        # Location-based queries - make them more specific
        if 'tell me about' in query_lower and ('center' in query_lower or 'centre' in query_lower):
            # Extract location if mentioned
            locations = ['sylhet', 'dhaka', 'chittagong', 'narayanganj']
            for loc in locations:
                if loc in query_lower:
                    return f"What are the Priority Centers in {loc.capitalize()}? How many Priority Centers are in {loc.capitalize()}?"
        
        # Return improved query
        return improved_query
    
    async def _get_lightrag_context(
        self,
        query: str,
        knowledge_base: Optional[str] = None,
        filter_financial_docs: bool = False
    ) -> tuple[str, list[str]]:
        """
        Get context from LightRAG (with caching)
        
        Args:
            query: The query string
            knowledge_base: Knowledge base to query
            filter_financial_docs: If True, exclude annual reports/financial statements from chunks
        
        Returns: (context_string, sources_list)
        """
        kb = knowledge_base or settings.LIGHTRAG_KNOWLEDGE_BASE
        
        # Improve query phrasing for better results
        improved_query = self._improve_query_for_lightrag(query)
        if improved_query != query:
            logger.info(f"[ROUTING] Improved query: '{query[:100]}' → '{improved_query[:100]}'")

        # Dynamic retrieval depth for term/tenure and policy/compliance questions.
        ql = (query or "").lower()
        is_term_question = any(k in ql for k in ["tenure", "term", "policy term", "plan term", "coverage period"])
        is_metlife_query = "metlife" in ql or "mcepp" in ql
        is_policy_query = any(
            k in ql
            for k in ["policy", "compliance", "procedure", "regulatory", "aml", "kyc", "guideline"]
        )
        top_k = settings.LIGHTRAG_TOP_K
        chunk_top_k = settings.LIGHTRAG_CHUNK_TOP_K
        if is_term_question and is_metlife_query:
            top_k = 20
            chunk_top_k = 30
            logger.info("[LIGHTRAG] Using deeper retrieval for MetLife term/tenure query")
        elif is_policy_query:
            top_k = settings.LIGHTRAG_POLICY_TOP_K
            chunk_top_k = settings.LIGHTRAG_POLICY_CHUNK_TOP_K
            logger.info("[LIGHTRAG] Using deeper retrieval for policy/compliance query")

        enable_rerank = settings.ENABLE_LIGHTRAG_RERANK
        
        # IMPORTANT: Include query parameters in the cache key string.
        cache_key_query = (
            f"{improved_query} || endpoint=query_data || mode=mix || top_k={top_k} || chunk_top_k={chunk_top_k} || "
            f"include_references=1 || only_need_context=1 || enable_rerank={int(enable_rerank)} || anchor_filter=v2"
        )
        cache_key = get_cache_key(cache_key_query, kb)
        
        # Check cache first
        cached = await self.redis_cache.get(cache_key)
        if cached:
            logger.info(f"Cache HIT for query: {improved_query[:50]}... (key: {cache_key})")
            context, sources = self._format_lightrag_context(cached, filter_financial_docs=filter_financial_docs)
            return context, sources
        
        logger.info(f"Cache MISS for query: {improved_query[:50]}... (key: {cache_key})")
        
        # Query LightRAG
        try:
            logger.info(f"Querying LightRAG for: {improved_query[:50]}... (knowledge_base: {kb}, filter_financial={filter_financial_docs})")
            response = await self.lightrag_client.query_data(
                query=improved_query,
                knowledge_base=kb,
                mode="mix",  # Use 'mix' mode (works better than 'hybrid')
                top_k=top_k,
                chunk_top_k=chunk_top_k,
                include_references=True,
                # CRITICAL: Do not let LightRAG's internal LLM generate an answer.
                # We only want grounded chunks/graph data, and we'll generate the final answer via OpenAI.
                only_need_context=True,
                enable_rerank=enable_rerank,
            )
            
            # Filter chunks to reduce irrelevant context bleed-through
            response = self._filter_lightrag_chunks_for_query(response, improved_query)

            # Cache the response (using parameter-aware cache key)
            await self.redis_cache.set(cache_key, response)
            
            context, sources = self._format_lightrag_context(response, filter_financial_docs=filter_financial_docs)
            
            # Low-confidence check: if context is too short, it might not be reliable
            # For banking, it's better to return empty and let the chatbot handle gracefully
            # rather than risk providing incorrect information
            if context and len(context) < settings.MIN_GROUNDING_CONTEXT_CHARS:
                logger.warning(
                    "LightRAG returned very short context (%s chars) - treating as ungrounded",
                    len(context),
                )
                return "", []
            
            return context, sources
        except Exception as e:
            error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"LightRAG query failed: {error_msg}")
            logger.error(f"Knowledge base: {kb}")
            logger.error(f"Query: {query[:100]}")
            
            # Return empty context on error (chatbot will still respond, just without LightRAG context)
            return "", []
    
    def _build_messages(
        self,
        query: str,
        context: str,
        conversation_history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Build messages for OpenAI API with prompt compression.
        
        Applies conversation history trimming to reduce token usage.
        """
        messages = [
            {"role": "system", "content": self.system_message}
        ]
        
        # Trim conversation history for prompt compression
        trimmed_history = self._trim_conversation_history(conversation_history)
        
        # Add trimmed conversation history
        for msg in trimmed_history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("message", "")
            })
        
        # Add current date/time information if query is about date/time
        datetime_info = ""
        if self._is_datetime_query(query):
            current_datetime = self._get_current_datetime()
            datetime_info = f"\n\nCurrent Date and Time: {current_datetime}"
        # Add current query with context (+ prompt add-ons)
        if context:
            prompt_addons = self._build_prompt_addons(query, context, trimmed_history)
            user_message = f"Context from knowledge base:\n{context}\n\nUser query: {query}{datetime_info}{prompt_addons}"
        else:
            user_message = f"{query}{datetime_info}"
        
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages
    
    def _get_conversation_key(self, session_id: Optional[str], client_ip: Optional[str] = None, channel: Optional[str] = None, sender_id: Optional[str] = None) -> str:
        """
        Derive stable conversation key for Redis disambiguation state.
        
        Priority:
        1. If session_id is provided and stable, use it directly
        2. If channel and sender_id are available, use f"{channel}:{sender_id}"
        3. Fallback to client_ip-based key (less stable but better than random UUID)
        
        Args:
            session_id: Session ID from request (may be None or unstable)
            client_ip: Client IP address (fallback for key derivation)
            channel: Channel identifier (e.g., "whatsapp", "teams", "web") - FUTURE: add to request model
            sender_id: Sender identifier (e.g., phone number, user ID) - FUTURE: add to request model
        
        Returns:
            Stable conversation key string
        """
        # TODO: When channel/sender_id are added to request model, use: f"{channel}:{sender_id}"
        if channel and sender_id:
            conversation_key = f"{channel}:{sender_id}"
            logger.info(f"[SESSION] Using channel-based conversation key: {conversation_key}")
            return conversation_key
        
        # If session_id is provided, use it (assume caller manages stability)
        if session_id:
            logger.info(f"[SESSION] Using provided session_id as conversation key: {session_id}")
            return session_id
        
        # Fallback: derive from client_ip (less stable but deterministic)
        if client_ip:
            conversation_key = f"ip:{client_ip}"
            logger.info(f"[SESSION] Derived conversation key from client_ip: {conversation_key}")
            return conversation_key
        
        # Last resort: generate UUID (will cause state loss but prevents errors)
        conversation_key = str(uuid.uuid4())
        logger.warning(f"[SESSION] No stable identifier available, generated UUID: {conversation_key}")
        return conversation_key
    
    async def process_chat(
        self,
        query: str,
        session_id: Optional[str] = None,
        knowledge_base: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_id: Optional[str] = None,
        employee: Optional["EmployeeUser"] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Process a chat query and stream the response
        
        Args:
            query: User's query
            session_id: Session ID for conversation history
            knowledge_base: LightRAG knowledge base name
            client_ip: Client IP address (used for stable conversation key derivation)
        
        Yields:
            Response chunks as strings
        """
        # Bind the AD-authenticated identity for this turn so persistence uses the
        # stable AD id (not client input) and stamps identity metadata.
        self._bind_identity(employee, user_id)
        # Derive stable conversation key (FIX #1: Session continuity)
        conversation_key = self._get_conversation_key(session_id, client_ip)
        # Use conversation_key for all disambiguation state operations
        # Store original session_id for memory/history (if provided)
        effective_session_id = session_id if session_id else conversation_key
        # Normalize session_id for the remainder of this request.
        # Many downstream calls assume a non-null session_id for state, headers, and persistence.
        session_id = effective_session_id
        forced_target: Optional[str] = None
        
        # ===== CRITICAL: Check for pending disambiguation state (BEFORE other processing) =====
        # This MUST happen before any other routing to ensure disambiguation state is always checked first
        pending_disambiguation = await self._get_disambiguation_state_any(conversation_key)
        if pending_disambiguation:
            # If user asked a new question, clear stale disambiguation state.
            if self._looks_like_new_query_during_disambiguation(
                query,
                pending_disambiguation.get("options", []),
            ):
                logger.info("[DISAMBIGUATION] New query detected; clearing pending disambiguation state.")
                await self._clear_disambiguation_state_any(conversation_key)
                pending_disambiguation = None
            else:
                disambiguation_type = pending_disambiguation.get("disambiguation_type")
                if disambiguation_type in {"ROUTING", "ROUTING_FEE_TYPE"}:
                    routing_result = await self._handle_routing_disambiguation(
                        query=query,
                        conversation_key=conversation_key,
                        pending_disambiguation=pending_disambiguation,
                    )
                    if routing_result.get("response"):
                        response_text = routing_result["response"]
                        await self._persist_turn(session_id, query, response_text, user_id=user_id)
                        async for chunk in self._stream_text(response_text):
                            yield chunk
                        return
                    forced_target = routing_result.get("resolved_target")
                    query = routing_result.get("resolved_query", query)
                else:
                    result = await self._handle_disambiguation_resolution(
                        query=query,
                        conversation_key=conversation_key,
                        session_id=effective_session_id,
                        pending_disambiguation=pending_disambiguation,
                        user_id=user_id,
                    )
                    if result:
                        # Stream the response and exit
                        async for chunk in self._stream_text(result["response"]):
                            yield chunk
                        # If available, also send sources marker for frontend parsing
                        sources = result.get("sources") or []
                        if sources:
                            marker = self._format_sources_marker(sources)
                            if marker:
                                yield marker
                        return
        
        # ===== LEAD GENERATION (capture + status queries) =====
        lead_response = await self._handle_lead_generation(
            query, conversation_key, session_id, employee=employee
        )
        if lead_response:
            await self._persist_turn(
                session_id,
                query,
                lead_response,
                client_ip=client_ip,
                routing_target="LEAD_GENERATION",
                user_id=user_id,
            )
            async for chunk in self._stream_text(lead_response):
                yield chunk
            return
        
        # Get conversation history
        db = get_db()
        memory = PostgresChatMemory(db=db)
        conversation_history = []
        try:
            if memory._available:
                # Load only this authenticated user's recent history (scoped by
                # user_id) to feed the LLM as conversational context.
                history = memory.get_conversation_history(
                    session_id=session_id,
                    limit=settings.CHAT_HISTORY_CONTEXT_LIMIT,
                    user_id=user_id,
                )
                conversation_history = [
                    {
                        "role": msg.role,
                        "message": msg.message,
                        "routing_target": msg.source_module,
                    }
                    for msg in history
                ]
        finally:
            memory.close()
            if db:
                db.close()

        # Bare option numbers after Redis disambiguation was cleared (e.g. user
        # replies "11" then "9") — recover from the last fee-engine list in history
        # instead of sending "9" to LightRAG.
        recovered = await self._try_recover_card_disambiguation_from_history(
            query=query,
            conversation_history=conversation_history,
            session_id=session_id,
            conversation_key=conversation_key,
            user_id=user_id,
        )
        if recovered:
            async for chunk in self._stream_text(recovered["response"]):
                yield chunk
            sources = recovered.get("sources") or []
            if sources:
                marker = self._format_sources_marker(sources)
                if marker:
                    yield marker
            return
        
        # ===== ROUTING DECISION LOGGING =====
        logger.info(f"[ROUTING] ===== Processing Query (STREAMING): '{query}' =====")

        decision = await self.routing_engine.decide(
            query=query,
            session_id=effective_session_id,
            knowledge_base=knowledge_base,
            client_ip=client_ip,
        )

        # ===== BROAD LOAN PRODUCT LINE QUERIES (DETERMINISTIC SHORT-CIRCUIT) =====
        # If the user is asking for the loan product lineup (not details), respond with
        # a product-line list and a follow-up question. This avoids generic bank-overview answers.
        if not forced_target and self._is_broad_loan_product_line_query(query):
            response_text = self._build_loan_product_line_list_response()
            await self._persist_turn(session_id, query, response_text, knowledge_base=None, client_ip=client_ip, routing_target="PRODUCT_INFO", user_id=user_id)
            async for chunk in self._stream_text(response_text):
                yield chunk
            return

        # ===== ROUTING DISAMBIGUATION (PHONEBOOK vs FEES vs LOCATION vs PROCESS) =====
        if not forced_target and self._should_prompt_routing_disambiguation(query, decision):
            fee_candidates = []
            if decision.is_fee_schedule_query:
                fee_candidates.append("FEE_ENGINE_CARDS")
            if decision.is_retail_asset_fee_query:
                fee_candidates.append("FEE_ENGINE_RETAIL_ASSETS")
            if decision.is_skybanking_fee_query:
                fee_candidates.append("FEE_ENGINE_SKYBANKING")

            prompt_message = self._build_routing_disambiguation_prompt()
            options = self._build_routing_disambiguation_options()
            state = {
                "product_line": "ROUTING",
                "charge_type": "ROUTING",
                "disambiguation_type": "ROUTING",
                "options": options,
                "prompt_message": prompt_message,
                "extra": {"base_query": query, "fee_candidates": fee_candidates},
            }
            await self._set_disambiguation_state_any(conversation_key, state)
            await self._persist_turn(session_id, query, prompt_message, routing_target="DISAMBIGUATION", user_id=user_id)
            async for chunk in self._stream_text(prompt_message):
                yield chunk
            return

        # Use decision.target as the single source of truth for routing
        # forced_target overrides if set (from disambiguation resolution)
        effective_target = forced_target if forced_target else decision.target
        logger.info(f"[ROUTING] Effective target: {effective_target} (forced={forced_target is not None})")

        # ===== DATETIME QUERIES - DETERMINISTIC (NO LightRAG / NO LLM) =====
        if effective_target == "DATETIME":
            response_text = self._build_datetime_response(query)
            async for chunk in self._stream_text(response_text):
                yield chunk
            await self._persist_turn(
                session_id,
                query,
                response_text,
                knowledge_base=None,
                client_ip=client_ip,
                routing_target="DATETIME",
                user_id=user_id,
            )
            return

        # ===== LOCATION QUERIES - ROUTE TO LOCATION SERVICE (HIGHEST PRIORITY) =====
        # Route location queries (branches, ATMs, CRMs, RTDMs, priority centers, head office) to location service
        # This MUST be checked BEFORE fee schedule queries to avoid misrouting priority center queries

        if effective_target == "LOCATION_SERVICE":
            logger.info(f"[LOCATION_SERVICE] ✓✓✓ LOCATION QUERY DETECTED: '{query}' → ROUTING TO LOCATION SERVICE (NO LightRAG, NO KB)")
            location_context = await self._get_location_context(query)
            sources = ["EBL Location Database (Normalized)"]
            
            # Use ONLY location service context - NO LightRAG, NO knowledge base
            combined_context = location_context
            logger.info(f"[LOCATION_SERVICE] Using EXCLUSIVE location service context: {len(location_context)} chars (LightRAG/KB explicitly skipped)")
            
            # Anti-hallucination hard guard:
            # Return the location service output directly (NO OpenAI call, NO paraphrasing).
            full_response = combined_context
            async for chunk in self._stream_deterministic_response(full_response, sources):
                yield chunk
            
            # Save to memory
            await self._persist_turn(session_id, query, full_response, knowledge_base=None, client_ip=client_ip, routing_target="LOCATION", user_id=user_id)
            
            return  # EXIT - do not proceed to LightRAG, phonebook, or any other routing
        
        # ===== CRITICAL: RETAIL ASSET FEE QUERIES - EXCLUSIVE FEE ENGINE ROUTING (HIGH PRIORITY) =====
        # Check for retail asset fee queries BEFORE card fee queries
        if effective_target == "FEE_ENGINE_RETAIL_ASSETS":
            logger.info(f"[FEE_ENGINE] ✓✓✓ RETAIL ASSET FEE QUERY DETECTED: '{query}' → EXCLUSIVE ROUTING TO FEE ENGINE")
            fee_context = await self._get_card_rates_context(query, session_id=effective_session_id, conversation_key=conversation_key)  # FIX #1: Pass conversation_key for stable disambiguation state
            sources = ["Retail Asset Charges Schedule"]
            
            # ALWAYS return fee engine response, even if empty
            if not fee_context:
                fee_context = (
                    f"{self.OFFICIAL_RETAIL_ASSET_HEADER}\n"
                    f"{self.FEE_ENGINE_SOURCE_RETAIL}\n\n"
                    "The specific information about this retail asset charge is not available in the current schedule. "
                    "Please verify the loan product details and try again, or contact Eastern Bank PLC. directly for this specific detail."
                )
            
            # Stream response in chunks
            full_response = fee_context
            async for chunk in self._stream_deterministic_response(full_response, sources):
                yield chunk
            
            # Save to memory
            await self._persist_turn(session_id, query, full_response, knowledge_base=None, client_ip=client_ip, routing_target="FEE_ENGINE_RETAIL", user_id=user_id)
            
            return  # EXIT - do not proceed to other routing
        
        # ===== CRITICAL: SKYBANKING FEE QUERIES - EXCLUSIVE FEE ENGINE ROUTING (HIGH PRIORITY) =====
        # Check for Skybanking fee queries BEFORE card fee queries
        if effective_target == "FEE_ENGINE_SKYBANKING":
            if self._is_generic_skybanking_fee_query(query):
                clarification = (
                    f"{self.OFFICIAL_SKYBANKING_HEADER}\n"
                    + "Please specify which Skybanking fee you need. For example:\n"
                    + "- Skybanking  Add money fee\n"
                    + "- Skybanking  Fund transfer fee (NPSB / Binimoy / RTGS)\n"
                    + "- Skybanking  A-Challan (government payment) fee\n"
                    + "- Skybanking  Statement / Certificate fee\n"
                    + "- Skybanking  Duplicate PIN charge\n"
                )
                async for chunk in self._stream_text(clarification):
                    yield chunk
                await self._persist_turn(session_id, query, clarification, knowledge_base=None, client_ip=client_ip, routing_target="FEE_ENGINE_SKYBANKING", user_id=user_id)
                return
            logger.info(f"[FEE_ENGINE] ✓✓✓ SKYBANKING FEE QUERY DETECTED: '{query}' → EXCLUSIVE ROUTING TO FEE ENGINE")
            fee_context = await self._get_card_rates_context(query, session_id=session_id)  # Pass session_id for disambiguation state storage
            sources = ["Skybanking Fees Schedule"]
            
            # ALWAYS return fee engine response, even if empty
            if not fee_context:
                fee_context = (
                    f"{self.OFFICIAL_SKYBANKING_HEADER}\n"
                    "Source: Fee Engine (Skybanking Fees Schedule)\n\n"
                    "The specific information about this Skybanking fee is not available in the current schedule. "
                    "Please verify the service details and try again, or contact Eastern Bank PLC. directly for this specific detail."
                )
            
            # Stream response in chunks
            full_response = fee_context
            async for chunk in self._stream_deterministic_response(full_response, sources):
                yield chunk
            
            # Save to memory
            await self._persist_turn(session_id, query, full_response, knowledge_base=None, client_ip=client_ip, routing_target="FEE_ENGINE_SKYBANKING", user_id=user_id)
            
            return  # EXIT - do not proceed to other routing
        
        # ===== CRITICAL: FEE SCHEDULE QUERIES - EXCLUSIVE FEE ENGINE ROUTING (HIGH PRIORITY) =====
        # MANDATORY: Fee queries MUST route to Fee Engine ONLY (authoritative source)
        # NO LightRAG fallback, NO knowledge base lookup, NO LLM guessing
        # This check happens AFTER location queries, retail asset queries, and Skybanking queries to avoid misrouting
        if effective_target == "FEE_ENGINE_CARDS":
            logger.info(f"[FEE_ENGINE] ✓✓✓ FEE SCHEDULE QUERY DETECTED (HIGHEST PRIORITY): '{query}' → ROUTING TO FEE ENGINE")
            fee_context = await self._get_card_rates_context(query, session_id=session_id)
            sources = ["Card Charges and Fees Schedule (Effective from 01st January, 2026)"]

            if fee_context:
                # Fee engine has a definitive answer — stream it directly (no LLM, no hallucination)
                logger.info(f"[FEE_ENGINE] Using EXCLUSIVE fee engine context: {len(fee_context)} chars")
                full_response = fee_context
                async for chunk in self._stream_deterministic_response(full_response, sources):
                    yield chunk
                await self._persist_turn(session_id, query, full_response, knowledge_base=None, client_ip=client_ip, routing_target="FEE_ENGINE_CARDS", user_id=user_id)
            else:
                logger.info(f"[FEE_ENGINE] No fee rule found for '{query}' — returning deterministic not-found response")
                full_response = self._build_card_fee_not_found_context()
                async for chunk in self._stream_deterministic_response(full_response, sources):
                    yield chunk
                await self._persist_turn(session_id, query, full_response, knowledge_base=None, client_ip=client_ip, routing_target="FEE_ENGINE_CARDS", user_id=user_id)

            return  # Fee engine is terminal for this target

        # Determine routing based on effective_target (single source of truth)
        should_check_apps = effective_target == "EBLHOME_APPS"
        should_check_forms = effective_target == "EBLHOME_FORMS"
        should_check_leadership = effective_target == "EBLHOME_LEADERSHIP"
        should_check_circulars = effective_target == "EBLHOME_CIRCULARS"
        should_check_soc = effective_target == "EBLHOME_SOC"
        should_check_proposals = effective_target == "EBLHOME_PROPOSALS"
        should_check_phonebook = effective_target == "PHONEBOOK"
        is_small_talk_route = effective_target == "OPENAI_SMALL_TALK"
        will_use_lightrag = effective_target == "LIGHTRAG"
        
        logger.info(
            f"[ROUTING] Final decision - effective_target={effective_target}, "
            f"will_check_leadership={should_check_leadership}, will_check_circulars={should_check_circulars}, "
            f"will_check_soc={should_check_soc}, will_check_proposals={should_check_proposals}, "
            f"will_check_apps={should_check_apps}, will_check_forms={should_check_forms}, "
            f"will_check_phonebook={should_check_phonebook}, will_use_lightrag={will_use_lightrag}"
        )
        
        if should_check_leadership:
            async for chunk in self._stream_leadership_response(query, session_id, client_ip, user_id=user_id):
                yield chunk
            return

        if should_check_circulars:
            async for chunk in self._stream_circulars_response(query, session_id, client_ip, user_id=user_id):
                yield chunk
            return

        if should_check_soc:
            async for chunk in self._stream_soc_response(query, session_id, client_ip, user_id=user_id):
                yield chunk
            return

        if should_check_proposals:
            async for chunk in self._stream_proposals_response(query, session_id, client_ip, user_id=user_id):
                yield chunk
            return

        if should_check_apps:
            async for chunk in self._stream_app_links_response(query, session_id, client_ip, user_id=user_id):
                yield chunk
            return

        if should_check_forms:
            async for chunk in self._stream_forms_response(query, session_id, client_ip, user_id=user_id):
                yield chunk
            return

        if should_check_phonebook:
            async for chunk in self._stream_phonebook_response(query, session_id, client_ip, user_id=user_id):
                yield chunk
            return

        # LightRAG path (fee, apps, forms, and phonebook targets exit above)
        context = ""
        sources: List[str] = []
        combined_context = ""

        if not is_small_talk_route:
            context, sources, knowledge_base, clarification = await self._prepare_lightrag_turn(
                query,
                decision,
                knowledge_base,
            )
            if clarification:
                logger.info("[POLICY] Policy query missing required entities, asking for clarification")
                await self._persist_turn(
                    session_id,
                    query,
                    clarification,
                    knowledge_base=None,
                    client_ip=client_ip,
                    routing_target="CLARIFICATION",
                    user_id=user_id,
                )
                for char in clarification:
                    yield char
                return
            combined_context = context

        # Block ungrounded LLM when LightRAG returned no usable context
        if will_use_lightrag and not is_small_talk_route and not self._has_sufficient_grounding(combined_context):
            ungrounded = self._build_ungrounded_response(query)
            logger.warning("[LIGHTRAG] Empty/short context — returning deterministic ungrounded response (no LLM)")
            async for chunk in self._stream_text(ungrounded):
                yield chunk
            await self._persist_turn(
                session_id,
                query,
                ungrounded,
                knowledge_base=knowledge_base,
                client_ip=client_ip,
                routing_target="LIGHTRAG_NO_CONTEXT",
                user_id=user_id,
            )
            return

        # Deterministic guardrail for MetLife tenure/term questions (avoid hallucination)
        extracted = self._extract_mcepp_plan_term_answer(query, combined_context)
        if extracted:
            async for chunk in self._stream_text(extracted):
                yield chunk
            await self._persist_turn(session_id, query, extracted, knowledge_base=knowledge_base, client_ip=client_ip, routing_target="LIGHTRAG", user_id=user_id)
            if sources:
                marker = self._format_sources_marker(sources)
                if marker:
                    yield marker
            return

        # Build messages
        messages = self._build_messages(query, combined_context, conversation_history)

        # ============================================================
        # RESPONSE CACHING: Check for cached response before OpenAI call
        # ============================================================
        cached_result = await self._get_cached_openai_response(
            query,
            combined_context,
            knowledge_base=knowledge_base,
            route_scope=effective_target,
        )
        if cached_result:
            # Cache hit! Stream the cached response
            cached_response = cached_result.get("response", "")
            cached_sources = cached_result.get("sources", [])
            logger.info(f"[RESPONSE_CACHE] 🎯 CACHE HIT - Streaming cached response ({len(cached_response)} chars)")
            
            # Stream cached response in chunks for consistent UX
            async for chunk in self._stream_cached_response(cached_response):
                yield chunk
            
            # Send sources if available
            final_sources = cached_sources if cached_sources else sources
            if final_sources:
                marker = self._format_sources_marker(final_sources)
                if marker:
                    yield marker
            
            # Save to memory (still track the interaction)
            await self._persist_turn(session_id, query, cached_response, knowledge_base=knowledge_base, client_ip=client_ip, routing_target=f"{effective_target}_CACHED", user_id=user_id)
            return

        # ============================================================
        # Cache miss - Call OpenAI API
        # ============================================================
        # Select model based on query complexity (gpt-4o-mini for simple, gpt-4o for complex)
        selected_model = self._select_model(query, decision)
        logger.info(f"[OPENAI] Selected model: {selected_model}")
        
        # Stream response from OpenAI
        full_response = ""
        try:
            # Calculate max_tokens dynamically to avoid context length errors
            # Reserve tokens for response, but cap at model limit
            # For gpt-4 models, max context is 8192 tokens
            # Estimate: system message ~2000 tokens, context ~4000 tokens, user query ~100 tokens
            # Reserve ~1500 tokens for response to be safe
            max_response_tokens = min(settings.OPENAI_MAX_TOKENS, 1500)
            
            stream = await self.openai_client.chat.completions.create(
                model=selected_model,
                messages=messages,
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=max_response_tokens,
                stream=True
            )
            
            async for chunk in stream:
                try:
                    if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        # Clean markdown formatting from content before yielding
                        cleaned_content = self._clean_markdown_formatting(content)
                        # Fix currency symbols using this request's context; do not rely on shared instance state.
                        cleaned_content = self._fix_currency_symbols(cleaned_content, combined_context)
                        # Fix bank name (replace "Eastern Bank Limited" with "Eastern Bank PLC.")
                        cleaned_content = self._fix_bank_name(cleaned_content)
                        yield cleaned_content
                except Exception as chunk_error:
                    logger.error(f"Error processing chunk: {chunk_error}", exc_info=True)
                    # Continue processing other chunks instead of breaking
                    continue
        except Exception as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            error_message = "I apologize, but I'm experiencing technical difficulties. Please try again later."
            yield error_message
            full_response = error_message
        
        # Clean markdown formatting from full response before saving
        full_response = self._clean_markdown_formatting(full_response)
        # Fix currency symbols as a safety net
        full_response = self._fix_currency_symbols(full_response, combined_context)
        # Fix bank name (replace "Eastern Bank Limited" with "Eastern Bank PLC")
        full_response = self._fix_bank_name(full_response)
        
        # ============================================================
        # RESPONSE CACHING: Cache the OpenAI response for future queries
        # ============================================================
        await self._cache_openai_response(
            query=query,
            context=combined_context,
            response=full_response,
            sources=sources,
            routing_target="LIGHTRAG",
            knowledge_base=knowledge_base,
            route_scope=effective_target,
        )
        
        # Store sources for later retrieval (we'll send them at the end of stream)
        # For now, we'll append sources as a special marker that frontend can parse
        if sources:
            logger.info(f"[SOURCES] Sending {len(sources)} sources: {sources[:3]}...")  # Log first 3 for debugging
            marker = self._format_sources_marker(sources)
            if marker:
                yield marker
        else:
            logger.info(f"[SOURCES] No sources to send for query: '{query[:50]}...'")
        
        # Save to memory
        await self._persist_turn(session_id, query, full_response, knowledge_base=knowledge_base, client_ip=client_ip, routing_target="LIGHTRAG", user_id=user_id)
    
    async def process_chat_sync(
        self,
        query: str,
        session_id: Optional[str] = None,
        knowledge_base: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_id: Optional[str] = None,
        employee: Optional["EmployeeUser"] = None,
    ) -> Dict[str, Any]:
        """
        Process a chat query and return complete response (non-streaming)
        
        Args:
            query: User's query
            session_id: Session ID for conversation history
            knowledge_base: LightRAG knowledge base name
            client_ip: Client IP address (used for stable conversation key derivation)
        
        Returns:
            Dictionary with response and session_id
        """
        # Bind the AD-authenticated identity for this turn (see _bind_identity).
        self._bind_identity(employee, user_id)
        # Derive stable conversation key (FIX #1: Session continuity)
        conversation_key = self._get_conversation_key(session_id, client_ip)
        # Use conversation_key for all disambiguation state operations
        # Store original session_id for memory/history (if provided)
        effective_session_id = session_id if session_id else conversation_key
        # Normalize session_id for the remainder of this request.
        # This prevents returning/using a None session_id when callers omit it.
        session_id = effective_session_id
        forced_target: Optional[str] = None
        
        # ===== CRITICAL: Check for pending disambiguation state (BEFORE other processing) =====
        # This MUST happen before any other routing to ensure disambiguation state is always checked first
        pending_disambiguation = await self._get_disambiguation_state_any(conversation_key)
        if pending_disambiguation:
            # If user asked a new question, clear stale disambiguation state.
            if self._looks_like_new_query_during_disambiguation(
                query,
                pending_disambiguation.get("options", []),
            ):
                logger.info("[DISAMBIGUATION] New query detected; clearing pending disambiguation state.")
                await self._clear_disambiguation_state_any(conversation_key)
                pending_disambiguation = None
            else:
                disambiguation_type = pending_disambiguation.get("disambiguation_type")
                if disambiguation_type in {"ROUTING", "ROUTING_FEE_TYPE"}:
                    routing_result = await self._handle_routing_disambiguation(
                        query=query,
                        conversation_key=conversation_key,
                        pending_disambiguation=pending_disambiguation,
                    )
                    if routing_result.get("response"):
                        response_text = routing_result["response"]
                        await self._persist_turn(session_id, query, response_text, user_id=user_id)
                        return {
                            "response": response_text,
                            "session_id": effective_session_id,
                            "sources": [],
                        }
                    forced_target = routing_result.get("resolved_target")
                    query = routing_result.get("resolved_query", query)
                else:
                    result = await self._handle_disambiguation_resolution(
                        query=query,
                        conversation_key=conversation_key,
                        session_id=effective_session_id,
                        pending_disambiguation=pending_disambiguation,
                        user_id=user_id,
                    )
                    if result:
                        return {
                            "response": result["response"],
                            "session_id": effective_session_id,
                            "sources": result.get("sources", []),
                        }
        
        # ===== LEAD GENERATION (capture + status queries) =====
        lead_response = await self._handle_lead_generation(
            query, conversation_key, session_id, employee=employee
        )
        if lead_response:
            await self._persist_turn(
                session_id,
                query,
                lead_response,
                client_ip=client_ip,
                routing_target="LEAD_GENERATION",
                user_id=user_id,
            )
            return {
                "response": lead_response,
                "session_id": effective_session_id,
                "sources": [],
            }
        
        # Get conversation history
        db = get_db()
        memory = PostgresChatMemory(db=db)
        conversation_history = []
        try:
            if memory._available:
                # Load only this authenticated user's recent history (scoped by
                # user_id) to feed the LLM as conversational context.
                history = memory.get_conversation_history(
                    session_id=session_id,
                    limit=settings.CHAT_HISTORY_CONTEXT_LIMIT,
                    user_id=user_id,
                )
                conversation_history = [
                    {
                        "role": msg.role,
                        "message": msg.message,
                        "routing_target": msg.source_module,
                    }
                    for msg in history
                ]
        finally:
            memory.close()
            if db:
                db.close()

        recovered = await self._try_recover_card_disambiguation_from_history(
            query=query,
            conversation_history=conversation_history,
            session_id=session_id,
            conversation_key=conversation_key,
            user_id=user_id,
        )
        if recovered:
            return {
                "response": recovered["response"],
                "session_id": effective_session_id,
                "sources": recovered.get("sources", []),
            }
        
        # ===== ROUTING DECISION LOGGING =====
        logger.info(f"[ROUTING] ===== Processing Query (SYNC): '{query}' =====")

        decision = await self.routing_engine.decide(
            query=query,
            session_id=effective_session_id,
            knowledge_base=knowledge_base,
            client_ip=client_ip,
        )

        # ===== BROAD LOAN PRODUCT LINE QUERIES (DETERMINISTIC SHORT-CIRCUIT) =====
        if not forced_target and self._is_broad_loan_product_line_query(query):
            response_text = self._build_loan_product_line_list_response()
            await self._persist_turn(session_id, query, response_text, knowledge_base=None, client_ip=client_ip, routing_target="PRODUCT_INFO", user_id=user_id)
            return {
                "response": response_text,
                "session_id": effective_session_id,
                "sources": [],
            }

        # Routing disambiguation (fees vs process vs location vs contact)
        if not forced_target and self._should_prompt_routing_disambiguation(query, decision):
            fee_candidates = []
            if decision.is_fee_schedule_query:
                fee_candidates.append("FEE_ENGINE_CARDS")
            if decision.is_retail_asset_fee_query:
                fee_candidates.append("FEE_ENGINE_RETAIL_ASSETS")
            if decision.is_skybanking_fee_query:
                fee_candidates.append("FEE_ENGINE_SKYBANKING")

            prompt_message = self._build_routing_disambiguation_prompt()
            options = self._build_routing_disambiguation_options()
            state = {
                "product_line": "ROUTING",
                "charge_type": "ROUTING",
                "disambiguation_type": "ROUTING",
                "options": options,
                "prompt_message": prompt_message,
                "extra": {"base_query": query, "fee_candidates": fee_candidates},
            }
            await self._set_disambiguation_state_any(conversation_key, state)
            await self._persist_turn(session_id, query, prompt_message, routing_target="DISAMBIGUATION", user_id=user_id)
            return {
                "response": prompt_message,
                "session_id": effective_session_id,
                "sources": [],
            }

        # Use decision.target as the single source of truth for routing
        # forced_target overrides if set (from disambiguation resolution)
        effective_target = forced_target if forced_target else decision.target
        logger.info(f"[ROUTING] Effective target: {effective_target} (forced={forced_target is not None})")

        # ===== DATETIME QUERIES - DETERMINISTIC (NO LightRAG / NO LLM) =====
        if effective_target == "DATETIME":
            response_text = self._build_datetime_response(query)
            await self._persist_turn(
                session_id,
                query,
                response_text,
                knowledge_base=None,
                client_ip=client_ip,
                routing_target="DATETIME",
                user_id=user_id,
            )
            return {
                "response": response_text,
                "session_id": session_id,
                "sources": [],
            }

        # ===== LOCATION QUERIES - ROUTE TO LOCATION SERVICE (HIGHEST PRIORITY) =====
        # Route location queries (branches, ATMs, CRMs, RTDMs, priority centers, head office) to location service
        # This MUST be checked BEFORE fee schedule queries to avoid misrouting priority center queries
        if effective_target == "LOCATION_SERVICE":
            logger.info(f"[LOCATION_SERVICE] ✓✓✓ LOCATION QUERY DETECTED: '{query}' → ROUTING TO LOCATION SERVICE (NO LightRAG, NO KB)")
            location_context = await self._get_location_context(query)
            sources = ["EBL Location Database (Normalized)"]
            
            # Use ONLY location service context - NO LightRAG, NO knowledge base
            combined_context = location_context
            logger.info(f"[LOCATION_SERVICE] Using EXCLUSIVE location service context: {len(location_context)} chars (LightRAG/KB explicitly skipped)")
            
            # Anti-hallucination hard guard:
            # Return the location service output directly (NO OpenAI call, NO paraphrasing).
            full_response = combined_context

            # Save to memory
            await self._persist_turn(session_id, query, full_response, knowledge_base=None, client_ip=client_ip, routing_target="LOCATION", user_id=user_id)
            
            return {
                "response": full_response,
                "sources": sources,
                "session_id": effective_session_id,
                "routing": "location_service"
            }  # EXIT - do not proceed to LightRAG, phonebook, or any other routing
        
        # ===== CRITICAL: RETAIL ASSET FEE QUERIES - EXCLUSIVE FEE ENGINE ROUTING (HIGH PRIORITY) =====
        # Check for retail asset fee queries BEFORE card fee queries
        if effective_target == "FEE_ENGINE_RETAIL_ASSETS":
            logger.info(f"[FEE_ENGINE] ✓✓✓ RETAIL ASSET FEE QUERY DETECTED: '{query}' → EXCLUSIVE ROUTING TO FEE ENGINE")
            fee_context = await self._get_card_rates_context(query, session_id=effective_session_id, conversation_key=conversation_key)  # FIX #1: Pass conversation_key for stable disambiguation state
            sources = ["Retail Asset Charges Schedule"]
            
            # ALWAYS return fee engine response, even if empty
            if not fee_context:
                fee_context = (
                    f"{self.OFFICIAL_RETAIL_ASSET_HEADER}\n"
                    f"{self.FEE_ENGINE_SOURCE_RETAIL}\n\n"
                    "The specific information about this retail asset charge is not available in the current schedule. "
                    "Please verify the loan product details and try again, or contact Eastern Bank PLC. directly for this specific detail."
                )
            
            # Anti-hallucination hard guard (SYNC):
            # Return the fee engine output directly (NO OpenAI call, NO paraphrasing).
            response_text = fee_context
            
            # Save to memory
            await self._persist_turn(effective_session_id, query, response_text, knowledge_base=None, client_ip=client_ip, routing_target="FEE_ENGINE_RETAIL", user_id=user_id)

            return {
                "response": response_text,
                "session_id": effective_session_id,
                "sources": sources
            }  # EXIT - do not proceed to other routing
        
        # ===== CRITICAL: SKYBANKING FEE QUERIES - EXCLUSIVE FEE ENGINE ROUTING (HIGH PRIORITY) =====
        # Check for Skybanking fee queries BEFORE card fee queries
        if effective_target == "FEE_ENGINE_SKYBANKING":
            if self._is_generic_skybanking_fee_query(query):
                response_text = (
                    f"{self.OFFICIAL_SKYBANKING_HEADER}\n"
                    + "Please specify which Skybanking fee you need. For example:\n"
                    + "- Skybanking  Add money fee\n"
                    + "- Skybanking  Fund transfer fee (NPSB / Binimoy / RTGS)\n"
                    + "- Skybanking  A-Challan (government payment) fee\n"
                    + "- Skybanking  Statement / Certificate fee\n"
                    + "- Skybanking  Duplicate PIN charge\n"
                )
                await self._persist_turn(effective_session_id, query, response_text, knowledge_base=None, client_ip=client_ip, routing_target="FEE_ENGINE_SKYBANKING", user_id=user_id)
                return {
                    "response": response_text,
                    "session_id": effective_session_id,
                    "sources": [],
                }
            logger.info(f"[FEE_ENGINE] ✓✓✓ SKYBANKING FEE QUERY DETECTED: '{query}' → EXCLUSIVE ROUTING TO FEE ENGINE")
            fee_context = await self._get_card_rates_context(query, session_id=effective_session_id, conversation_key=conversation_key)  # FIX #1: Pass conversation_key for stable disambiguation state
            sources = ["Skybanking Fees Schedule"]
            
            # ALWAYS return fee engine response, even if empty
            if not fee_context:
                fee_context = (
                    f"{self.OFFICIAL_SKYBANKING_HEADER}\n"
                    f"{self.FEE_ENGINE_SOURCE_SKYBANKING}\n\n"
                    "The specific information about this Skybanking fee is not available in the current schedule. "
                    "Please verify the service details and try again, or contact Eastern Bank PLC. directly for this specific detail."
                )

            # Anti-hallucination hard guard (SYNC):
            # Return the fee engine output directly (NO OpenAI call, NO paraphrasing).
            response_text = fee_context
            
            # Save to memory
            await self._persist_turn(effective_session_id, query, response_text, knowledge_base=None, client_ip=client_ip, routing_target="FEE_ENGINE_SKYBANKING", user_id=user_id)
            
            return {
                "response": response_text,
                "session_id": effective_session_id,
                "sources": sources
            }  # EXIT - do not proceed to other routing
        
        # ===== CRITICAL: FEE SCHEDULE QUERIES - EXCLUSIVE FEE ENGINE ROUTING =====
        # MANDATORY: Fee queries MUST route to Fee Engine ONLY (authoritative source)
        # NO LightRAG fallback, NO knowledge base lookup, NO LLM guessing
        # This check happens AFTER location queries, retail asset queries, and Skybanking queries to avoid misrouting
        if effective_target == "FEE_ENGINE_CARDS":
            logger.info(f"[FEE_ENGINE] ✓✓✓ FEE SCHEDULE QUERY DETECTED: '{query}' → ROUTING TO FEE ENGINE")
            fee_context = await self._get_card_rates_context(query, session_id=session_id)
            sources = ["Card Charges and Fees Schedule (Effective from 01st January, 2026)"]

            if fee_context:
                logger.info(f"[FEE_ENGINE] Using fee engine context: {len(fee_context)} chars")
                await self._persist_turn(session_id, query, fee_context, knowledge_base=None, client_ip=client_ip, routing_target="FEE_ENGINE_CARDS", user_id=user_id)
                return {
                    "response": fee_context,
                    "session_id": session_id,
                    "sources": sources,
                }
            else:
                logger.info(f"[FEE_ENGINE] No fee rule found for '{query}' — returning deterministic not-found response")
                response_text = self._build_card_fee_not_found_context()
                await self._persist_turn(session_id, query, response_text, knowledge_base=None, client_ip=client_ip, routing_target="FEE_ENGINE_CARDS", user_id=user_id)
                return {
                    "response": response_text,
                    "session_id": session_id,
                    "sources": sources,
                }

        # Determine routing based on effective_target (single source of truth)
        should_check_apps = effective_target == "EBLHOME_APPS"
        should_check_forms = effective_target == "EBLHOME_FORMS"
        should_check_leadership = effective_target == "EBLHOME_LEADERSHIP"
        should_check_circulars = effective_target == "EBLHOME_CIRCULARS"
        should_check_soc = effective_target == "EBLHOME_SOC"
        should_check_proposals = effective_target == "EBLHOME_PROPOSALS"
        should_check_phonebook = effective_target == "PHONEBOOK"
        is_small_talk_route = effective_target == "OPENAI_SMALL_TALK"
        will_use_lightrag = effective_target == "LIGHTRAG"
        
        logger.info(
            f"[ROUTING] Final decision - effective_target={effective_target}, "
            f"will_check_leadership={should_check_leadership}, will_check_circulars={should_check_circulars}, "
            f"will_check_soc={should_check_soc}, will_check_proposals={should_check_proposals}, "
            f"will_check_apps={should_check_apps}, will_check_forms={should_check_forms}, "
            f"will_check_phonebook={should_check_phonebook}, will_use_lightrag={will_use_lightrag}"
        )
        
        if should_check_leadership:
            result = self.leadership_handler.lookup(query, self.leadership_db)
            leadership_meta = (
                f"leadership:term={result.search_term};found={result.found}"
                if result.search_term
                else ("leadership:found=false" if not result.found else None)
            )
            await self._persist_turn(
                session_id,
                query,
                result.response_text,
                knowledge_base=leadership_meta,
                client_ip=client_ip,
                routing_target="EBLHOME_LEADERSHIP",
                user_id=user_id,
            )
            return {
                "response": result.response_text,
                "session_id": session_id,
                "sources": ["EBL Home Leadership"],
            }

        if should_check_circulars:
            result = self.circulars_handler.lookup(query, self.circulars_db)
            circulars_meta = f"circulars:term={result.search_term};found={result.found}" if result.search_term else None
            await self._persist_turn(
                session_id, query, result.response_text, knowledge_base=circulars_meta,
                client_ip=client_ip, routing_target="EBLHOME_CIRCULARS", user_id=user_id,
            )
            return {"response": result.response_text, "session_id": session_id, "sources": ["EBL Home Circulars"]}

        if should_check_soc:
            result = self.soc_handler.lookup(query, self.soc_db)
            soc_meta = f"soc:term={result.search_term};found={result.found}" if result.search_term else None
            await self._persist_turn(
                session_id, query, result.response_text, knowledge_base=soc_meta,
                client_ip=client_ip, routing_target="EBLHOME_SOC", user_id=user_id,
            )
            return {
                "response": result.response_text,
                "session_id": session_id,
                "sources": ["EBL Home Schedule of Charges"],
            }

        if should_check_proposals:
            result = self.proposals_handler.lookup(query, self.proposals_db)
            proposals_meta = f"proposals:term={result.search_term};found={result.found}" if result.search_term else None
            await self._persist_turn(
                session_id, query, result.response_text, knowledge_base=proposals_meta,
                client_ip=client_ip, routing_target="EBLHOME_PROPOSALS", user_id=user_id,
            )
            return {
                "response": result.response_text,
                "session_id": session_id,
                "sources": ["EBL Home Proposal Updates"],
            }

        if should_check_apps:
            result = self.app_links_handler.lookup(query, self.apps_db)
            apps_meta = (
                f"apps:term={result.search_term};found={result.found}"
                if result.search_term
                else ("apps:found=false" if not result.found else None)
            )
            await self._persist_turn(
                session_id,
                query,
                result.response_text,
                knowledge_base=apps_meta,
                client_ip=client_ip,
                routing_target="EBLHOME_APPS",
                user_id=user_id,
            )
            return {
                "response": result.response_text,
                "session_id": session_id,
                "sources": ["EBL Home Applications"],
            }

        if should_check_forms:
            result = self.forms_handler.lookup(query, self.forms_db)
            forms_meta = (
                f"forms:term={result.search_term};found={result.found}"
                if result.search_term
                else ("forms:found=false" if not result.found else None)
            )
            await self._persist_turn(
                session_id,
                query,
                result.response_text,
                knowledge_base=forms_meta,
                client_ip=client_ip,
                routing_target="EBLHOME_FORMS",
                user_id=user_id,
            )
            return {
                "response": result.response_text,
                "session_id": session_id,
                "sources": ["EBL Home Forms"],
            }

        if should_check_phonebook:
            result = self.phonebook_handler.lookup(query, self.phonebook_db)
            phonebook_meta = (
                f"phonebook:term={result.search_term};found={result.found}"
                if result.search_term
                else ("phonebook:found=false" if not result.found else None)
            )
            await self._persist_turn(
                session_id,
                query,
                result.response_text,
                knowledge_base=phonebook_meta,
                client_ip=client_ip,
                routing_target="PHONEBOOK",
                user_id=user_id,
            )
            return {
                "response": result.response_text,
                "session_id": session_id,
                "sources": ["EBL Phonebook / Employee Directory"],
            }

        # LightRAG path (fee and phonebook targets exit above)
        context = ""
        sources: List[str] = []
        combined_context = ""

        if not is_small_talk_route:
            context, sources, knowledge_base, clarification = await self._prepare_lightrag_turn(
                query,
                decision,
                knowledge_base,
            )
            if clarification:
                logger.info("[POLICY] Policy query missing required entities, asking for clarification")
                await self._persist_turn(
                    session_id,
                    query,
                    clarification,
                    knowledge_base=None,
                    client_ip=client_ip,
                    routing_target="CLARIFICATION",
                    user_id=user_id,
                )
                return {
                    "response": clarification,
                    "session_id": session_id,
                }
            combined_context = context

        # Block ungrounded LLM when LightRAG returned no usable context
        if will_use_lightrag and not is_small_talk_route and not self._has_sufficient_grounding(combined_context):
            ungrounded = self._build_ungrounded_response(query)
            logger.warning("[LIGHTRAG] Empty/short context — returning deterministic ungrounded response (no LLM)")
            await self._persist_turn(
                session_id,
                query,
                ungrounded,
                knowledge_base=knowledge_base,
                client_ip=client_ip,
                routing_target="LIGHTRAG_NO_CONTEXT",
                user_id=user_id,
            )
            return {
                "response": ungrounded,
                "session_id": session_id,
                "sources": [],
            }

        extracted = self._extract_mcepp_plan_term_answer(query, combined_context)
        if extracted:
            await self._persist_turn(
                session_id,
                query,
                extracted,
                knowledge_base=knowledge_base,
                client_ip=client_ip,
                routing_target="LIGHTRAG",
                user_id=user_id,
            )
            return {
                "response": extracted,
                "session_id": session_id,
                "sources": sources,
            }

        messages = self._build_messages(query, combined_context, conversation_history)

        cached_result = await self._get_cached_openai_response(
            query,
            combined_context,
            knowledge_base=knowledge_base,
            route_scope=effective_target,
        )
        if cached_result:
            cached_response = cached_result.get("response", "")
            cached_sources = cached_result.get("sources", [])
            logger.info(
                "[RESPONSE_CACHE] CACHE HIT - Returning cached response (%s chars)",
                len(cached_response),
            )
            await self._persist_turn(
                session_id,
                query,
                cached_response,
                knowledge_base=knowledge_base,
                client_ip=client_ip,
                routing_target=f"{effective_target}_CACHED",
                user_id=user_id,
            )
            return {
                "response": cached_response,
                "session_id": session_id,
                "sources": cached_sources if cached_sources else sources,
            }

        selected_model = self._select_model(query, decision)
        logger.info(f"[OPENAI] Selected model: {selected_model}")

        try:
            max_response_tokens = min(settings.OPENAI_MAX_TOKENS, 1500)
            response = await self.openai_client.chat.completions.create(
                model=selected_model,
                messages=messages,
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=max_response_tokens,
                stream=False,
            )
            full_response = response.choices[0].message.content or ""
            full_response = self._clean_markdown_formatting(full_response)
            full_response = self._fix_currency_symbols(full_response, combined_context)
            full_response = self._fix_bank_name(full_response)
        except Exception as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            full_response = "I apologize, but I'm experiencing technical difficulties. Please try again later."

        await self._cache_openai_response(
            query=query,
            context=combined_context,
            response=full_response,
            sources=sources,
            routing_target="LIGHTRAG",
            knowledge_base=knowledge_base,
            route_scope=effective_target,
        )

        await self._persist_turn(
            session_id,
            query,
            full_response,
            knowledge_base=knowledge_base,
            client_ip=client_ip,
            routing_target="LIGHTRAG",
            user_id=user_id,
        )

        return {
            "response": full_response,
            "session_id": session_id,
            "sources": sources,
        }

