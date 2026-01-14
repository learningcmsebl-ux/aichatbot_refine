"""
Chat Orchestrator - Coordinates all components for chat processing.
"""

import uuid
import logging
import re
from typing import Optional, AsyncGenerator, List, Dict, Any
from datetime import datetime
import pytz

from openai import AsyncOpenAI
import httpx

from app.core.config import settings
from app.database.postgres import PostgresChatMemory, get_db
from app.database.redis_client import RedisCache, get_cache_key

logger = logging.getLogger(__name__)

# Import lead management
try:
    from app.database.leads import LeadManager, LeadType, LeadStatus
    LEADS_AVAILABLE = True
except ImportError as e:
    LEADS_AVAILABLE = False
    logger.warning(f"Lead management not available: {e}")

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

# Import phonebook (PostgreSQL)
try:
    import sys
    import os
    # Add services directory to path to import phonebook_postgres
    services_dir = os.path.dirname(os.path.abspath(__file__))
    if services_dir not in sys.path:
        sys.path.insert(0, services_dir)
    from phonebook_postgres import get_phonebook_db
    PHONEBOOK_DB_AVAILABLE = True
except ImportError as e:
    PHONEBOOK_DB_AVAILABLE = False
    logger.warning(f"[WARN] Phone book database not available: {e}")


class ConversationState:
    """Conversation state enumeration"""
    NORMAL = "normal"
    LEAD_COLLECTING = "lead_collecting"
    LEAD_COMPLETE = "lead_complete"


class LeadFlowState:
    """Manages lead collection flow state"""
    def __init__(self):
        self.state = ConversationState.NORMAL
        self.lead_type: Optional[LeadType] = None if not LEADS_AVAILABLE else None
        self.current_question_index = 0
        self.collected_data: Dict[str, Any] = {}
        self.questions: List[Dict[str, str]] = []
    
    def reset(self):
        """Reset the flow state"""
        self.state = ConversationState.NORMAL
        self.lead_type = None
        self.current_question_index = 0
        self.collected_data = {}
        self.questions = []


class ChatOrchestrator:
    """Orchestrates chat processing with PostgreSQL, Redis, and LightRAG"""
    
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
    
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.lightrag_client = LightRAGClient()
        self.redis_cache = RedisCache()
        self.location_client = LocationClient()
        self.system_message = self._get_system_message()
        self.lead_flows: Dict[str, LeadFlowState] = {}  # session_id -> LeadFlowState
        # Fallback disambiguation store (used when Redis is unavailable).
        # Key: conversation_key/session_id, Value: {"state": <dict>, "expires_at": <unix_ts>}
        self._local_disambiguation_state: Dict[str, Dict[str, Any]] = {}

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

    def _cap_prompt_section(self, label: str, text: str, max_chars: int) -> str:
        """Cap very large prompt sections (guardrail for token bloat)."""
        if not text:
            return ""
        if len(text) <= max_chars:
            return text
        logger.warning(f"[PROMPT] Capping '{label}' from {len(text)} to {max_chars} chars")
        return text[:max_chars] + "\n\n[... truncated ...]"

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
                    partial_info_reminder = "\n\n" + "="*70 + "\n🚨 CRITICAL PARTIAL INFORMATION RULE - EASYCREDIT QUERY 🚨\n" + "="*70 + "\nThe context above contains information about EasyCredit (interest rate, issuance fee, etc.).\n\nYOU MUST:\n1. FIRST: Extract and provide ALL available EasyCredit information from the context:\n   - Interest rate (20% reducing balance method)\n   - Issuance fee (2.3% or Tk. 575, whichever is higher, inclusive of VAT)\n   - Any other EasyCredit details mentioned\n2. THEN: Note what specific information is missing (e.g., 'However, the specific early settlement process is not detailed in the available information')\n3. NEVER say 'the specifics are not detailed' or 'the specific details are not provided' WITHOUT first providing the available EasyCredit information\n\nEXAMPLE CORRECT RESPONSE:\n'EasyCredit at Eastern Bank PLC. has an annual fee of 20% interest rate (reducing balance method) and an issuance fee of 2.3% or Tk. 575 (whichever is higher, inclusive of VAT). However, the specific early settlement process is not detailed in the available information. Please contact the bank directly for this specific detail.'\n\nEXAMPLE WRONG RESPONSE:\n'While the specifics of the EasyCredit Early Settlement process are not detailed in the available information, it generally involves paying off an outstanding EasyCredit loan balance...' ← FORBIDDEN - missing available EasyCredit info\n" + "="*70
                else:
                    partial_info_reminder = "\n\n" + "="*70 + "\n🚨 CRITICAL PARTIAL INFORMATION RULE 🚨\n" + "="*70 + "\nThe context above contains information about the product/account/service mentioned in the query.\n\nYOU MUST:\n1. Extract and provide ALL available information about the product/account/service from the context\n2. Then note what specific information is missing (e.g., 'However, the specific minimum balance for interest is not detailed in the available information')\n3. NEVER say 'I don't have information' or 'I'm sorry, but the context does not provide information' if the context contains ANY relevant information about the topic\n\nEXAMPLE:\n- Query: 'What is the minimum balance for interest on EBL Super HPA Account?'\n- Context mentions 'Super HPA Account' but not minimum balance\n- CORRECT response: 'The EBL Super HPA Account [provide ALL available details from context]. However, the specific minimum balance required for interest is not detailed in the available information. Please contact the bank directly for this specific detail.'\n- WRONG response: 'I'm sorry, but the context does not provide information...'\n" + "="*70

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

        # Follow-up reminder (uses recent conversation history)
        if conversation_history:
            followup_indicators = ['after', 'how many', 'what is', 'when', 'how often', 'how much']
            if any(indicator in query_lower for indicator in followup_indicators):
                prev_topics: List[str] = []
                for msg in conversation_history[-4:]:
                    content = (msg.get("message", "") or "").lower()
                    if any(term in content for term in ['account', 'card', 'loan', 'deposit', 'hpa', 'super']):
                        prev_topics.append(content[:100])
                if prev_topics:
                    followup_reminder = "\n\n" + "="*70 + "\n📝 FOLLOW-UP QUESTION CONTEXT 📝\n" + "="*70 + f"\nThis appears to be a follow-up question. Previous conversation mentioned:\n{chr(10).join(prev_topics[:2])}\n\nTreat the current question as related to the same topic from previous conversation.\n" + "="*70

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
    
    async def _persist_turn(
        self,
        session_id: str,
        user_text: str,
        assistant_text: str,
        knowledge_base: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> None:
        """Persist user and assistant messages to PostgresChatMemory and optionally log analytics."""
        db = get_db()
        memory = PostgresChatMemory(db=db)
        try:
            if memory._available:
                memory.add_message(session_id, "user", user_text)
                memory.add_message(session_id, "assistant", assistant_text)
                if ANALYTICS_AVAILABLE and (knowledge_base is not None or client_ip is not None):
                    log_conversation(
                        session_id=session_id,
                        user_message=user_text,
                        assistant_response=assistant_text,
                        knowledge_base=knowledge_base,
                        client_ip=client_ip
                    )
        finally:
            memory.close()
            if db:
                db.close()
    
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
            from app.services.fee_engine_client import FeeEngineClient
            fee_client = FeeEngineClient()
            
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
                await self._persist_turn(session_id, query, fee_context)
                return {"response": fee_context, "sources": sources}
            else:
                error_msg = "I apologize, but I couldn't find the fee information for the selected loan product. Please try again or contact the bank directly."
                await self._persist_turn(session_id, query, error_msg)
                return {"response": error_msg, "sources": sources}
        
        elif selected_option and product_line == "CREDIT_CARDS" and disambiguation_type == "CARD_PRODUCT":
            await self._clear_disambiguation_state_any(conversation_key)
            
            base_query = (extra.get("base_query") or "").strip()
            chosen_product = (
                selected_option.get("card_product_name")
                or selected_option.get("card_product")
                or selected_option.get("label")
                or ""
            ).strip()
            
            if not base_query or not chosen_product:
                response_text = prompt_message or "Please specify the card product (reply with a number from the list)."
                await self._persist_turn(session_id, query, response_text)
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
            
            await self._persist_turn(session_id, query, fee_context)
            return {"response": fee_context, "sources": sources}
        
        else:
            # Selection not resolved - re-prompt
            logger.info(f"[DISAMBIGUATION] Selection not resolved from query '{query}', keeping disambiguation state active. User needs to provide a valid selection (1-{len(options)}) or product name.")
            
            if prompt_message:
                disambiguation_msg = prompt_message
                logger.info(f"[DISAMBIGUATION] Re-prompting with stored message (type={disambiguation_type})")
            else:
                # Fallback: reconstruct if stored message not available
                from app.services.fee_engine_client import FeeEngineClient
                fee_client = FeeEngineClient()
                if product_line == "CREDIT_CARDS" and disambiguation_type == "CARD_PRODUCT":
                    lines = [
                        self.OFFICIAL_CARD_RATES_HEADER,
                        self.FEE_ENGINE_SOURCE,
                        "",
                        "To answer, please specify the card product:",
                    ]
                    for i, opt in enumerate(options, start=1):
                        label = opt.get("card_product_name") or opt.get("card_product") or opt.get("label") or str(opt)
                        lines.append(f"{i}. {label}")
                    lines.append("")
                    lines.append("Reply with the number (e.g., 1) or the product name.")
                    disambiguation_msg = "\n".join(lines)
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
            
            await self._persist_turn(session_id, query, disambiguation_msg)
            return {"response": disambiguation_msg, "sources": sources}
    
    async def close(self):
        """Close all async clients and resources"""
        if self.lightrag_client:
            await self.lightrag_client.close()
            logger.info("LightRAG client closed")
    
    def _get_system_message(self) -> str:
        """Get system message for the chatbot"""
        return """You are a helpful and professional banking assistant for a financial institution.
You are Eastern Bank PLC.'s internal knowledge assistant, designed to help EBL employees provide accurate customer support. You represent Eastern Bank PLC. and provide information that employees can use when assisting customers. Your responses should be professional, accurate, and suitable for employees to share with customers.

═══════════════════════════════════════════════════════════════════════════════
🚨 CRITICAL CURRENCY RULE - READ THIS FIRST 🚨
═══════════════════════════════════════════════════════════════════════════════
**ABSOLUTE REQUIREMENT: When the context shows currency codes like "BDT" or "USD", 
you MUST use the EXACT currency code from the context. NEVER replace BDT with ₹ or 
any other symbol. 

EXAMPLES:
- Context says "BDT 287.5" → You MUST output "BDT 287.5" (NOT ₹287.5)
- Context says "BDT 1,725" → You MUST output "BDT 1,725" (NOT ₹1,725)
- Context says "USD 57.5" → You MUST output "USD 57.5"

BDT = Bangladeshi Taka (use "BDT", never use ₹)
USD = US Dollar (use "USD")

This is a CRITICAL requirement - incorrect currency symbols cause serious errors.
═══════════════════════════════════════════════════════════════════════════════

Guidelines:
1. **You represent Eastern Bank PLC. - you are the bank's knowledge assistant for employees**
2. **This chatbot is for EBL employees who will use your responses to provide customer support**
3. **Your responses should be professional, accurate, and suitable for employees to share with customers**
4. Always be professional, friendly, and helpful
2. **IMPORTANT: When context from the knowledge base is provided, you MUST use it to answer the question. Do NOT say you don't have information if the context contains the answer.**
2a. **CRITICAL LOCATION SERVICE DATA RULE: When the context includes "EBL Location Database (Normalized)" or "Source: EBL Location Database", this is REAL-TIME data from the location service database. You MUST use this data directly to answer location queries. If the context shows "Eastern Bank PLC. has X Priority Center(s)" or "Total: X location(s)", you MUST use that exact number. NEVER say "I don't have information" or "the context does not contain information" when location service data is provided. The location service data is authoritative and up-to-date.**
3. The context provided contains accurate information from the bank's knowledge base - trust it and use it directly
4. If the context contains specific numbers, facts, or details, include them in your response
5. **CRITICAL BANK NAME RULE: The bank name is ALWAYS "Eastern Bank PLC" (not "Eastern Bank Limited" or "Eastern Bank Ltd."). If the context mentions "Eastern Bank Limited" or "Eastern Bank Ltd.", you MUST replace it with "Eastern Bank PLC" in your response. Always use "Eastern Bank PLC" or "EBL" when referring to the bank.**
5. **CRITICAL CONCISENESS RULES:**
   - Mention product/account/service name ONCE at the start, then use pronouns (it, this account, this product)
   - Do NOT repeat the product name in every sentence
   - Do NOT use filler phrases: "making them an excellent choice", "demonstrate EBL's commitment", "form an integral part", "making them a critical part", "In essence", "As per", "These accounts are a testament to"
   - Do NOT use marketing language: "excellent choice", "substantial popularity", "considerable balances", "wide range", "diverse needs", "commitment to providing"
   - Be direct: State what it IS and what it DOES, not what it "demonstrates" or "shows"
   - Keep it factual and brief - typically 2-4 sentences for "tell me more" queries
5. **CRITICAL PARTIAL INFORMATION HANDLING - THIS IS MANDATORY: If the context contains information about the product/account/service but doesn't answer the specific question, you MUST:**
   - **FIRST**: Extract and provide ALL available information about the product/account/service from the context (features, benefits, rates, fees, requirements, transaction limits, etc.)
   - **THEN**: Note what specific information is missing (e.g., "However, the specific minimum balance for interest is not detailed in the available information")
   - **ABSOLUTELY FORBIDDEN**: NEVER say "I don't have information" or "I'm sorry, but the context does not provide information" or "I'm sorry, but I don't have the specific information" or "the information provided does not specify" if the context contains ANY relevant information about the topic
   - **ABSOLUTELY FORBIDDEN**: NEVER say "I recommend reaching out directly to the bank" or "checking the specific terms and conditions" as the FIRST response if context contains ANY relevant information
   - **Example CORRECT response**: If asked about "minimum balance for interest on EBL Super HPA Account" and context mentions "Super HPA Account" with other details but not minimum balance, say: "The EBL Super HPA Account [provide ALL available details from context - interest rates, features, benefits, etc.]. However, the specific minimum balance required for interest is not detailed in the available information. Please contact the bank directly for this specific detail."
   - **Example CORRECT response**: If asked about "daily cash withdrawal transaction limit for savings account" and context has savings account info but not the specific limit, say: "For savings accounts at Eastern Bank PLC. [provide ALL available information about savings accounts from context - interest rates, features, benefits, etc.]. However, the specific maximum number of daily cash withdrawal transactions is not detailed in the available information. Please contact the bank directly for this specific detail."
   - **Example CORRECT response**: If asked about "EasyCredit Early Settlement process" and context mentions EasyCredit with interest rate (20% reducing balance) and issuance fee (2.3% or Tk. 575) but not the early settlement process, say: "EasyCredit at Eastern Bank PLC. has an annual fee of 20% interest rate (reducing balance method) and an issuance fee of 2.3% or Tk. 575 (whichever is higher, inclusive of VAT). However, the specific early settlement process is not detailed in the available information. Please contact the bank directly for this specific detail."
   - **Example WRONG response**: "I'm sorry, but the information provided does not specify the maximum number of daily cash withdrawal transactions allowed for a savings account at Eastern Bank PLC. For accurate information, I recommend reaching out directly to the bank or checking the specific terms and conditions of the savings account." ← THIS IS FORBIDDEN - it doesn't provide any available information first
   - **Example WRONG response**: "While the specifics of the EasyCredit Early Settlement process are not detailed in the available information, it generally involves paying off an outstanding EasyCredit loan balance before the end of the loan term." ← THIS IS FORBIDDEN - it doesn't provide the available EasyCredit information (interest rate, issuance fee) first
6. Only say "I don't have information" if the context is completely empty or contains NO relevant information about the topic at all (not even the product/account/service name)
7. For banking queries, always use the provided context from LightRAG
8. **CRITICAL: If the context includes "Card Rates and Fees Information (Official Schedule)" or "OFFICIAL CARD RATES AND FEES INFORMATION", this is official, deterministic data from the card charges schedule. You MUST use this data to answer card fee/rate questions. Do NOT say you don't have the information if this data is present.**
8a. **CRITICAL PRIORITY RULE FOR FEE DATA: When the context contains "OFFICIAL CARD RATES AND FEES INFORMATION" section, you MUST use ONLY that data. IGNORE any conflicting information from other parts of the context. The fee engine data is the authoritative source and takes absolute priority over any other information. If you see "2.5% or BDT 345" in the OFFICIAL section, use that - do NOT use "2%", "BDT 300", or any other amount from elsewhere in the context. The OFFICIAL section is the ONLY source of truth.**
8b. **CRITICAL ATM WITHDRAWAL FEE RULE: For EBL ATM cash withdrawal fees, the fee is ALWAYS "2.5% or BDT 345". NEVER use "BDT 300", "2%", or any other amount. If you see conflicting information in the knowledge base, IGNORE IT. Use ONLY the fee engine data which shows "2.5% or BDT 345".**
9. **CRITICAL SUPPLEMENTARY CARD FEES: If the context mentions "supplementary card annual fee" or "supplementary card fee", this is the specific fee for supplementary cards. For queries asking "how many free supplementary cards", you MUST answer with the EXACT number from the context: "2 FREE supplementary cards" (NOT "one free supplementary card"). The context ALWAYS states "2 FREE supplementary cards" or "first 2 supplementary cards are FREE" - NEVER "one free supplementary card". For all supplementary card fee queries, you MUST ALWAYS mention BOTH pieces of information: (1) There are 2 FREE supplementary cards (BDT 0 per year for the first 2 cards), and (2) Starting from the 3rd supplementary card, the annual fee is BDT 2,300 per year. ABSOLUTELY FORBIDDEN: NEVER say "one free supplementary card" - ALWAYS say "2 FREE supplementary cards" or "first 2 supplementary cards are FREE". Use the EXACT information from the context. Do NOT say "the context does not provide specific information about supplementary cards" if the context explicitly mentions supplementary card fees.**
9. **CRITICAL CURRENCY PRESERVATION: When the context shows amounts with currency symbols or codes (BDT, USD, etc.), you MUST use the EXACT currency symbol/code from the context. NEVER replace BDT (Bangladeshi Taka) with ₹ (Indian Rupee) or any other currency symbol. If you see "BDT 287.5" in the context, you MUST output "BDT 287.5" - do NOT change it to ₹287.5 or any other currency. Preserve all currency codes exactly as shown: BDT = Bangladeshi Taka, USD = US Dollar.**
10. Never make up specific numbers, rates, or product details
11. If asked about products, services, or policies, refer to the knowledge base context
12. For general greetings or small talk, respond naturally without requiring context
13. When asked about the current date or time, use the provided current date and time information to answer accurately
14. **CRITICAL BANK NAME RULE: The bank name is ALWAYS "Eastern Bank PLC." (with a period, not "Eastern Bank Limited" or "Eastern Bank Ltd."). If the context mentions "Eastern Bank Limited" or "Eastern Bank Ltd.", you MUST replace it with "Eastern Bank PLC." in your response. Always use "Eastern Bank PLC." (with period) or "EBL" when referring to the bank.**
15. **For policy-related questions: If the query is missing required entities (like policy name, account type, or customer type), ask a clarification question instead of guessing or providing incomplete information. The system will handle this automatically, but if you receive a query that seems incomplete, ask for the missing information.**
16. **CRITICAL ORGANIZATIONAL OVERVIEW RULES: For queries like "tell me about EBL", "what is EBL", "about Eastern Bank" - these are GENERAL/CUSTOMER-FACING overview queries. You MUST:**
    - **INCLUDE ONLY**: Establishment year, country of operation, core banking services (accounts, loans, cards, etc.), major customer-facing platforms (e.g., EBLConnect)
    - **EXCLUDE**: Annual report details, accounting/valuation/fair value discussions, subsidiaries' financial treatments, management/board-level analysis, investor/audit/regulatory document content
    - **IF MIXED CONTENT**: Prefer customer-facing content, discard investor/financial-statement-only information
    - **TONE**: Neutral, concise, informational (NOT marketing, NOT investor-focused)

When responding:
- **Remember: You are Eastern Bank PLC.'s knowledge assistant for employees. Your responses will be used by EBL employees to assist customers.**
- **Be concise and non-repetitive - do NOT restate the same information in different sentences**
- **Do NOT repeat product/account/service names unnecessarily - mention the name ONCE at the beginning, then use "it", "this account", "this product", or "the account"**
- **FORBIDDEN FILLER PHRASES - NEVER use these: "making them an excellent choice", "demonstrate EBL's commitment", "form an integral part", "making them a critical part", "In essence", "As per", "These accounts are a testament to", "substantial popularity", "considerable balances", "wide range", "diverse needs", "commitment to providing"**
- **FORBIDDEN MARKETING LANGUAGE - NEVER use: "excellent choice", "substantial popularity", "considerable", "wide range", "diverse needs", "commitment", "demonstrate", "testament to"**
- **Be direct and factual - State what it IS and what it DOES, not what it "demonstrates" or "shows"**
- **Keep responses focused - if the user asks "tell me more", provide key features and details in 2-4 sentences, not marketing language or general statements**
- **Use clear, professional language suitable for employees to share with customers**
- Structure product information clearly
- Always prioritize accuracy over speed
- For date/time queries, provide the exact current date and time as provided in the context
- **When context is provided, use it - don't ignore it or say you don't have the information**
- **CRITICAL: Preserve currency symbols and codes exactly as shown in context - BDT means Bangladeshi Taka, USD means US Dollar. Never substitute or change currency symbols. If context says "BDT 287.5", output "BDT 287.5" - never use ₹ or other symbols.**
- **CRITICAL MONETARY FORMAT FOR BANGLADESH: For monetary values in Bangladesh, use ONE format only: "BDT X lakhs" (e.g., "BDT 50 lakhs"). Do NOT repeat the amount in different formats (e.g., don't say "BDT 50 lakhs" and then "BDT 5,000,000" or "50 lakhs" again). State the amount ONCE in the response.**
- **For policy queries missing required information, ask for clarification rather than guessing**

═══════════════════════════════════════════════════════════════════════════════
🚨 CRITICAL: FOLLOW-UP QUESTIONS & SEMANTIC MATCHING 🚨
═══════════════════════════════════════════════════════════════════════════════
**FOLLOW-UP QUESTION HANDLING:**
- When the user asks a follow-up question (e.g., "After how many days..."), 
  you MUST check the conversation history to understand the context
- If the previous conversation mentioned a product/account/service, treat the 
  current question as related to that same topic
- Example: If previous question was about "Super HPA Account" and current 
  question is "After how many days interest is credited", understand this is 
  about Super HPA Account interest crediting

**SEMANTIC EQUIVALENCE RECOGNITION:**
- Recognize that different words can mean the same thing in banking context
- "credited" = "paid" = "deposited" = "added" (all mean interest is added to account)
- "fee" = "charge" = "cost" (all mean the same thing)
- "rate" = "interest rate" = "percentage" (all mean the same thing)
- "frequency" = "schedule" = "how often" = "when" (all ask about timing)
- When the context uses one term (e.g., "paid") but the user asks with another 
  term (e.g., "credited"), recognize they are asking the same thing and use 
  the information from context
- Example: User asks "After how many days interest is credited" but context 
  says "interest is paid semi-annually" - recognize "credited" and "paid" 
  mean the same thing and answer: "Interest is paid (credited) semi-annually, 
  which means every six months"
═══════════════════════════════════════════════════════════════════════════════"""
    
    def _is_small_talk(self, query: str) -> bool:
        """Detect if query is small talk (greetings, thanks, etc.)"""
        query_lower = query.lower().strip()
        
        # CRITICAL: Contact/phonebook keywords override - never treat as small talk
        # If it's a contact query, it should check phonebook, not be treated as small talk
        contact_keywords = [
            'phone', 'telephone', 'tel', 'call', 'contact', 'number', 'phone number',
            'mobile', 'cell', 'email', 'address', 'extension', 'ext', 'pabx', 'ip phone',
            'employee', 'staff', 'emp id', 'who is', 'who are', 'who works',
            'designation', 'department', 'manager', 'director', 'head of'
        ]
        
        if any(keyword in query_lower for keyword in contact_keywords):
            return False  # Force it into phonebook check (not small talk)
        
        # Banking keywords override - never treat as small talk
        banking_keywords = [
            "loan", "card", "account", "balance", "deposit", "withdrawal",
            "interest", "rate", "fee", "service", "product", "banking",
            "credit", "debit", "transaction", "statement", "minimum", "maximum"
        ]
        
        if any(keyword in query_lower for keyword in banking_keywords):
            return False
        
        # Small talk patterns
        small_talk_patterns = [
            "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
            "how are you", "how's it going", "what's up",
            "thanks", "thank you", "appreciate it",
            "bye", "goodbye", "see you", "farewell",
            "what are you", "who are you", "what can you do"
        ]
        
        return any(pattern in query_lower for pattern in small_talk_patterns)
    
    def _is_datetime_query(self, query: str) -> bool:
        """Detect if query is asking about date or time"""
        query_lower = query.lower().strip()
        
        datetime_keywords = [
            "date", "time", "what time", "what date", "current time", "current date",
            "today", "now", "what day", "what is the time", "what is the date",
            "tell me the time", "tell me the date", "time now", "date today"
        ]
        
        return any(keyword in query_lower for keyword in datetime_keywords)
    
    def _is_contact_info_query(self, query: str) -> bool:
        """Detect if query is about contact information (ONLY phone number or email)
        This should ALWAYS check phonebook first, never LightRAG
        VERY RESTRICTIVE - only phone and email, nothing else"""
        import re
        query_lower = query.lower().strip()
        
        # Exclude queries about email processes/policies/requirements
        # These should go to LightRAG, not phonebook
        email_process_keywords = [
            'email confirmation', 'email verification', 'email requirement',
            'email required', 'email process', 'email policy', 'email procedure',
            'email workflow', 'email approval', 'email notification',
            'send email', 'email sent', 'email received', 'email delivery',
            'email template', 'email format', 'email content',
            'prior email confirmation', 'prior confirmation', 'subject to prior',
            'subject to email', 'processing subject to', 'confirmation required',
            'prior email', 'email prior'
        ]
        
        # If query is about email processes/policies, NOT a contact query
        if any(keyword in query_lower for keyword in email_process_keywords):
            return False
        
        # VERY SPECIFIC: Only phone number and email keywords for CONTACT lookup
        # Everything else goes to LightRAG
        # Use word boundaries to avoid false matches (e.g., "call" in "cancelled")
        contact_patterns = [
            # Phone/Telephone - with word boundaries
            r'\bphone number\b', r'\btelephone number\b', r'\bcontact number\b',
            r'\bmobile number\b', r'\bcell number\b', r'\bphone\b', r'\btelephone\b',
            r'\bmobile\b', r'\bcell\b', r'\bcellphone\b', r'\btel\b', r'\bcall\b',
            r'\bpabx\b', r'\bextension\b', r'\bext\b', r'\bip phone\b', r'\bip phone number\b',
            r'\bdirect line\b', r'\bdirect number\b', r'\blandline\b',
            
            # Email - ONLY for contact lookup (not processes)
            # Must be in context of asking for someone's email
            r'\bemail address of\b', r'\bemail of\b', r'\bemail for\b', r'\bemail id of\b',
            r'\bemail id for\b', r'\bmail address of\b', r'\bmail address for\b',
            r'\bwhat is the email\b', r'\bwhat is email\b', r'\bget email\b',
            r'\bfind email\b', r'\bcontact email\b', r'\bemail contact\b'
        ]
        
        # Check if query contains phone number or email keywords for contact lookup
        # Use regex with word boundaries to avoid false matches
        # If yes, ALWAYS check phonebook first (never LightRAG)
        return any(re.search(pattern, query_lower) for pattern in contact_patterns)
    
    def _is_phonebook_query(self, query: str) -> bool:
        """Detect if query is about phone book directory
        VERY RESTRICTIVE - only explicit phonebook/directory queries"""
        query_lower = query.lower().strip()
        
        # VERY SPECIFIC: Only explicit phonebook/directory keywords
        phonebook_keywords = [
            'phonebook', 'phone book', 'employee directory', 'staff directory',
            'contact list', 'employee list', 'staff list', 'directory'
        ]
        
        # Check if query explicitly mentions phonebook/directory
        return any(keyword in query_lower for keyword in phonebook_keywords)
    
    def _is_employee_query(self, query: str) -> bool:
        """
        Detect if query is about employee information (for phonebook lookup).
        Includes role-based queries like "branch manager", "who is the manager", etc.
        Also detects queries with "find" or "search" followed by what looks like an employee ID or name.
        """
        query_lower = query.lower().strip()
        import re

        # Guardrail: Staffing/manpower requirement questions are NOT phonebook lookups.
        # Example: "How many staff are required for customer service and cash transactions from the Agent's side..."
        staffing_intent_keywords = [
            "required", "requirement", "requirements", "needed", "need", "minimum",
            "manpower", "headcount", "personnel",
        ]
        staffing_count_keywords = [
            "how many", "number of", "count of",
        ]
        outlet_context_keywords = [
            "agent", "agent outlet", "outlet", "booth", "counter", "branch", "service point"
        ]
        ops_context_keywords = [
            "customer service", "cash transaction", "cash transactions", "cash withdrawal", "cash deposit"
        ]
        if (
            ("staff" in query_lower or any(k in query_lower for k in ["manpower", "headcount", "personnel"]))
            and any(k in query_lower for k in staffing_count_keywords)
            and any(k in query_lower for k in staffing_intent_keywords)
            and (any(k in query_lower for k in outlet_context_keywords) or any(k in query_lower for k in ops_context_keywords))
        ):
            logger.info(f"[ROUTING] Staffing requirement query detected - NOT routing to phonebook: '{query}'")
            return False
        
        # Pattern 0: "find" or "search" followed by employee ID pattern (e.g., "find cr_app3_test", "search abc123")
        # Employee IDs often contain underscores, letters, and numbers
        # Match patterns like: "find X", "search X", "lookup X", "who is X", "contact X", "info about X"
        find_search_patterns = [
            r'\b(find|search|lookup|contact|info about)\s+([a-z0-9_]+)',  # "find cr_app3_test" or "find abc123"
            r'\b(who is)\s+([a-z0-9_]+)',  # "who is cr_app3_test"
        ]
        for pattern in find_search_patterns:
            match = re.search(pattern, query_lower)
            if match:
                # Check if the matched term looks like an employee ID or name
                search_term = match.group(2) if len(match.groups()) >= 2 else ""
                # Employee IDs typically: contain underscores, or are alphanumeric with at least 3 chars
                if search_term and len(search_term) >= 3:
                    # If it contains underscore or looks like an ID pattern, route to phonebook
                    if '_' in search_term or re.match(r'^[a-z0-9]+$', search_term):
                        logger.info(f"[ROUTING] Detected find/search query with employee ID/name pattern '{search_term}' → phonebook")
                        return True
        
        # Pattern 1: "who is" + role/designation queries (e.g., "who is the branch manager")
        # This catches queries asking about specific people in specific roles
        who_is_patterns = [
            r'who\s+is\s+(the\s+)?(branch\s+)?manager',
            r'who\s+is\s+(the\s+)?(.*\s+)?manager\s+of',
            r'who\s+is\s+the\s+(.*\s+)?manager',
            r'who\s+is\s+(the\s+)?(head|director|officer|executive)\s+of',
            r'who\s+is\s+(the\s+)?(.*\s+)?(head|director|officer|executive)',
        ]
        if any(re.search(pattern, query_lower) for pattern in who_is_patterns):
            logger.info(f"[ROUTING] Detected 'who is' role query → phonebook")
            return True
        
        # Pattern 2: Role + "of" + location/branch (e.g., "branch manager of Gulshan")
        role_location_patterns = [
            r'(branch\s+)?manager\s+of',
            r'manager\s+of\s+(.*\s+)?branch',
            r'(head|director|officer)\s+of\s+(.*\s+)?branch',
            r'(.*\s+)?manager\s+at\s+(.*\s+)?branch',
        ]
        if any(re.search(pattern, query_lower) for pattern in role_location_patterns):
            logger.info(f"[ROUTING] Detected role + location query → phonebook")
            return True
        
        # Pattern 3: VERY SPECIFIC employee search/lookup keywords
        employee_keywords = [
            'employee id', 'employee number', 'emp id', 'emp_id',
            'employee phone', 'employee email', 'employee contact',
            'staff phone', 'staff email', 'staff contact',
            'who is employee', 'who are employees', 'find employee',
            'search employee', 'lookup employee', 'employee directory',
            'staff directory', 'employee list', 'staff list'
        ]
        
        # Pattern 4: "employee" or "staff" combined with contact-related terms
        if 'employee' in query_lower or 'staff' in query_lower:
            # Only if combined with contact/search terms
            contact_terms = ['phone', 'email', 'contact', 'number', 'id', 'search', 'find', 'lookup', 'who']
            if any(term in query_lower for term in contact_terms):
                return True
        
        return any(keyword in query_lower for keyword in employee_keywords)
    
    def _is_financial_report_query(self, query: str) -> bool:
        """Detect if query is about financial reports"""
        query_lower = query.lower().strip()
        
        financial_keywords = [
            'financial report', 'annual report', 'quarterly report', 'financial statement',
            'revenue', 'profit', 'loss', 'income statement', 'balance sheet',
            'cash flow', 'earnings', 'dividend', 'financial year', 'fiscal year',
            'audit', 'auditor', 'financial performance', 'financial results',
            'quarterly results', 'annual results', 'financial data', 'financial metrics'
        ]
        
        return any(keyword in query_lower for keyword in financial_keywords)
    
    def _is_user_document_query(self, query: str) -> bool:
        """Detect if query is about user-uploaded documents"""
        query_lower = query.lower().strip()
        
        user_doc_keywords = [
            'user document', 'uploaded document', 'custom document', 'my document',
            'document i uploaded', 'document i provided', 'my file', 'uploaded file',
            'custom file', 'user file', 'personal document', 'my upload'
        ]
        
        return any(keyword in query_lower for keyword in user_doc_keywords)
    
    def _is_organizational_overview_query(self, query: str) -> bool:
        """
        Detect if query is asking for high-level organizational overview about EBL/Eastern Bank.
        These queries should get customer-facing overviews, NOT investor/financial content.
        
        Examples:
        - "tell me about EBL"
        - "what is EBL"
        - "about Eastern Bank"
        - "tell me about Eastern Bank PLC"
        """
        query_lower = query.lower().strip()
        
        # Patterns that indicate organizational overview queries
        overview_patterns = [
            # "tell me about" + bank name
            (r'tell\s+me\s+about\s+(ebl|eastern\s+bank)', 'tell me about EBL/Eastern Bank'),
            # "what is" + bank name
            (r'what\s+is\s+(ebl|eastern\s+bank)', 'what is EBL/Eastern Bank'),
            # "about" + bank name (at start or after "tell me")
            (r'^about\s+(ebl|eastern\s+bank)', 'about EBL/Eastern Bank'),
            # "who is" + bank name
            (r'who\s+is\s+(ebl|eastern\s+bank)', 'who is EBL/Eastern Bank'),
            # "describe" + bank name
            (r'describe\s+(ebl|eastern\s+bank)', 'describe EBL/Eastern Bank'),
        ]
        
        for pattern, description in overview_patterns:
            if re.search(pattern, query_lower):
                logger.info(f"[ROUTING] Detected organizational overview query: '{description}'")
                return True
        
        return False
    
    def _is_management_query(self, query: str) -> bool:
        """Detect if query is about EBL management/management committee"""
        query_lower = query.lower().strip()
        
        management_keywords = [
            'management', 'management committee', 'mancom', 'managing director',
            'md and ceo', 'deputy managing director', 'chief financial officer', 'cfo',
            'chief technology officer', 'cto', 'chief risk officer', 'cro',
            'head of', 'unit head', 'executive committee', 'management team',
            'who is the managing director', 'who is the cfo', 'who is the cto',
            'management structure', 'organizational structure', 'management hierarchy',
            'ebl management', 'ebl executives', 'bank management', 'leadership team'
        ]
        
        return any(keyword in query_lower for keyword in management_keywords)
    
    def _is_milestone_query(self, query: str) -> bool:
        """
        Detect if query is about EBL milestones/history/achievements.
        NOT greedy - only matches explicit milestone/history queries, NOT general "about ebl" queries.
        """
        query_lower = query.lower().strip()
        
        # Normalize "mile stone" to "milestone" for matching
        query_normalized = query_lower.replace('mile stone', 'milestone').replace('mile-stone', 'milestone')
        
        # CRITICAL: Check if this is an organizational overview query FIRST
        # If it is, it should NOT be treated as a milestone query
        if self._is_organizational_overview_query(query):
            return False
        
        # Only match if query EXPLICITLY mentions milestone/history keywords
        # Remove "about ebl" and "ebl background" from keywords - these are too generic
        milestone_keywords = [
            'milestone', 'milestones', 'history', 'historical', 'achievement', 'achievements',
            'timeline', 'journey', 'evolution', 'development', 'growth', 'progress',
            'founded', 'establishment', 'established', 'inception', 'origin', 'beginnings',
            'ebl milestone', 'ebl milestones', 'ebl history', 'bank milestone', 'bank milestones',
            'what are the milestones', 'ebl achievements',
            'bank achievements', 'company history', 'bank history', 'corporate history'
            # REMOVED: 'about ebl', 'ebl background', 'ebl information' - too generic, caught by org overview
        ]
        
        return any(keyword in query_normalized for keyword in milestone_keywords)
    
    def _is_fee_schedule_query(self, query: str) -> bool:
        """
        STRONG detector for fee/charge schedule queries.
        Returns True if query contains fee-related keywords with card context.
        This ensures ALL card fee queries route to Fee Engine (authoritative source).
        
        Hardening: Generic terms (price, pricing, cost) require card-related context
        to prevent false positives (e.g., "loan pricing" should not route to card fees).
        
        EXCLUDES: Retail asset charges (fast cash, loans, etc.) - these are handled separately.
        """
        query_lower = query.lower().strip()
        
        # Guardrail: Transaction-limit / allowed-count queries should NOT route to fee engine.
        # Examples:
        # - "maximum number of daily Cash Withdrawal transactions allowed for a Savings Account"
        # - "how many cash transactions are allowed per day"
        limit_intent_keywords = [
            "maximum number", "max number", "how many", "number of",
            "limit", "limits", "allowed", "permit", "per day", "daily", "in a day",
        ]
        transaction_words = ["transaction", "transactions", "cash withdrawal", "withdrawal", "deposit"]
        account_words = ["savings account", "current account", "account"]
        fee_intent_words = ["fee", "fees", "charge", "charges", "rate", "pricing", "price", "cost", "commission"]

        if (
            any(k in query_lower for k in limit_intent_keywords)
            and any(w in query_lower for w in transaction_words)
            and any(w in query_lower for w in account_words)
            and not any(w in query_lower for w in fee_intent_words)
        ):
            logger.info(f"[ROUTING] Transaction-limit query detected - NOT routing to fee engine: '{query}'")
            return False
        
        # EXCLUDE retail asset/loan queries - these should NOT route to card fees
        retail_asset_keywords = [
            "fast cash", "fast loan", "education loan", "edu loan",
            "personal loan", "home loan", "car loan", "auto loan",
            "business loan", "executive loan", "assure loan", "women's loan",
            "retail asset", "loan processing", "loan fee", "loan charge",
            "overdraft", "od", "emi loan", "secured loan", "unsecured loan"
        ]
        
        # If query contains retail asset keywords, it's NOT a card fee query
        if any(kw in query_lower for kw in retail_asset_keywords):
            logger.info(f"[ROUTING] Query contains retail asset keywords - NOT routing to card fees: '{query}'")
            return False
        
        # Card-related context keywords (required for generic terms)
        card_context_keywords = [
            "card", "atm", "lounge", "supplementary", "pin", "rfcd",
            "visa", "mastercard", "diners", "unionpay", "taka pay",
            "credit card", "debit card", "prepaid card",
            "classic", "gold", "platinum", "infinite", "signature", "titanium", "world"
        ]
        
        # Specific fee types (always route - these are card-specific)
        specific_fee_keywords = [
            "annual fee", "yearly fee", "renewal fee", "issuance fee", "issuance charge", 
            "joining fee", "replacement fee", "card replacement", "pin replacement", 
            "pin fee", "late payment fee", "late fee", "overlimit fee", "over-limit fee",
            
            # Transaction fees (card-specific)
            "cash advance fee", "cash withdrawal fee", "atm withdrawal fee", 
            "withdrawal fee", "transaction fee",
            
            # Service fees (card-specific)
            "duplicate statement fee", "duplicate estatement", "certificate fee",
            "chequebook fee", "customer verification fee", "cib fee", 
            "transaction alert fee", "sms alert", "transaction alert",
            "sales voucher fee", "sales voucher", "return cheque fee",
            "undelivered card fee", "atm receipt fee", "cctv footage fee",
            "cctv", "fund transfer fee", "wallet transfer fee",
            "want2buy fee", "easycredit fee", "risk assurance fee",
            "balance maintenance fee",
            
            # Interest rates (card-specific)
            "interest rate", "rate of interest", "apr", "annual percentage rate",
            "card interest", "credit card rate",
            
            # Lounge access (card-specific)
            "lounge", "lounge access", "sky lounge", "airport lounge", "lounge visit",
            "skylounge", "international lounge", "domestic lounge", "global lounge",
            "lounge free visit", "lounge fee", "priority pass",
            
            # Supplementary card fee queries (avoid overly-broad "how many")
            "supplementary fee", "supplementary charge", "supplementary annual fee",
            "free supplementary", "supplementary card free",
            
            # Schedule/document references
            "fee schedule", "charges schedule", "card charges", "card fees",
            "fee information", "charge information",
            
            # Core fee terms (when used with card context or in card-specific phrases)
            "fee", "fees", "charge", "charges"
        ]
        
        # Generic terms that require card context
        generic_terms = ["cost", "pricing", "price"]
        
        # Check for specific card-fee phrases (always route)
        if any(kw in query_lower for kw in specific_fee_keywords):
            # But avoid routing generic "fee/charge" unless we have card context or schedule reference
            has_card_context = any(ctx in query_lower for ctx in card_context_keywords)
            has_schedule_ref = any(ref in query_lower for ref in ["fee schedule", "charges schedule", "card charges", "card fees"])
            has_specific_phrase = any(
                kw in query_lower
                for kw in [
                    "annual fee", "issuance fee", "replacement fee", "late payment fee",
                    "overlimit fee", "cash withdrawal fee", "atm withdrawal fee", "cash advance fee",
                    "sales voucher fee", "transaction alert fee", "lounge fee", "lounge free visit",
                    "supplementary fee", "supplementary annual fee",
                ]
            )
            if has_specific_phrase:
                return True
            return has_card_context or has_schedule_ref
        
        # Check for generic terms - require card context
        has_generic_term = any(term in query_lower for term in generic_terms)
        if has_generic_term:
            # Generic term found - require card context
            has_card_context = any(ctx in query_lower for ctx in card_context_keywords)
            return has_card_context
        
        # No match
        return False
    
    def _is_retail_asset_fee_query(self, query: str) -> bool:
        """
        Detect if query is about retail asset charges (loans, fast cash, etc.).
        Returns True if query contains retail asset keywords with fee/charge context.
        """
        query_lower = query.lower().strip()
        
        # FIX #5: Retail-asset-exclusive fee terms (these fees only exist for retail assets)
        # Check these FIRST - if present and NOT a card query, route to RETAIL_ASSETS
        retail_asset_exclusive_fees = [
            'partial payment fee', 'partial payment',
            'early settlement fee', 'early settlement', 'early_settlement',
            # Stamp duty/charge is a retail-asset charge in our v2 schedule
            'stamp charge', 'stamp duty',
            # Reschedule / restructure fees (retail assets v2)
            'reschedule & restructure fee', 'reschedule and restructure fee',
            'reschedule & restructure exit fee', 'reschedule and restructure exit fee',
            'reschedule fee', 'rescheduling fee',
            'restructure fee', 'restructuring fee',
            # Common retail-asset charge terms that users ask without saying "loan"
            'notarization fee',
            'noc fee', 'loan repayment certificate', 'loan repayment certificate (noc)',
            'loan outstanding certificate', 'loan outstanding certificate fee',
        ]
        has_exclusive_fee = any(fee_term in query_lower for fee_term in retail_asset_exclusive_fees)
        has_card_keyword = any(card_kw in query_lower for card_kw in ['card', 'credit card', 'debit card', 'visa', 'mastercard'])
        
        if has_exclusive_fee and not has_card_keyword:
            logger.info(f"[ROUTING] Retail asset exclusive fee query detected (no product keyword required): '{query}'")
            return True
        
        # Retail asset product keywords
        retail_asset_keywords = [
            "fast cash", "fast loan", "education loan", "edu loan",
            "personal loan", "home loan", "car loan", "auto loan",
            "business loan", "executive loan", "assure loan", "women's loan",
            "retail asset", "loan processing", "overdraft", "od", "emi loan"
        ]
        
        # Fee/charge keywords
        fee_keywords = [
            "fee", "fees", "charge", "charges", "cost", "pricing", "price",
            "processing fee", "enhancement fee", "reduction fee", "cancellation fee",
            "renewal fee", "settlement fee", "early_settlement_fee", "settlement"
        ]
        
        # Check if query contains both retail asset keywords AND fee keywords
        has_retail_asset = any(kw in query_lower for kw in retail_asset_keywords)
        has_fee_keyword = any(kw in query_lower for kw in fee_keywords)
        
        if has_retail_asset and has_fee_keyword:
            logger.info(f"[ROUTING] Retail asset fee query detected: '{query}'")
            return True
        
        return False
    
    def _is_skybanking_fee_query(self, query: str) -> bool:
        """
        Detect if query is about Skybanking fees/charges.
        Returns True if query contains Skybanking keywords with fee/charge context.
        """
        query_lower = query.lower().strip()
        
        # Skybanking product keywords
        skybanking_keywords = [
            "skybanking", "sky banking", "ebl skybanking",
            "digital banking", "mobile banking", "online banking",
            "skybanking app", "ebl app", "mobile app"
        ]
        
        # Fee/charge keywords
        fee_keywords = [
            "fee", "fees", "charge", "charges", "cost", "pricing", "price",
            "certificate fee", "account certificate", "fund transfer fee",
            "transfer fee", "transaction fee"
        ]
        
        # Check if query contains both Skybanking keywords AND fee keywords
        has_skybanking = any(kw in query_lower for kw in skybanking_keywords)
        has_fee_keyword = any(kw in query_lower for kw in fee_keywords)
        
        if has_skybanking and has_fee_keyword:
            logger.info(f"[ROUTING] Skybanking fee query detected: '{query}'")
            return True
        
        return False
    
    def _is_card_rates_query(self, query: str) -> bool:
        """
        Legacy method - now delegates to _is_fee_schedule_query for consistency.
        Kept for backward compatibility.
        """
        return self._is_fee_schedule_query(query)
    
    def _is_location_query(self, query: str) -> bool:
        """
        Detect if query is about locations (branches, ATMs, CRMs, RTDMs, priority centers, head office).
        
        Returns True if query contains location-related keywords.
        """
        query_lower = query.lower()
        
        # Location keywords - check for explicit location-related terms
        location_keywords = [
            # Branches
            'branch', 'branches', 'bank branch', 'ebl branch',
            # Head office
            'head office', 'headoffice', 'headquarter', 'headquarters', 'corporate office', 'main office',
            # ATMs
            'atm', 'atms', 'automated teller machine', 'cash machine', 'cashpoint',
            # CRMs
            'crm', 'customer relationship machine', 'customer service machine',
            # RTDMs
            'rtdm', 'retail transaction deposit machine', 'deposit machine',
            # Priority centers - CRITICAL: All priority center queries must go to location service
            'priority center', 'priority centre', 'priority centers', 'priority centres',
            'priority banking center', 'priority banking centre', 'priority banking centers', 'priority banking centres',
            # General location queries - expanded patterns
            'where is', 'where are', 'where can i find', 'where can i locate',
            'find branch', 'find atm', 'locate', 'location', 'address', 'address of',
            'location of', 'tell me location', 'what is the location', 'what is the address',
            'nearest branch', 'nearest atm', 'near me', 
            'in dhaka', 'in chittagong', 'in sylhet', 'in khulna', 'in rajshahi',
            'dhaka branch', 'chittagong branch', 'sylhet branch'
        ]
        
        # Check for location-related patterns
        import re
        location_patterns = [
            r'\blocation\s+of\b',  # "location of X"
            r'\baddress\s+of\b',   # "address of X"
            r'\bwhere\s+is\b',     # "where is X"
            r'\bwhere\s+are\b',    # "where are X"
            r'\btell\s+me\s+(the\s+)?(location|address)',  # "tell me location/address"
            r'\bwhat\s+is\s+the\s+(location|address)',     # "what is the location/address"
            # Count queries for priority centers - CRITICAL: These must go to location service
            r'\bhow\s+many\s+priority\s+(center|centre)',  # "how many priority center"
            r'\bhow\s+many\s+priority\s+(center|centre)s',  # "how many priority centers"
            r'\bnumber\s+of\s+priority\s+(center|centre)',  # "number of priority center"
            r'\bcount\s+of\s+priority\s+(center|centre)',  # "count of priority center"
            r'\bpriority\s+(center|centre).*\b(how many|number|count|total)',  # "priority center how many"
        ]
        
        # Check if query contains location keywords
        has_location_keyword = any(kw in query_lower for kw in location_keywords)
        
        # Check for location patterns using regex
        has_location_pattern = any(re.search(pattern, query_lower) for pattern in location_patterns)
        
        # Also check if query mentions a branch name pattern (e.g., "AGRABAD BRANCH", "Dhanmondi branch")
        # This catches queries like "location of AGRABAD BRANCH" even if "branch" comes after
        has_branch_name_pattern = bool(re.search(r'\b(branch|atm|crm|rtdm|priority\s+center|priority\s+centre)\b', query_lower, re.IGNORECASE))
        
        # CRITICAL: Special check for priority center count queries
        # These queries MUST go to location service, not LightRAG
        has_priority_center_count_query = bool(
            re.search(r'\b(how many|number|count|total).*priority\s+(center|centre)', query_lower, re.IGNORECASE) or
            re.search(r'\bpriority\s+(center|centre).*\b(how many|number|count|total|does.*have|has)', query_lower, re.IGNORECASE)
        )
        
        # Return True if any location indicator is found
        is_location = has_location_keyword or has_location_pattern or has_branch_name_pattern or has_priority_center_count_query
        
        if is_location:
            logger.info(f"[ROUTING] Detected location query: '{query}' (keyword={has_location_keyword}, pattern={has_location_pattern}, branch_pattern={has_branch_name_pattern}, priority_count={has_priority_center_count_query})")
            return True
        
        return False
    
    async def _get_location_context(self, query: str) -> str:
        """
        Get location context from location service.
        
        Args:
            query: Natural language query about locations
        
        Returns:
            Formatted location information string
        """
        try:
            location_result = await self.location_client.get_locations(query, limit=20)
            
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
    
    def _is_compliance_query(self, query: str) -> bool:
        """Detect if query is about compliance, AML, regulatory, or policy matters"""
        query_lower = query.lower().strip()
        
        compliance_keywords = [
            # AML (Anti-Money Laundering)
            'aml', 'anti money laundering', 'anti-money laundering', 'money laundering',
            'aml policy', 'aml compliance', 'aml regulation', 'aml requirements',
            'aml customer', 'aml customers', 'aml sensitive', 'aml risk',
            
            # Compliance & Regulatory
            'compliance', 'regulatory', 'regulation', 'regulations', 'regulatory compliance',
            'compliance policy', 'compliance requirement', 'compliance requirements',
            'regulatory policy', 'regulatory requirement', 'regulatory requirements',
            
            # Policy & Procedures
            'policy', 'policies', 'procedure', 'procedures', 'guideline', 'guidelines',
            'bank policy', 'banking policy', 'bank policies', 'banking policies',
            'internal policy', 'internal policies', 'operational policy',
            
            # KYC (Know Your Customer)
            'kyc', 'know your customer', 'kyc policy', 'kyc compliance', 'kyc requirement',
            'kyc requirements', 'customer due diligence', 'cdd',
            
            # Risk & Fraud
            'risk management', 'fraud prevention', 'fraud detection', 'suspicious activity',
            'suspicious transaction', 'transaction monitoring', 'sanctions',
            'sanctions screening', 'ofac', 'pep', 'politically exposed person',
            
            # Sensitive Customers
            'sensitive customer', 'sensitive customers', 'high risk customer',
            'high risk customers', 'risk customer', 'risk customers',
            
            # Regulatory Bodies
            'bangladesh bank', 'central bank', 'bb guideline', 'bb guidelines',
            'regulatory authority', 'regulatory authorities'
        ]
        
        return any(keyword in query_lower for keyword in compliance_keywords)
    
    def _check_policy_entities(self, query: str) -> tuple[bool, Optional[str]]:
        """
        Check if a policy query has required entities.
        Returns: (has_required_entities, clarification_question_if_missing)
        """
        import re
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
    
    def _is_banking_product_query(self, query: str) -> bool:
        """Detect if query is about banking products/services (should use LightRAG, not phonebook)"""
        query_lower = query.lower().strip()
        
        # Card product names that indicate a card query (even without the word "card")
        card_products = [
            "classic", "gold", "platinum", "infinite", "signature", "titanium", 
            "world", "visa", "mastercard", "diners club", "unionpay", "taka pay",
            "prepaid", "debit", "credit", "rfcd", "global"
        ]
        
        # Check if query mentions card products (even without "card" word)
        has_card_product = any(product in query_lower for product in card_products)
        has_card_keyword = "card" in query_lower
        
        # If query mentions card products + fee/rate keywords, it's a banking product query
        card_fee_rate_keywords = ['fee', 'fees', 'charge', 'charges', 'rate', 'rates', 'annual', 'yearly', 'interest', 'supplementary', 'supplement']
        if has_card_product or has_card_keyword:
            if any(kw in query_lower for kw in card_fee_rate_keywords):
                logger.info(f"[ROUTING] Detected card product query: has_card_product={has_card_product}, has_card_keyword={has_card_keyword}, fee_rate_keywords={[kw for kw in card_fee_rate_keywords if kw in query_lower]}")
                return True
        
        # Banking product/service keywords - these should go to LightRAG, NOT phonebook
        banking_product_keywords = [
            # Credit/Debit Cards
            'credit card', 'debit card', 'card limit', 'card conversion', 'card upgrade',
            'card feature', 'card benefit', 'card reward', 'card fee', 'card charge',
            'card application', 'card activation', 'card statement', 'card transaction',
            
            # Loans
            'loan', 'personal loan', 'home loan', 'car loan', 'business loan',
            'loan interest', 'loan rate', 'loan term', 'loan eligibility', 'loan application',
            'loan approval', 'loan repayment', 'loan emi', 'loan processing',
            
            # Accounts
            'account', 'accounts',  # Standalone account keyword to catch all account types
            'savings account', 'current account', 'fixed deposit', 'fd', 'rd', 'recurring deposit',
            'rfcd', 'rfd', 'recurring fixed', 'recurring fixed deposit',  # RFCD account types
            'account opening', 'account balance', 'account statement', 'account fee',
            'account interest', 'account rate', 'account minimum balance',
            'account type', 'account types', 'types of account', 'kinds of account',
            
            # Corporate/Commercial Banking
            'corporate customer', 'corporate customers', 'corporate account', 'corporate accounts',
            'corporate banking', 'commercial customer', 'commercial customers',
            'corporate service', 'corporate process', 'corporate procedure',
            'corporate requirement', 'corporate requirements', 'corporate policy',
            'corporate confirmation', 'email confirmation', 'email verification',
            'processing requirement', 'processing requirements', 'before processing',
            'whose email confirmation', 'email confirmation required', 'confirmation required',
            'prior email confirmation', 'prior confirmation', 'subject to prior',
            'subject to email', 'processing subject to', 'subject to confirmation',
            'in case of corporate', 'case of corporate', 'corporate processing',
            'in the case of', 'in case of', 'case of', 'subject to',
            
            # Banking Services
            'online banking', 'mobile banking', 'internet banking', 'atm', 'cash withdrawal',
            'fund transfer', 'remittance', 'foreign exchange', 'forex', 'currency exchange',
            'locker', 'safe deposit', 'cheque', 'draft', 'demand draft',
            'standing instruction', 'standing instructions', 'si', 'si setup', 'si cancellation',
            'si cancel', 'cancel si', 'cancel standing instruction', 'recurring payment',
            'recurring transfer', 'automatic payment', 'automatic transfer', 'auto debit',
            'auto credit', 'scheduled payment', 'scheduled transfer', 'recurring debit',
            'recurring credit', 'auto payment', 'auto transfer',
            
            # Branch/Center Locations
            'priority center', 'priority centre', 'priority centers', 'priority centres',
            'branch', 'branches', 'branch location', 'branch locations',
            'center', 'centre', 'centers', 'centres', 'service center', 'service centre',
            'how many', 'number of', 'count of', 'list of', 'where is', 'where are',
            'sylhet', 'dhaka', 'chittagong', 'city', 'location', 'locations',
            
            # Products & Services
            'banking product', 'financial product', 'service', 'banking service',
            'product feature', 'product benefit', 'product eligibility', 'product requirement',
            'interest rate', 'exchange rate', 'service charge', 'fee structure',
            'conversion', 'upgrade', 'downgrade', 'limit', 'limit increase', 'limit decrease',
            
            # Company Information & History
            'milestone', 'milestones', 'history', 'about ebl', 'ebl history', 'ebl background',
            'company history', 'bank history', 'establishment', 'founded', 'founding',
            'achievement', 'achievements', 'award', 'awards', 'recognition', 'recognition',
            'timeline', 'journey', 'evolution', 'growth', 'development', 'progress'
        ]
        
        # Check for banking product patterns
        return any(keyword in query_lower for keyword in banking_product_keywords)
    
    def _detect_lead_intent(self, query: str) -> Optional[LeadType]:
        """Detect if user wants to apply for credit card or loan"""
        query_lower = query.lower().strip()
        
        # Credit card intent keywords
        credit_card_keywords = [
            'apply for credit card', 'want credit card', 'need credit card',
            'get credit card', 'credit card application', 'apply credit card',
            'interested in credit card', 'credit card interest', 'new credit card',
            'generate a lead for credit card', 'lead for credit card', 'create lead credit card'
        ]
        
        # Loan intent keywords
        loan_keywords = [
            'apply for loan', 'want loan', 'need loan', 'get loan',
            'loan application', 'apply loan', 'interested in loan',
            'loan interest', 'personal loan', 'home loan', 'car loan',
            'business loan', 'new loan', 'generate a lead for loan',
            'lead for loan', 'create lead loan', 'generate lead'
        ]
        
        if any(keyword in query_lower for keyword in credit_card_keywords):
            return LeadType.CREDIT_CARD
        elif any(keyword in query_lower for keyword in loan_keywords):
            return LeadType.LOAN
        
        return None
    
    def _get_lead_questions(self, lead_type: LeadType) -> List[Dict[str, str]]:
        """Get questions for lead collection based on type"""
        if lead_type == LeadType.CREDIT_CARD:
            return [
                {"field": "full_name", "question": "Great! I'd be happy to help you apply for a credit card. May I have your full name?"},
                {"field": "phone", "question": "Thank you! What's your phone number?"},
                {"field": "email", "question": "And your email address?"},
                {"field": "date_of_birth", "question": "What's your date of birth? (DD/MM/YYYY)"},
                {"field": "employment_status", "question": "What's your employment status? (Employed/Self-employed/Student/Retired)"},
                {"field": "monthly_income", "question": "What's your approximate monthly income? (BDT)"},
            ]
        elif lead_type == LeadType.LOAN:
            return [
                {"field": "full_name", "question": "Great! I'd be happy to help you with a loan application. May I have your full name?"},
                {"field": "phone", "question": "Thank you! What's your phone number?"},
                {"field": "email", "question": "And your email address?"},
                {"field": "loan_type", "question": "What type of loan are you interested in? (Personal/Home/Car/Business)"},
                {"field": "loan_amount", "question": "What loan amount are you looking for? (BDT)"},
                {"field": "employment_status", "question": "What's your employment status? (Employed/Self-employed/Student/Retired)"},
                {"field": "monthly_income", "question": "What's your approximate monthly income? (BDT)"},
            ]
        return []
    
    def _extract_answer(self, query: str, field: str) -> Optional[str]:
        """Extract answer from user query based on field type"""
        query_lower = query.lower().strip()
        
        # For email
        if field == "email":
            import re
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            match = re.search(email_pattern, query)
            if match:
                return match.group(0)
        
        # For phone
        elif field == "phone":
            import re
            # Extract digits
            digits = re.sub(r'\D', '', query)
            if len(digits) >= 10:
                return digits
        
        # For date of birth
        elif field == "date_of_birth":
            import re
            date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
            match = re.search(date_pattern, query)
            if match:
                return match.group(0)
        
        # For amounts
        elif field in ["loan_amount", "monthly_income"]:
            import re
            # Extract numbers
            numbers = re.findall(r'\d+', query.replace(',', ''))
            if numbers:
                return numbers[0]
        
        # For other fields, return the query as-is (user might have provided the answer directly)
        return query.strip() if query.strip() else None
    
    def _process_lead_collection(
        self,
        session_id: str,
        query: str
    ) -> tuple[str, bool]:
        """
        Process lead collection flow
        Returns: (response_message, is_complete)
        """
        if session_id not in self.lead_flows:
            self.lead_flows[session_id] = LeadFlowState()
        
        flow = self.lead_flows[session_id]
        
        # Check if user wants to cancel
        if any(word in query.lower() for word in ['cancel', 'stop', 'nevermind', 'no thanks', 'no thank you']):
            flow.reset()
            return "No problem! I've cancelled the application. How else can I help you today?", True
        
        # Get current question
        if flow.current_question_index < len(flow.questions):
            current_q = flow.questions[flow.current_question_index]
            field = current_q["field"]
            
            # Extract answer
            answer = self._extract_answer(query, field)
            
            if answer:
                # Store answer
                flow.collected_data[field] = answer
                flow.current_question_index += 1
                
                # Check if we have more questions
                if flow.current_question_index < len(flow.questions):
                    next_q = flow.questions[flow.current_question_index]
                    return next_q["question"], False
                else:
                    # All questions answered - save lead
                    if LEADS_AVAILABLE:
                        lead_manager = LeadManager()
                        lead = lead_manager.create_lead(
                            session_id=session_id,
                            lead_type=flow.lead_type,
                            full_name=flow.collected_data.get("full_name"),
                            email=flow.collected_data.get("email"),
                            phone=flow.collected_data.get("phone"),
                            date_of_birth=flow.collected_data.get("date_of_birth"),
                            additional_info={k: v for k, v in flow.collected_data.items() 
                                           if k not in ["full_name", "email", "phone", "date_of_birth"]}
                        )
                        
                        if lead:
                            flow.reset()
                            lead_type_name = flow.lead_type.value.replace('_', ' ').title()
                            return f"Thank you! I've submitted your {lead_type_name} application. Our team will contact you shortly. Your application ID is #{lead.id}. Is there anything else I can help you with?", True
                        else:
                            flow.reset()
                            return "I apologize, but there was an error saving your application. Please try again later or contact our support team.", True
                    else:
                        flow.reset()
                        return "I apologize, but the lead generation system is currently unavailable. Please contact our support team directly.", True
            else:
                # Couldn't extract answer - ask again
                return f"I didn't quite catch that. {current_q['question']}", False
        else:
            # No more questions - should not happen
            flow.reset()
            return "Thank you for your interest! How else can I help you?", True
    
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
    
    def _get_current_datetime(self) -> str:
        """Get current date and time in a formatted string"""
        try:
            # Try to get timezone from settings, default to UTC
            timezone_str = getattr(settings, 'TIMEZONE', 'UTC')
            tz = pytz.timezone(timezone_str)
        except Exception:
            # Fallback to system local time if timezone is invalid
            tz = None
        
        if tz:
            now = datetime.now(tz)
        else:
            # Use system local time
            now = datetime.now()
        
        # Format: "Monday, December 9, 2025 at 2:45:30 PM UTC"
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%I:%M:%S %p")
        
        if tz:
            timezone_str = now.strftime("%Z")
            return f"{date_str} at {time_str} {timezone_str}"
        else:
            return f"{date_str} at {time_str}"
    
    def _clean_markdown_formatting(self, text: str) -> str:
        """
        Remove markdown formatting from text (especially ** for bold)
        This ensures clean text output without markdown syntax
        """
        if not text:
            return text
        
        import re
        # Remove markdown bold (**text**)
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        # Remove markdown italic (*text* or _text_)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        text = re.sub(r'_(.*?)_', r'\1', text)
        # Remove markdown code blocks (```code```)
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        # Remove markdown inline code (`code`)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # Remove markdown headers (# Header)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        
        return text
    
    def _fix_currency_symbols(self, text: str, context: str = "") -> str:
        """
        Fix currency symbol hallucinations - replace incorrect currency symbols with correct ones.
        This is a safety net to catch cases where LLM hallucinates currency symbols.
        """
        if not text:
            return text
        
        import re
        
        # Check if context contains BDT amounts
        has_bdt_in_context = "BDT" in context if context else False
        
        # Pattern to match currency symbols followed by numbers (₹287.5, ₹1,725, etc.)
        # Replace ₹ (Indian Rupee) with BDT if context has BDT
        if has_bdt_in_context:
            # Match ₹ followed by optional space and number
            text = re.sub(r'₹\s*(\d+(?:[.,]\d+)?)', r'BDT \1', text)
            # Also catch cases where ₹ might be used with commas
            text = re.sub(r'₹\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)', r'BDT \1', text)
        
        return text
    
    def _fix_bank_name(self, text: str) -> str:
        """
        Fix bank name - replace "Eastern Bank Limited" or "Eastern Bank Ltd." with "Eastern Bank PLC." (with period).
        Also ensures "Eastern Bank PLC" (without period) becomes "Eastern Bank PLC." (with period).
        This ensures consistent bank name usage across all responses.
        """
        if not text:
            return text
        
        import re
        
        # Replace "Eastern Bank Limited" with "Eastern Bank PLC." (case-insensitive)
        text = re.sub(r'Eastern Bank Limited', 'Eastern Bank PLC.', text, flags=re.IGNORECASE)
        # Replace "Eastern Bank Ltd." with "Eastern Bank PLC." (case-insensitive)
        text = re.sub(r'Eastern Bank Ltd\.', 'Eastern Bank PLC.', text, flags=re.IGNORECASE)
        # Also catch "Eastern Bank Ltd" without period
        text = re.sub(r'Eastern Bank Ltd\b', 'Eastern Bank PLC.', text, flags=re.IGNORECASE)
        
        # Ensure "Eastern Bank PLC" (without period) becomes "Eastern Bank PLC." (with period)
        # More aggressive: replace ALL instances of "Eastern Bank PLC" (without period) with "Eastern Bank PLC."
        # First, handle cases where it's already followed by a period (do nothing)
        # Then, replace all other instances
        # Match "Eastern Bank PLC" that is NOT followed by a period
        text = re.sub(r'\bEastern Bank PLC\b(?!\.)', 'Eastern Bank PLC.', text, flags=re.IGNORECASE)
        
        return text
    
    def _resolve_selection(self, query: str, options: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Resolve user selection from query.
        
        Args:
            query: User's query/message
            options: List of option dicts with loan_product, loan_product_name, charge_context, etc.
        
        Returns:
            Selected option dict or None if no match
        """
        import re
        query_lower = query.strip().lower()
        
        # Stopwords that should not be used for matching (common words in answer_text)
        STOPWORDS = {
            "fee", "card", "bdt", "usd", "per", "transaction", "amount", "charge", "on", "the", "a", "an",
            "for", "of", "in", "at", "to", "from", "with", "by", "or", "and", "is", "are", "was", "were",
            "balance", "outstanding", "year", "month", "day", "leaves", "leaf", "page", "schedule"
        }
        
        # Minimum token length for keyword matching (ignore very short tokens)
        MIN_TOKEN_LENGTH = 3
        
        # Fix A: Extract leading number with regex to handle "1.", "1)", "1. Fast Cash...", etc.
        # Match patterns like: "1", "1.", "1)", "1. Fast Cash", "1) Fast Cash", etc.
        m = re.match(r"^\s*(\d+)\s*[\.\)]?\s*", query_lower)
        if m:
            try:
                selection_num = int(m.group(1))
                if 1 <= selection_num <= len(options):
                    selected = options[selection_num - 1]
                    logger.info(f"[DISAMBIGUATION] Resolved selection by number {selection_num}: loan_product={selected.get('loan_product')}, charge_context={selected.get('charge_context')}")
                    return selected
            except (ValueError, IndexError):
                pass  # Invalid number, try keyword matching
        
        # Check for keyword matching in loan product names and charge contexts
        for option in options:
            loan_product = option.get("loan_product", "").lower()
            loan_product_name = option.get("loan_product_name", "").lower()
            card_product = option.get("card_product", "").lower()
            card_product_name = option.get("card_product_name", "").lower()
            charge_context = option.get("charge_context", "").lower()
            charge_description = option.get("charge_description", "").lower()
            # NOTE: answer_text is NOT used for keyword matching (contains common words like "fee", "bdt", "per")
            
            # Check if query contains loan product keywords
            keywords_to_check = []
            if loan_product:
                keywords_to_check.append(loan_product)
            if loan_product_name:
                keywords_to_check.append(loan_product_name)
                # Also check individual words from product name (filter stopwords and short tokens)
                for word in loan_product_name.split():
                    if len(word) >= MIN_TOKEN_LENGTH and word not in STOPWORDS:
                        keywords_to_check.append(word)
            if card_product:
                keywords_to_check.append(card_product)
                # Filter stopwords and short tokens from card product words
                for word in card_product.split():
                    if len(word) >= MIN_TOKEN_LENGTH and word not in STOPWORDS:
                        keywords_to_check.append(word)
            if card_product_name:
                keywords_to_check.append(card_product_name)
                # Filter stopwords and short tokens from card product name words
                for word in card_product_name.split():
                    if len(word) >= MIN_TOKEN_LENGTH and word not in STOPWORDS:
                        keywords_to_check.append(word)
            if charge_description:
                keywords_to_check.append(charge_description)
                # Filter stopwords and short tokens from charge description words
                for word in charge_description.split():
                    if len(word) >= MIN_TOKEN_LENGTH and word not in STOPWORDS:
                        keywords_to_check.append(word)
            # REMOVED: answer_text.split() - answer_text contains common words that cause false matches
            
            # Check for common loan product keyword mappings
            loan_product_keywords = {
                "fast cash": ["fast cash", "fastcash"],
                "fast loan": ["fast loan", "fastloan"],
                "education loan": ["education loan", "edu loan", "education"],
                "home loan": ["home loan", "homeloan"],
                "auto loan": ["auto loan", "car loan", "auto", "car"],
                "executive loan": ["executive loan", "executive", "personal loan"],
            }
            
            # Add mapped keywords
            for key, keywords in loan_product_keywords.items():
                if key in loan_product or key in loan_product_name:
                    keywords_to_check.extend(keywords)
            
            # Check for charge_context keywords (if this is a second-level disambiguation)
            if charge_context:
                context_keywords = {
                    "on_limit": ["on limit", "on loan amount", "loan amount"],
                    "on_enhanced_amount": ["enhanced", "enhancement", "enhance", "enhanced amount"],
                    "on_reduced_amount": ["reduced", "reduction", "reduce", "reduced amount"],
                    "general": ["general", "normal", "standard"]
                }
                if charge_context in context_keywords:
                    keywords_to_check.extend(context_keywords[charge_context])
            
            # Check if any keyword matches
            for keyword in keywords_to_check:
                if keyword and keyword in query_lower:
                    logger.info(f"[DISAMBIGUATION] Resolved selection by keyword '{keyword}': loan_product={option.get('loan_product')}, charge_context={option.get('charge_context')}")
                    return option
        
        logger.info(f"[DISAMBIGUATION] Could not resolve selection from query: '{query}'")
        return None
    
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
        # Import fee engine client
        try:
            from app.services.fee_engine_client import FeeEngineClient
            fee_client = FeeEngineClient()
            
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
            if fee_result and fee_result.get("status") == "NEEDS_DISAMBIGUATION" and "options" in fee_result:
                options = fee_result.get("options") or []
                charge_type = fee_result.get("charge_type") or ""

                lines = [
                    self.OFFICIAL_CARD_RATES_HEADER,
                    self.FEE_ENGINE_SOURCE,
                    "",
                    "To answer, please specify the card product:",
                ]
                for i, opt in enumerate(options, start=1):
                    label = opt.get("card_product_name") or opt.get("card_product") or opt.get("label") or str(opt)
                    lines.append(f"{i}. {label}")
                lines.append("")
                lines.append("Reply with the number (e.g., 1) or the product name.")
                prompt = "\n".join(lines)

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
            
            # Handle retail asset charges (status = "FOUND")
            if fee_result and fee_result.get("status") == "FOUND" and "charges" in fee_result:
                formatted = fee_client.format_fee_response(fee_result, query=query)
                context = f"{self.OFFICIAL_RETAIL_ASSET_HEADER}\n{formatted}\n\nThis information is from the Retail Asset Charges Schedule and is authoritative."
                logger.info(f"[FEE_ENGINE] Retail asset charge found and formatted for query: '{query}'")
                return context
            
            # Handle Skybanking fees (status = "FOUND")
            if fee_result and fee_result.get("status") == "FOUND" and "fees" in fee_result:
                formatted = fee_client.format_fee_response(fee_result, query=query)
                context = f"{self.OFFICIAL_SKYBANKING_HEADER}\n{'='*70}\n{formatted}\n{'='*70}\n\nThis information is from the Skybanking Fees Schedule and is authoritative."
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
                if product_line == "RETAIL_ASSETS":
                    # Format the retail asset NO_RULE_FOUND response using format_fee_response
                    formatted = fee_client.format_fee_response(fee_result, query=query)
                    context = f"OFFICIAL RETAIL ASSET CHARGES INFORMATION\n{formatted if formatted else 'The requested retail asset charge information is not found in the Retail Asset Charges Schedule.'}\n\nPlease verify the loan product details and try again, or contact Eastern Bank PLC. directly for this specific detail."
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
                
                # Return deterministic message for unknown statuses (card fees only)
                lines = [
                    "=" * 70,
                    self.OFFICIAL_CARD_RATES_HEADER,
                    self.FEE_ENGINE_SOURCE,
                    "=" * 70,
                    "",
                    f"The requested fee information could not be retrieved (status: {status}).",
                    "",
                    "The requested fee information is not available in the Card Charges and Fees Schedule (effective 01 Jan 2026).",
                    "",
                    "Please verify the card details and try again, or contact the bank for assistance.",
                    "",
                    "=" * 70,
                    ""
                ]
                return "\n".join(lines)
        except ImportError:
            logger.warning("[FEE_ENGINE] FeeEngineClient not available")
            # Return deterministic not-found message instead of falling back
            lines = [
                "=" * 70,
                self.OFFICIAL_CARD_RATES_HEADER,
                self.FEE_ENGINE_SOURCE,
                "=" * 70,
                "",
                "The fee engine service is not available.",
                "",
                "The requested fee information is not available in the Card Charges and Fees Schedule (effective 01 Jan 2026).",
                "",
                "Please contact the bank for assistance.",
                "",
                "=" * 70,
                ""
            ]
            return "\n".join(lines)
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
            lines = [
                "=" * 70,
                self.OFFICIAL_CARD_RATES_HEADER,
                self.FEE_ENGINE_SOURCE,
                "=" * 70,
                "",
                "An error occurred while retrieving fee information.",
                "",
                "The requested fee information is not available in the Card Charges and Fees Schedule (effective 01 Jan 2026).",
                "",
                "Please verify the card details and try again, or contact the bank for assistance.",
                "",
                "=" * 70,
                ""
            ]
            return "\n".join(lines)
        
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
        lines = [
            "=" * 70,
            self.OFFICIAL_CARD_RATES_HEADER,
                            self.FEE_ENGINE_SOURCE,
            "=" * 70,
            "",
            "The fee engine service returned no result.",
            "",
            "The requested fee information is not available in the Card Charges and Fees Schedule (effective 01 Jan 2026).",
            "",
            "Please verify the card details and try again, or contact the bank for assistance.",
            "",
            "=" * 70,
            ""
        ]
        return "\n".join(lines)
    
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
        
        # PRIORITY 1: If we have a full response (only_need_context=False), use it directly
        # This is the most complete and formatted answer from LightRAG
        if "response" in lightrag_response and lightrag_response.get("response"):
            response_text = lightrag_response["response"]
            # If response is a complete answer (not just a prompt template), use it
            # BUT: If filtering financial docs, check if response mentions financial content
            if response_text and not response_text.strip().startswith("---Role---"):
                # For organizational overview queries, skip response if it's clearly financial
                if filter_financial_docs:
                    response_lower = response_text.lower()
                    # Check if response is heavily financial-focused
                    financial_indicators = ['annual report', 'financial statement', 'balance sheet', 
                                          'income statement', 'cash flow', 'audit', 'subsidiary',
                                          'fair value', 'valuation', 'board of directors report']
                    if any(indicator in response_lower for indicator in financial_indicators):
                        logger.info(f"[FILTER] Excluding response text (contains financial content)")
                        # Don't add response, fall through to chunks
                    else:
                        context_parts.append("Source Data:")
                        context_parts.append(response_text)
                else:
                    context_parts.append("Source Data:")
                    context_parts.append(response_text)
                # Still include entities/relationships/chunks if available for additional context
            else:
                # Response is a prompt template, fall through to extract structured data
                pass
        
        # PRIORITY 2: Extract structured data (entities, relationships, chunks)
        # This is used when only_need_context=True or when response is not available
        
        # Extract entities from knowledge graph
        if "entities" in lightrag_response:
            entities = lightrag_response.get("entities", [])
            if entities:
                if not context_parts:  # Only add header if we don't have response text
                    context_parts.append("Entities Data From Knowledge Graph(KG):")
                else:
                    context_parts.append("\n\nEntities Data From Knowledge Graph(KG):")
                for entity in entities[:5]:  # Limit to top 5
                    if isinstance(entity, dict):
                        name = entity.get("name", "")
                        desc = entity.get("description", "")
                        if name or desc:
                            context_parts.append(f"- {name}: {desc}")
        
        # Extract relationships
        if "relationships" in lightrag_response:
            relationships = lightrag_response.get("relationships", [])
            if relationships:
                if not context_parts:
                    context_parts.append("Relationships Data From Knowledge Graph(KG):")
                else:
                    context_parts.append("\n\nRelationships Data From Knowledge Graph(KG):")
                for rel in relationships[:5]:  # Limit to top 5
                    if isinstance(rel, dict):
                        source = rel.get("source", "")
                        relation = rel.get("relation", "")
                        target = rel.get("target", "")
                        if source and relation and target:
                            context_parts.append(f"- {source} → {relation} → {target}")
        
        # Extract document chunks and their sources
        if "chunks" in lightrag_response:
            chunks = lightrag_response.get("chunks", [])
            if chunks:
                if not context_parts:
                    context_parts.append("Original Texts From Document Chunks(DC):")
                else:
                    context_parts.append("\n\nOriginal Texts From Document Chunks(DC):")
                for chunk in chunks[:10]:  # Limit to top 10
                    if isinstance(chunk, dict):
                        # Extract source from chunk metadata first (for filtering)
                        # Try multiple possible field names for source
                        source = (
                            chunk.get("source") or 
                            chunk.get("file_name") or 
                            chunk.get("document") or 
                            chunk.get("file") or
                            chunk.get("doc_name") or
                            ""
                        )
                        
                        # CRITICAL: Filter out financial documents if requested (for org overview queries)
                        if filter_financial_docs and source and self._is_financial_document(source):
                            excluded_count += 1
                            logger.info(f"[FILTER] Excluding chunk from financial document: {source}")
                            continue  # Skip this chunk
                        
                        text = chunk.get("text", chunk.get("content", ""))
                        if text:
                            context_parts.append(f"- {text}")
                        
                        # Add source to sources list (only if not filtered)
                        if source and source not in seen_sources:
                            seen_sources.add(source)
                            sources.append(source)
                            logger.info(f"[SOURCES] Extracted source from chunk: {source}")
                
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
                    source = ref.get("source", ref.get("file_name", ref.get("document", "")))
                    # Filter financial documents
                    if filter_financial_docs and self._is_financial_document(source):
                        logger.info(f"[FILTER] Excluding reference from financial document: {source}")
                        continue
                    if source and source not in seen_sources:
                        seen_sources.add(source)
                        sources.append(source)
        
        # Final fallback: use response text even if it looks like a prompt
        if not context_parts and "response" in lightrag_response:
            context_parts.append(lightrag_response["response"])
        
        context_str = "\n".join(context_parts) if context_parts else ""
        return context_str, sources
    
    def _improve_query_for_lightrag(self, query: str, is_card_rates_query: bool = False) -> str:
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
        
        cache_key = get_cache_key(improved_query, kb)
        
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
            response = await self.lightrag_client.query(
                query=improved_query,
                knowledge_base=kb,
                mode="mix",  # Use 'mix' mode (works better than 'hybrid')
                top_k=8,  # KG Top K: 8 (conservative increase from 5 for better coverage)
                chunk_top_k=10,  # Chunk Top K: 10 (conservative increase from 5 for better recall)
                include_references=True,
                only_need_context=False,  # Get full response, not just context
                # Removed max_entity_tokens, max_relation_tokens, max_total_tokens, enable_rerank
                # These parameters were causing the query to miss relevant information
                # LightRAG will use its internal defaults which work better
            )
            
            # Cache the response (using improved query for cache key)
            await self.redis_cache.set(cache_key, response)
            
            context, sources = self._format_lightrag_context(response, filter_financial_docs=filter_financial_docs)
            
            # Low-confidence check: if context is too short, it might not be reliable
            # For banking, it's better to return empty and let the chatbot handle gracefully
            # rather than risk providing incorrect information
            if context and len(context) < 100:
                logger.warning(f"LightRAG returned very short context ({len(context)} chars) - may not be reliable")
                # Return empty to trigger fallback behavior
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
        """Build messages for OpenAI API"""
        messages = [
            {"role": "system", "content": self.system_message}
        ]
        
        # Add conversation history
        for msg in conversation_history:
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
            prompt_addons = self._build_prompt_addons(query, context, conversation_history)
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
        client_ip: Optional[str] = None
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
        # Derive stable conversation key (FIX #1: Session continuity)
        conversation_key = self._get_conversation_key(session_id, client_ip)
        # Use conversation_key for all disambiguation state operations
        # Store original session_id for memory/history (if provided)
        effective_session_id = session_id if session_id else conversation_key
        # Normalize session_id for the remainder of this request.
        # Many downstream calls assume a non-null session_id for state, headers, and persistence.
        session_id = effective_session_id
        
        # ===== CRITICAL: Check for pending disambiguation state (BEFORE other processing) =====
        # This MUST happen before any other routing to ensure disambiguation state is always checked first
        pending_disambiguation = await self._get_disambiguation_state_any(conversation_key)
        if pending_disambiguation:
            result = await self._handle_disambiguation_resolution(
                query=query,
                conversation_key=conversation_key,
                session_id=effective_session_id,
                pending_disambiguation=pending_disambiguation
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
        
        # Check if user is already in lead collection flow
        # DISABLED: Lead generation is disabled via ENABLE_LEAD_GENERATION setting
        # Code preserved for future use - set ENABLE_LEAD_GENERATION=True in .env to re-enable
        if settings.ENABLE_LEAD_GENERATION and LEADS_AVAILABLE:
            if session_id in self.lead_flows and self.lead_flows[session_id].state == ConversationState.LEAD_COLLECTING:
                response, is_complete = self._process_lead_collection(session_id, query)
                if is_complete:
                    self.lead_flows[session_id].state = ConversationState.NORMAL
                # Save to memory
                await self._persist_turn(session_id, query, response)
                yield response
                return
        
        # Check for lead intent FIRST (before other processing)
        # DISABLED: Lead generation is disabled via ENABLE_LEAD_GENERATION setting
        # Code preserved for future use - set ENABLE_LEAD_GENERATION=True in .env to re-enable
        if settings.ENABLE_LEAD_GENERATION and LEADS_AVAILABLE:
            lead_intent = self._detect_lead_intent(query)
            
            # If new lead intent detected, start lead collection
            if lead_intent:
                if session_id not in self.lead_flows:
                    self.lead_flows[session_id] = LeadFlowState()
                
                flow = self.lead_flows[session_id]
                flow.state = ConversationState.LEAD_COLLECTING
                flow.lead_type = lead_intent
                flow.questions = self._get_lead_questions(lead_intent)
                flow.current_question_index = 0
                
                # Start with first question
                first_question = flow.questions[0]["question"]
                # Save to memory
                await self._persist_turn(session_id, query, first_question)
                yield first_question
                return
        
        # Get conversation history
        db = get_db()
        memory = PostgresChatMemory(db=db)
        conversation_history = []
        try:
            if memory._available:
                history = memory.get_conversation_history(
                    session_id=session_id,
                    limit=settings.MAX_CONVERSATION_HISTORY
                )
                conversation_history = [
                    {"role": msg.role, "message": msg.message}
                    for msg in history
                ]
        finally:
            memory.close()
            if db:
                db.close()
        
        # ===== ROUTING DECISION LOGGING =====
        logger.info(f"[ROUTING] ===== Processing Query (STREAMING): '{query}' =====")
        logger.info(f"[ROUTING] CODE VERSION: Corporate customer routing fix v2.0 - includes 'in the case of' pattern")
        
        # ===== LOCATION QUERIES - ROUTE TO LOCATION SERVICE (HIGHEST PRIORITY) =====
        # Route location queries (branches, ATMs, CRMs, RTDMs, priority centers, head office) to location service
        # This MUST be checked BEFORE fee schedule queries to avoid misrouting priority center queries
        is_location_query = self._is_location_query(query)
        if is_location_query:
            logger.info(f"[LOCATION_SERVICE] ✓✓✓ LOCATION QUERY DETECTED: '{query}' → ROUTING TO LOCATION SERVICE (NO LightRAG, NO KB)")
            location_context = await self._get_location_context(query)
            sources = ["EBL Location Database (Normalized)"]
            
            # Use ONLY location service context - NO LightRAG, NO knowledge base
            combined_context = location_context
            logger.info(f"[LOCATION_SERVICE] Using EXCLUSIVE location service context: {len(location_context)} chars (LightRAG/KB explicitly skipped)")
            
            # Build messages with location context only
            messages = self._build_messages(query, combined_context, conversation_history)
            
            # Stream response from OpenAI with location data only
            full_response = ""
            try:
                max_response_tokens = min(settings.OPENAI_MAX_TOKENS, 2000)
                stream = await self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=messages,
                    temperature=settings.OPENAI_TEMPERATURE,
                    max_tokens=max_response_tokens,
                    stream=True
                )
                
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield content
            except Exception as e:
                logger.error(f"[LOCATION_SERVICE] Error generating response: {e}")
                error_msg = "I apologize, but I encountered an error while processing your location inquiry. Please try again."
                yield error_msg
                full_response = error_msg
            
            # Save to memory
            await self._persist_turn(session_id, query, full_response)
            
            return  # EXIT - do not proceed to LightRAG, phonebook, or any other routing
        
        # ===== CRITICAL: RETAIL ASSET FEE QUERIES - EXCLUSIVE FEE ENGINE ROUTING (HIGH PRIORITY) =====
        # Check for retail asset fee queries BEFORE card fee queries
        is_retail_asset_fee_query = self._is_retail_asset_fee_query(query)
        if is_retail_asset_fee_query:
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
            async for chunk in self._stream_text(fee_context):
                yield chunk
            
            # Save to memory
            await self._persist_turn(session_id, query, full_response, knowledge_base=None, client_ip=client_ip)
            
            return  # EXIT - do not proceed to other routing
        
        # ===== CRITICAL: SKYBANKING FEE QUERIES - EXCLUSIVE FEE ENGINE ROUTING (HIGH PRIORITY) =====
        # Check for Skybanking fee queries BEFORE card fee queries
        is_skybanking_fee_query = self._is_skybanking_fee_query(query)
        if is_skybanking_fee_query:
            logger.info(f"[FEE_ENGINE] ✓✓✓ SKYBANKING FEE QUERY DETECTED: '{query}' → EXCLUSIVE ROUTING TO FEE ENGINE")
            fee_context = await self._get_card_rates_context(query, session_id=session_id)  # Pass session_id for disambiguation state storage
            sources = ["Skybanking Fees Schedule"]
            
            # ALWAYS return fee engine response, even if empty
            if not fee_context:
                fee_context = (
                    "=" * 70 + "\n"
                    f"{self.OFFICIAL_SKYBANKING_HEADER}\n"
                    "Source: Fee Engine (Skybanking Fees Schedule)\n"
                    "=" * 70 + "\n\n"
                    "The specific information about this Skybanking fee is not available in the current schedule. "
                    "Please verify the service details and try again, or contact Eastern Bank PLC. directly for this specific detail."
                )
            
            # Stream response in chunks
            full_response = fee_context
            async for chunk in self._stream_text(fee_context):
                yield chunk
            
            # Save to memory
            await self._persist_turn(session_id, query, full_response, knowledge_base=None, client_ip=client_ip)
            
            return  # EXIT - do not proceed to other routing
        
        # ===== CRITICAL: FEE SCHEDULE QUERIES - EXCLUSIVE FEE ENGINE ROUTING (HIGH PRIORITY) =====
        # MANDATORY: Fee queries MUST route to Fee Engine ONLY (authoritative source)
        # NO LightRAG fallback, NO knowledge base lookup, NO LLM guessing
        # This check happens AFTER location queries, retail asset queries, and Skybanking queries to avoid misrouting
        is_fee_schedule_query = self._is_fee_schedule_query(query)
        if is_fee_schedule_query:
            logger.info(f"[FEE_ENGINE] ✓✓✓ FEE SCHEDULE QUERY DETECTED (HIGHEST PRIORITY): '{query}' → EXCLUSIVE ROUTING TO FEE ENGINE (NO LightRAG, NO KB)")
            fee_context = await self._get_card_rates_context(query, session_id=session_id)
            sources = ["Card Charges and Fees Schedule (Effective from 01st January, 2026)"]
            
            # ALWAYS return fee engine response, even if empty
            # If no rule found → return deterministic "not found in schedule" response
            if not fee_context:
                logger.warning(f"[FEE_ENGINE] Fee engine returned empty - returning deterministic not-found message")
                fee_context = (
                    "=" * 70 + "\n"
                    f"{self.OFFICIAL_CARD_RATES_HEADER}\n"
                    f"{self.FEE_ENGINE_SOURCE}\n"
                    "=" * 70 + "\n\n"
                    "The requested fee information is not found in the Card Charges and Fees Schedule (effective 01 Jan 2026).\n"
                    "Please verify the card details and try again.\n\n"
                    "=" * 70
                )
            
            # Use ONLY fee engine context - NO LightRAG, NO knowledge base
            combined_context = fee_context
            logger.info(f"[FEE_ENGINE] Using EXCLUSIVE fee engine context: {len(fee_context)} chars (LightRAG/KB explicitly skipped)")

            # Anti-hallucination hard guard:
            # Stream the fee engine output directly (NO OpenAI call, NO paraphrasing).
            full_response = combined_context
            async for chunk in self._stream_text(full_response):
                yield chunk

            # Save to memory
            await self._persist_turn(session_id, query, full_response, knowledge_base=None, client_ip=client_ip)

            return  # EXIT - do not proceed to LightRAG, phonebook, or any other routing
        
        # CRITICAL: Check for phonebook/employee/contact queries FIRST (before other routing)
        # These should ALWAYS go to phonebook, never LightRAG
        is_small_talk = self._is_small_talk(query)
        is_contact_query = self._is_contact_info_query(query)
        is_phonebook_query = self._is_phonebook_query(query)
        is_employee_query = self._is_employee_query(query)
        
        # If it's a phonebook/employee/contact query, route to phonebook immediately
        if (is_phonebook_query or is_contact_query or is_employee_query) and not is_small_talk and PHONEBOOK_DB_AVAILABLE:
            logger.info(f"[ROUTING] ✓ Query detected as phonebook/contact/employee → ROUTING TO PHONEBOOK (NOT LightRAG)")
            should_check_phonebook = True
        else:
            # CRITICAL: Check for organizational overview queries (these need special filtering)
            is_org_overview_query = self._is_organizational_overview_query(query)
            
            # CRITICAL: Check for banking product/compliance/management/financial/milestone/user document queries
            # These should go to LightRAG, NOT phonebook
            is_banking_product_query = self._is_banking_product_query(query)
            is_compliance_query = self._is_compliance_query(query)
            is_management_query = self._is_management_query(query)
            is_financial_query = self._is_financial_report_query(query)
            is_milestone_query = self._is_milestone_query(query)
            is_user_doc_query = self._is_user_document_query(query)
            
            # Log all routing checks
            logger.info(f"[ROUTING] Routing checks - org_overview={is_org_overview_query}, banking_product={is_banking_product_query}, compliance={is_compliance_query}, management={is_management_query}, financial={is_financial_query}, milestone={is_milestone_query}, user_doc={is_user_doc_query}")
            
            # If it's an organizational overview query, route to LightRAG but with special filtering instructions
            # If it's a banking product/compliance/management/financial/milestone/user document query, skip phonebook and go to LightRAG
            if is_org_overview_query or is_banking_product_query or is_compliance_query or is_management_query or is_financial_query or is_milestone_query or is_user_doc_query:
                routing_type = []
                if is_org_overview_query:
                    routing_type.append("org_overview")
                if is_banking_product_query:
                    routing_type.append("banking_product")
                if is_compliance_query:
                    routing_type.append("compliance")
                if is_management_query:
                    routing_type.append("management")
                if is_financial_query:
                    routing_type.append("financial")
                if is_milestone_query:
                    routing_type.append("milestone")
                if is_user_doc_query:
                    routing_type.append("user_doc")
                logger.info(f"[ROUTING] ✓ Query detected as special ({', '.join(routing_type)}) → ROUTING TO LIGHTRAG (skipping phonebook)")
                should_check_phonebook = False
            elif is_small_talk:
                logger.info(f"[ROUTING] ✓ Query detected as small talk → ROUTING TO OPENAI (no LightRAG)")
                should_check_phonebook = False
            else:
                logger.info(f"[ROUTING] ✓ Query not matched to special categories → ROUTING TO LIGHTRAG (default)")
                should_check_phonebook = False
        
        logger.info(f"[ROUTING] Final decision - will_check_phonebook={should_check_phonebook}, will_use_lightrag={not should_check_phonebook and not is_small_talk}")
        
        # Check phonebook FIRST for contact queries (before LightRAG)
        if should_check_phonebook:
            try:
                phonebook_db = get_phonebook_db()
                
                # Extract search term from query
                # For role-based queries like "branch manager of X", preserve the full context
                import re
                query_lower = query.lower()
                
                # Check if it's a role + location query (e.g., "branch manager of Gulshan")
                role_location_pattern = r'(branch\s+)?manager\s+(of|at)\s+(.+?)(?:\s+branch)?$'
                match = re.search(role_location_pattern, query_lower)
                if match:
                    # Extract location/branch name
                    location = match.group(3).strip()
                    role = match.group(1) + "manager" if match.group(1) else "manager"
                    search_term = f"{role} {location}"
                    logger.info(f"[PHONEBOOK] Extracted role+location query: '{search_term}' from '{query}'")
                else:
                    # First, check if query starts with "find", "search", "lookup", etc. and extract the term after it
                    find_search_pattern = r'^(find|search|lookup|who is|contact|info about|get)\s+(.+)$'
                    match = re.search(find_search_pattern, query_lower, re.IGNORECASE)
                    if match:
                        # Extract the search term after the prefix
                        search_term = match.group(2).strip()
                        logger.info(f"[PHONEBOOK] Extracted search term '{search_term}' from query '{query}' (removed prefix '{match.group(1)}')")
                    else:
                        # Handle patterns like "phone number of X", "contact info for X", "email of X"
                        # Extract employee ID/name after "of", "for", etc.
                        # Pattern: (contact word) (optional "number") (of/for/about) (employee ID/name)
                        of_for_patterns = [
                            r'\b(phone|contact|email|mobile|telephone)\s+number\s+(?:of|for|about)\s+(.+)$',  # "phone number of X"
                            r'\b(phone|contact|email|mobile|telephone)\s+(?:of|for|about)\s+(.+)$',  # "phone of X"
                            r'\b(contact|info|information|details?)\s+(?:info|information|details?)?\s+(?:of|for|about)\s+(.+)$',  # "contact info for X"
                        ]
                        match = None
                        for pattern in of_for_patterns:
                            match = re.search(pattern, query_lower, re.IGNORECASE)
                            if match:
                                search_term = match.group(2).strip() if len(match.groups()) >= 2 else match.group(1).strip()
                                logger.info(f"[PHONEBOOK] Extracted search term '{search_term}' from query '{query}' (removed contact info prefix)")
                                break
                        if not match:
                            # Standard extraction: remove common words but preserve role and location terms
                            search_term = re.sub(
                                r'\b(phone|contact|number|email|address|mobile|telephone|who\s+is|what\s+is|tell\s+me|the|is|are|was|were|of|for|about)\b', 
                                '', 
                                query, 
                                flags=re.IGNORECASE
                            ).strip()
                    # Clean up multiple spaces and remove leading/trailing "of", "for", "about"
                    search_term = re.sub(r'\s+', ' ', search_term).strip()
                    search_term = re.sub(r'^(of|for|about)\s+', '', search_term, flags=re.IGNORECASE).strip()
                    search_term = re.sub(r'\s+(of|for|about)$', '', search_term, flags=re.IGNORECASE).strip()
                    
                    # Remove bank name suffixes (e.g., "of EBL", "of Eastern Bank", "at EBL")
                    # This helps when queries include "head of Retail & SME Banking Division of EBL"
                    search_term = re.sub(r'\s+(of|at|in)\s+(ebl|eastern\s+bank|eastern\s+bank\s+plc)[\s.]*$', '', search_term, flags=re.IGNORECASE).strip()
                    
                    # Remove "Division" if it appears anywhere (e.g., "Retail & SME Banking Division head" -> "Retail & SME Banking head")
                    # This helps match designations that don't include "Division"
                    # Remove "division" as a whole word (not part of other words)
                    original_search_term = search_term
                    search_term = re.sub(r'\bdivision\b', '', search_term, flags=re.IGNORECASE).strip()
                    # Clean up multiple spaces that might result
                    search_term = re.sub(r'\s+', ' ', search_term).strip()
                    if original_search_term != search_term:
                        logger.info(f"[PHONEBOOK] Removed 'division' from search term: '{original_search_term}' -> '{search_term}'")
                    
                    # If search term looks like a division/department name without a role, try adding "head"
                    # This handles queries like "Who is Retail & SME Banking Division?" -> "Retail & SME Banking head"
                    division_dept_keywords = ['banking', 'division', 'department', 'unit', 'section', 'retail', 'sme', 'corporate', 'operations', 'finance', 'hr', 'ict', 'it']
                    role_keywords = ['head', 'manager', 'director', 'officer', 'executive', 'president', 'ceo', 'cfo', 'chief', 'senior', 'assistant']
                    search_term_lower = search_term.lower()
                    has_division_keyword = any(keyword in search_term_lower for keyword in division_dept_keywords)
                    has_role_keyword = any(keyword in search_term_lower for keyword in role_keywords)
                    
                    # If it looks like a division/department name but no role mentioned, try with "head"
                    if has_division_keyword and not has_role_keyword:
                        search_term_with_head = f"{search_term} head"
                        logger.info(f"[PHONEBOOK] Query looks like division/department without role, trying with 'head': '{search_term_with_head}'")
                        # Try search with "head" added
                        results = phonebook_db.smart_search(search_term_with_head, limit=5)
                        if results:
                            logger.info(f"[OK] Found {len(results)} results with 'head' added")
                        else:
                            # Also try department search as fallback
                            logger.info(f"[PHONEBOOK] No results with 'head', trying department search for: '{search_term}'")
                            dept_results = phonebook_db.search_by_department(search_term, limit=5)
                            if dept_results:
                                results = dept_results
                                logger.info(f"[OK] Found {len(dept_results)} results via department search")
                            else:
                                # Try original search term as fallback
                                results = phonebook_db.smart_search(search_term, limit=5)
                    else:
                        # Try multiple search strategies
                        results = phonebook_db.smart_search(search_term, limit=5)
                
                # Final cleanup: Always remove "division" and bank name suffixes before searching
                # This ensures cleanup happens regardless of which code path was taken
                if search_term:
                    original_final = search_term
                    search_term = re.sub(r'\s+(of|at|in)\s+(ebl|eastern\s+bank|eastern\s+bank\s+plc)[\s.]*$', '', search_term, flags=re.IGNORECASE).strip()
                    search_term = re.sub(r'\bdivision\b', '', search_term, flags=re.IGNORECASE).strip()
                    search_term = re.sub(r'\s+', ' ', search_term).strip()
                    if original_final != search_term:
                        logger.info(f"[PHONEBOOK] Final cleanup: '{original_final}' -> '{search_term}'")
                        # If we cleaned the term and haven't searched yet, try searching with cleaned term
                        if not results:
                            results = phonebook_db.smart_search(search_term, limit=5)
                
                if results:
                    logger.info(f"[OK] Found {len(results)} results in phonebook for: {search_term}")
                    
                    # Stream response in chunks for better performance
                    full_response = ""
                    
                    if len(results) == 1:
                        # Single result - detailed format (stream in chunks)
                        contact_info = phonebook_db.format_contact_info(results[0])
                        # Stream in sentence chunks
                        sentences = contact_info.split('\n')
                        for sentence in sentences:
                            if sentence.strip():
                                chunk = sentence + '\n'
                                full_response += chunk
                                yield chunk
                        # Add source
                        source_chunk = "\n\n(Source: Phone Book Database)"
                        full_response += source_chunk
                        yield source_chunk
                    else:
                        # Multiple results - list format (stream each result as it's formatted)
                        for i, emp in enumerate(results[:5], 1):
                            # Stream each employee entry as a chunk
                            entry_chunk = f"{i}. {emp['full_name']}\n"
                            full_response += entry_chunk
                            yield entry_chunk
                            
                            if emp.get('designation'):
                                chunk = f"   Designation: {emp['designation']}\n"
                                full_response += chunk
                                yield chunk
                            if emp.get('department'):
                                chunk = f"   Department: {emp['department']}\n"
                                full_response += chunk
                                yield chunk
                            if emp.get('email'):
                                chunk = f"   Email: {emp['email']}\n"
                                full_response += chunk
                                yield chunk
                            if emp.get('employee_id'):
                                chunk = f"   Employee ID: {emp['employee_id']}\n"
                                full_response += chunk
                                yield chunk
                            if emp.get('mobile'):
                                chunk = f"   Mobile: {emp['mobile']}\n"
                                full_response += chunk
                                yield chunk
                            if emp.get('ip_phone'):
                                chunk = f"   IP Phone: {emp['ip_phone']}\n"
                                full_response += chunk
                                yield chunk
                            
                            # Empty line between entries
                            full_response += "\n"
                            yield "\n"
                        
                        # Stream summary
                        total_count = phonebook_db.count_search_results(search_term)
                        summary_chunk = f"We found {total_count} matching contact(s) in total. Showing only the top 5 results.\n\n"
                        full_response += summary_chunk
                        yield summary_chunk
                        
                        if total_count > 5:
                            narrow_chunk = "Please provide more details to narrow down the search.\n\n"
                            full_response += narrow_chunk
                            yield narrow_chunk
                        
                        source_chunk = "(Source: Phone Book Database)"
                        full_response += source_chunk
                        yield source_chunk
                    
                    # Save to memory
                    await self._persist_turn(session_id, query, full_response, knowledge_base=None, client_ip=client_ip)
                    
                    return  # DO NOT query LightRAG for contact queries
                    
                else:
                    # No results in phonebook - return helpful message (DO NOT use LightRAG)
                    logger.info(f"[INFO] No results in phonebook for '{search_term}' (contact query - NOT using LightRAG)")
                    
                    # Stream response in chunks
                    chunks = [
                        f"I couldn't find any contact information for '{search_term}' in the employee directory. ",
                        "Please try:\n",
                        "- Providing the full name\n",
                        "- Using the employee ID\n",
                        "- Specifying the department or designation\n",
                        "\n(Source: Phone Book Database)"
                    ]
                    
                    full_response = ""
                    for chunk in chunks:
                        full_response += chunk
                        yield chunk
                    
                    # Save to memory
                    await self._persist_turn(session_id, query, full_response, knowledge_base=None, client_ip=client_ip)
                    
                    return  # DO NOT query LightRAG for contact queries
                    
            except Exception as e:
                # For contact queries, even if phonebook has an error, don't use LightRAG
                logger.error(f"[ERROR] Phonebook error for contact query (NOT using LightRAG): {e}")
                
                # Stream error response in chunks
                chunks = [
                    "I'm having trouble accessing the employee directory right now. ",
                    "Please try again in a moment, or contact support for assistance.",
                    "\n\n(Source: Phone Book Database)"
                ]
                
                full_response = ""
                for chunk in chunks:
                    full_response += chunk
                    yield chunk
                
                # Save to memory
                await self._persist_turn(session_id, query, full_response, knowledge_base=None)
                
                return  # DO NOT query LightRAG for contact queries
        
        # Determine if we need LightRAG context (only for non-contact queries)
        context = ""
        sources = []
        card_rates_context = ""
        is_card_rates_query = False  # Initialize to avoid UnboundLocalError
        
        if not is_small_talk:
            # Check for policy queries and validate required entities
            if is_compliance_query:
                has_entities, clarification = self._check_policy_entities(query)
                if not has_entities and clarification:
                    logger.info(f"[POLICY] Policy query missing required entities, asking for clarification")
                    # Save to memory
                    await self._persist_turn(session_id, query, clarification, knowledge_base=None, client_ip=client_ip)
                    
                    # Stream clarification question
                    for char in clarification:
                        yield char
                    return  # Don't query LightRAG if entities are missing
            
            # REMOVED: Old fallback path for fee queries - fee queries are now handled at the top of the function
            # Fee schedule queries are handled at the top of process_chat() and process_chat_sync()
            # and exit immediately, so this code path should never be reached for fee queries
            # Initialize variables for non-fee queries
            is_card_rates_query = False
            card_rates_context = None
            
            # For non-fee queries, use LightRAG as normal
            # Smart routing: determine which knowledge base to use based on query content
            # This prevents confusion between financial reports and user documents
            if knowledge_base is None:
                knowledge_base = self._get_knowledge_base(query)
            
            logger.info(f"[ROUTING] Calling LightRAG with knowledge_base='{knowledge_base}' for query: '{query[:100]}'")
            # CRITICAL: Filter financial documents for organizational overview queries
            filter_financial = self._is_organizational_overview_query(query)
            context, lightrag_sources = await self._get_lightrag_context(query, knowledge_base, filter_financial_docs=filter_financial)
            sources.extend(lightrag_sources)  # Add LightRAG sources
            if context:
                logger.info(f"[ROUTING] LightRAG returned context (length: {len(context)} chars, sources: {len(lightrag_sources)}, filtered_financial={filter_financial})")
            else:
                logger.warning(f"[ROUTING] LightRAG returned empty context")
            
            # If no sources found but we have context, add knowledge base name as fallback source
            if not sources and context and knowledge_base:
                sources.append(f"Knowledge Base: {knowledge_base}")
                logger.info(f"[SOURCES] Added knowledge base name as fallback source: {knowledge_base}")
        
        # Combine card rates context (if any) with LightRAG context
        # CRITICAL: For card rates queries, use ONLY card rates context (never LightRAG)
        combined_context = ""
        if is_card_rates_query:
            # For card rates queries, use ONLY fee engine data (never LightRAG)
            if card_rates_context:
                combined_context = card_rates_context
                logger.info(f"[CARD_RATES] Using ONLY card rates context: {len(card_rates_context)} chars (LightRAG skipped)")
            else:
                # This should not happen if _get_card_rates_context is updated correctly
                # But handle gracefully with a not-found message
                combined_context = (
                    "=" * 70 + "\n"
                    f"{self.OFFICIAL_CARD_RATES_HEADER}\n"
                    f"{self.FEE_ENGINE_SOURCE}\n"
                    "=" * 70 + "\n\n"
                    "The requested fee information is not found in the Card Charges and Fees Schedule (effective 01 Jan 2026).\n"
                    "Please verify the card details and try again.\n\n"
                    "=" * 70
                )
                logger.warning(f"[CARD_RATES] No context available from fee engine - using not-found message")
        elif card_rates_context and context:
            # For non-card-rates queries, combine both if available
            combined_context = f"{card_rates_context}\n\n{context}"
            logger.info(f"[CARD_RATES] Combined context: card_rates={len(card_rates_context)} chars, lightrag={len(context)} chars")
        elif card_rates_context:
            combined_context = card_rates_context
            logger.info(f"[CARD_RATES] Using only card rates context: {len(card_rates_context)} chars")
        else:
            combined_context = context
        
        # Build messages
        messages = self._build_messages(query, combined_context, conversation_history)

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
                model=settings.OPENAI_MODEL,
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
                        # Fix currency symbols if needed (use combined_context if available)
                        if hasattr(self, '_last_combined_context'):
                            cleaned_content = self._fix_currency_symbols(cleaned_content, self._last_combined_context)
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
        await self._persist_turn(session_id, query, full_response, knowledge_base=knowledge_base, client_ip=client_ip)
    
    async def process_chat_sync(
        self,
        query: str,
        session_id: Optional[str] = None,
        knowledge_base: Optional[str] = None,
        client_ip: Optional[str] = None
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
        # Derive stable conversation key (FIX #1: Session continuity)
        conversation_key = self._get_conversation_key(session_id, client_ip)
        # Use conversation_key for all disambiguation state operations
        # Store original session_id for memory/history (if provided)
        effective_session_id = session_id if session_id else conversation_key
        # Normalize session_id for the remainder of this request.
        # This prevents returning/using a None session_id when callers omit it.
        session_id = effective_session_id
        
        # ===== CRITICAL: Check for pending disambiguation state (BEFORE other processing) =====
        # This MUST happen before any other routing to ensure disambiguation state is always checked first
        pending_disambiguation = await self._get_disambiguation_state_any(conversation_key)
        if pending_disambiguation:
            result = await self._handle_disambiguation_resolution(
                query=query,
                conversation_key=conversation_key,
                session_id=effective_session_id,
                pending_disambiguation=pending_disambiguation
            )
            if result:
                return {
                    "response": result["response"],
                    "session_id": effective_session_id,
                    "sources": result.get("sources", []),
                }
        
        # Get conversation history
        db = get_db()
        memory = PostgresChatMemory(db=db)
        conversation_history = []
        try:
            if memory._available:
                history = memory.get_conversation_history(
                    session_id=session_id,
                    limit=settings.MAX_CONVERSATION_HISTORY
                )
                conversation_history = [
                    {"role": msg.role, "message": msg.message}
                    for msg in history
                ]
        finally:
            memory.close()
            if db:
                db.close()
        
        # ===== ROUTING DECISION LOGGING =====
        logger.info(f"[ROUTING] ===== Processing Query (SYNC): '{query}' =====")
        
        # ===== CRITICAL: RETAIL ASSET FEE QUERIES - EXCLUSIVE FEE ENGINE ROUTING (HIGH PRIORITY) =====
        # Check for retail asset fee queries BEFORE card fee queries
        is_retail_asset_fee_query = self._is_retail_asset_fee_query(query)
        if is_retail_asset_fee_query:
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
            await self._persist_turn(effective_session_id, query, response_text, knowledge_base=None, client_ip=client_ip)

            return {
                "response": response_text,
                "session_id": effective_session_id,
                "sources": sources
            }  # EXIT - do not proceed to other routing
        
        # ===== CRITICAL: SKYBANKING FEE QUERIES - EXCLUSIVE FEE ENGINE ROUTING (HIGH PRIORITY) =====
        # Check for Skybanking fee queries BEFORE card fee queries
        is_skybanking_fee_query = self._is_skybanking_fee_query(query)
        if is_skybanking_fee_query:
            logger.info(f"[FEE_ENGINE] ✓✓✓ SKYBANKING FEE QUERY DETECTED: '{query}' → EXCLUSIVE ROUTING TO FEE ENGINE")
            fee_context = await self._get_card_rates_context(query, session_id=effective_session_id, conversation_key=conversation_key)  # FIX #1: Pass conversation_key for stable disambiguation state
            sources = ["Skybanking Fees Schedule"]
            
            # ALWAYS return fee engine response, even if empty
            if not fee_context:
                fee_context = (
                    "=" * 70 + "\n"
                    f"{self.OFFICIAL_SKYBANKING_HEADER}\n"
                    f"{self.FEE_ENGINE_SOURCE_SKYBANKING}\n"
                    "=" * 70 + "\n\n"
                    "The specific information about this Skybanking fee is not available in the current schedule. "
                    "Please verify the service details and try again, or contact Eastern Bank PLC. directly for this specific detail."
                )

            # Anti-hallucination hard guard (SYNC):
            # Return the fee engine output directly (NO OpenAI call, NO paraphrasing).
            response_text = fee_context
            
            # Save to memory
            await self._persist_turn(effective_session_id, query, response_text, knowledge_base=None, client_ip=client_ip)
            
            return {
                "response": response_text,
                "session_id": effective_session_id,
                "sources": sources
            }  # EXIT - do not proceed to other routing
        
        # ===== CRITICAL: FEE SCHEDULE QUERIES - EXCLUSIVE FEE ENGINE ROUTING =====
        # MANDATORY: Fee queries MUST route to Fee Engine ONLY (authoritative source)
        # NO LightRAG fallback, NO knowledge base lookup, NO LLM guessing
        # This check happens AFTER location queries, retail asset queries, and Skybanking queries to avoid misrouting
        is_fee_schedule_query = self._is_fee_schedule_query(query)
        if is_fee_schedule_query:
            logger.info(f"[FEE_ENGINE] ✓✓✓ FEE SCHEDULE QUERY DETECTED (HIGHEST PRIORITY): '{query}' → EXCLUSIVE ROUTING TO FEE ENGINE (NO LightRAG, NO KB)")
            fee_context = await self._get_card_rates_context(query, session_id=session_id)
            sources = ["Card Charges and Fees Schedule (Effective from 01st January, 2026)"]
            
            # ALWAYS return fee engine response, even if empty
            # If no rule found → return deterministic "not found in schedule" response
            if not fee_context:
                logger.warning(f"[FEE_ENGINE] Fee engine returned empty - returning deterministic not-found message")
                fee_context = (
                    "=" * 70 + "\n"
                    f"{self.OFFICIAL_CARD_RATES_HEADER}\n"
                    f"{self.FEE_ENGINE_SOURCE}\n"
                    "=" * 70 + "\n\n"
                    "The requested fee information is not found in the Card Charges and Fees Schedule (effective 01 Jan 2026).\n"
                    "Please verify the card details and try again.\n\n"
                    "=" * 70
                )
            
            # Use ONLY fee engine context - NO LightRAG, NO knowledge base
            combined_context = fee_context
            logger.info(f"[FEE_ENGINE] Using EXCLUSIVE fee engine context: {len(fee_context)} chars (LightRAG/KB explicitly skipped)")

            # Anti-hallucination hard guard:
            # Return the fee engine output directly (NO OpenAI call, NO paraphrasing).
            response_text = combined_context

            # Save to memory
            await self._persist_turn(session_id, query, response_text, knowledge_base=None, client_ip=client_ip)

            return {
                "response": response_text,
                "session_id": session_id,
                "sources": sources
            }  # EXIT - do not proceed to LightRAG, phonebook, or any other routing
        
        # ===== LOCATION QUERIES - ROUTE TO LOCATION SERVICE (HIGH PRIORITY) =====
        # Route location queries (branches, ATMs, CRMs, RTDMs, priority centers, head office) to location service
        is_location_query = self._is_location_query(query)
        if is_location_query:
            logger.info(f"[LOCATION_SERVICE] ✓✓✓ LOCATION QUERY DETECTED: '{query}' → ROUTING TO LOCATION SERVICE (NO LightRAG, NO KB)")
            location_context = await self._get_location_context(query)
            sources = ["EBL Location Database (Normalized)"]
            
            # Use ONLY location service context - NO LightRAG, NO knowledge base
            combined_context = location_context
            logger.info(f"[LOCATION_SERVICE] Using EXCLUSIVE location service context: {len(location_context)} chars (LightRAG/KB explicitly skipped)")
            
            # Build messages with location context only
            messages = self._build_messages(query, combined_context, conversation_history)

            # Generate response from OpenAI with location data only
            full_response = ""
            try:
                max_response_tokens = min(settings.OPENAI_MAX_TOKENS, 2000)
                response = await self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=messages,
                    temperature=settings.OPENAI_TEMPERATURE,
                    max_tokens=max_response_tokens
                )
                
                if response.choices and response.choices[0].message.content:
                    full_response = response.choices[0].message.content
            except Exception as e:
                logger.error(f"[LOCATION_SERVICE] Error generating response: {e}")
                full_response = "I apologize, but I encountered an error while processing your location inquiry. Please try again."

            # Save to memory
            await self._persist_turn(session_id, query, full_response, knowledge_base=None, client_ip=client_ip)
            
            return {
                "response": full_response,
                "sources": sources,
                "routing": "location_service"
            }  # EXIT - do not proceed to LightRAG, phonebook, or any other routing
        
        # CRITICAL: Check for phonebook/employee/contact queries FIRST (before other routing)
        # These should ALWAYS go to phonebook, never LightRAG
        is_small_talk = self._is_small_talk(query)
        is_contact_query = self._is_contact_info_query(query)
        is_phonebook_query = self._is_phonebook_query(query)
        is_employee_query = self._is_employee_query(query)
        
        # If it's a phonebook/employee/contact query, route to phonebook immediately
        if (is_phonebook_query or is_contact_query or is_employee_query) and not is_small_talk and PHONEBOOK_DB_AVAILABLE:
            logger.info(f"[ROUTING] ✓ Query detected as phonebook/contact/employee → ROUTING TO PHONEBOOK (NOT LightRAG)")
            should_check_phonebook = True
        else:
            # CRITICAL: Check for organizational overview queries (these need special filtering)
            is_org_overview_query = self._is_organizational_overview_query(query)
            
            # CRITICAL: Check for banking product/compliance/management/financial/milestone/user document queries
            # These should go to LightRAG, NOT phonebook
            is_banking_product_query = self._is_banking_product_query(query)
            is_compliance_query = self._is_compliance_query(query)
            is_management_query = self._is_management_query(query)
            is_financial_query = self._is_financial_report_query(query)
            is_milestone_query = self._is_milestone_query(query)
            is_user_doc_query = self._is_user_document_query(query)
            
            # Log all routing checks
            logger.info(f"[ROUTING] Routing checks - org_overview={is_org_overview_query}, banking_product={is_banking_product_query}, compliance={is_compliance_query}, management={is_management_query}, financial={is_financial_query}, milestone={is_milestone_query}, user_doc={is_user_doc_query}")
            
            # If it's an organizational overview query, route to LightRAG but with special filtering instructions
            # If it's a banking product/compliance/management/financial/milestone/user document query, skip phonebook and go to LightRAG
            if is_org_overview_query or is_banking_product_query or is_compliance_query or is_management_query or is_financial_query or is_milestone_query or is_user_doc_query:
                routing_type = []
                if is_org_overview_query:
                    routing_type.append("org_overview")
                if is_banking_product_query:
                    routing_type.append("banking_product")
                if is_compliance_query:
                    routing_type.append("compliance")
                if is_management_query:
                    routing_type.append("management")
                if is_financial_query:
                    routing_type.append("financial")
                if is_milestone_query:
                    routing_type.append("milestone")
                if is_user_doc_query:
                    routing_type.append("user_doc")
                logger.info(f"[ROUTING] ✓ Query detected as special ({', '.join(routing_type)}) → ROUTING TO LIGHTRAG (skipping phonebook)")
                should_check_phonebook = False
            elif is_small_talk:
                logger.info(f"[ROUTING] ✓ Query detected as small talk → ROUTING TO OPENAI (no LightRAG)")
                should_check_phonebook = False
            else:
                logger.info(f"[ROUTING] ✓ Query not matched to special categories → ROUTING TO LIGHTRAG (default)")
                should_check_phonebook = False
        
        logger.info(f"[ROUTING] Final decision - will_check_phonebook={should_check_phonebook}, will_use_lightrag={not should_check_phonebook and not is_small_talk}")
        
        # Check phonebook FIRST for contact queries (before LightRAG)
        if should_check_phonebook:
            try:
                phonebook_db = get_phonebook_db()
                
                # Extract search term from query
                # For role-based queries like "branch manager of X", preserve the full context
                import re
                query_lower = query.lower()
                
                # Check if it's a role + location query (e.g., "branch manager of Gulshan")
                role_location_pattern = r'(branch\s+)?manager\s+(of|at)\s+(.+?)(?:\s+branch)?$'
                match = re.search(role_location_pattern, query_lower)
                if match:
                    # Extract location/branch name
                    location = match.group(3).strip()
                    role = match.group(1) + "manager" if match.group(1) else "manager"
                    search_term = f"{role} {location}"
                    logger.info(f"[PHONEBOOK] Extracted role+location query: '{search_term}' from '{query}'")
                else:
                    # First, check if query starts with "find", "search", "lookup", etc. and extract the term after it
                    find_search_pattern = r'^(find|search|lookup|who is|contact|info about|get)\s+(.+)$'
                    match = re.search(find_search_pattern, query_lower, re.IGNORECASE)
                    if match:
                        # Extract the search term after the prefix
                        search_term = match.group(2).strip()
                        logger.info(f"[PHONEBOOK] Extracted search term '{search_term}' from query '{query}' (removed prefix '{match.group(1)}')")
                    else:
                        # Handle patterns like "phone number of X", "contact info for X", "email of X"
                        # Extract employee ID/name after "of", "for", etc.
                        # Pattern: (contact word) (optional "number") (of/for/about) (employee ID/name)
                        of_for_patterns = [
                            r'\b(phone|contact|email|mobile|telephone)\s+number\s+(?:of|for|about)\s+(.+)$',  # "phone number of X"
                            r'\b(phone|contact|email|mobile|telephone)\s+(?:of|for|about)\s+(.+)$',  # "phone of X"
                            r'\b(contact|info|information|details?)\s+(?:info|information|details?)?\s+(?:of|for|about)\s+(.+)$',  # "contact info for X"
                        ]
                        match = None
                        for pattern in of_for_patterns:
                            match = re.search(pattern, query_lower, re.IGNORECASE)
                            if match:
                                search_term = match.group(2).strip() if len(match.groups()) >= 2 else match.group(1).strip()
                                logger.info(f"[PHONEBOOK] Extracted search term '{search_term}' from query '{query}' (removed contact info prefix)")
                                break
                        if not match:
                            # Standard extraction: remove common words but preserve role and location terms
                            search_term = re.sub(
                                r'\b(phone|contact|number|email|address|mobile|telephone|who\s+is|what\s+is|tell\s+me|the|is|are|was|were|of|for|about)\b', 
                                '', 
                                query, 
                                flags=re.IGNORECASE
                            ).strip()
                    # Clean up multiple spaces and remove leading/trailing "of", "for", "about"
                    search_term = re.sub(r'\s+', ' ', search_term).strip()
                    search_term = re.sub(r'^(of|for|about)\s+', '', search_term, flags=re.IGNORECASE).strip()
                    search_term = re.sub(r'\s+(of|for|about)$', '', search_term, flags=re.IGNORECASE).strip()
                    
                    # Remove bank name suffixes (e.g., "of EBL", "of Eastern Bank", "at EBL")
                    # This helps when queries include "head of Retail & SME Banking Division of EBL"
                    search_term = re.sub(r'\s+(of|at|in)\s+(ebl|eastern\s+bank|eastern\s+bank\s+plc)[\s.]*$', '', search_term, flags=re.IGNORECASE).strip()
                    
                    # Remove "Division" if it appears anywhere (e.g., "Retail & SME Banking Division head" -> "Retail & SME Banking head")
                    # This helps match designations that don't include "Division"
                    # Remove "division" as a whole word (not part of other words)
                    original_search_term = search_term
                    search_term = re.sub(r'\bdivision\b', '', search_term, flags=re.IGNORECASE).strip()
                    # Clean up multiple spaces that might result
                    search_term = re.sub(r'\s+', ' ', search_term).strip()
                    if original_search_term != search_term:
                        logger.info(f"[PHONEBOOK] Removed 'division' from search term: '{original_search_term}' -> '{search_term}'")
                    
                    # If search term looks like a division/department name without a role, try adding "head"
                    # This handles queries like "Who is Retail & SME Banking Division?" -> "Retail & SME Banking head"
                    division_dept_keywords = ['banking', 'division', 'department', 'unit', 'section', 'retail', 'sme', 'corporate', 'operations', 'finance', 'hr', 'ict', 'it']
                    role_keywords = ['head', 'manager', 'director', 'officer', 'executive', 'president', 'ceo', 'cfo', 'chief', 'senior', 'assistant']
                    search_term_lower = search_term.lower()
                    has_division_keyword = any(keyword in search_term_lower for keyword in division_dept_keywords)
                    has_role_keyword = any(keyword in search_term_lower for keyword in role_keywords)
                    
                    # If it looks like a division/department name but no role mentioned, try with "head"
                    if has_division_keyword and not has_role_keyword:
                        search_term_with_head = f"{search_term} head"
                        logger.info(f"[PHONEBOOK] Query looks like division/department without role, trying with 'head': '{search_term_with_head}'")
                        # Try search with "head" added
                        results = phonebook_db.smart_search(search_term_with_head, limit=5)
                        if results:
                            logger.info(f"[OK] Found {len(results)} results with 'head' added")
                        else:
                            # Also try department search as fallback
                            logger.info(f"[PHONEBOOK] No results with 'head', trying department search for: '{search_term}'")
                            dept_results = phonebook_db.search_by_department(search_term, limit=5)
                            if dept_results:
                                results = dept_results
                                logger.info(f"[OK] Found {len(dept_results)} results via department search")
                            else:
                                # Try original search term as fallback
                                results = phonebook_db.smart_search(search_term, limit=5)
                    else:
                        # Try multiple search strategies
                        results = phonebook_db.smart_search(search_term, limit=5)
                
                # Final cleanup: Always remove "division" and bank name suffixes before searching
                # This ensures cleanup happens regardless of which code path was taken
                if search_term:
                    original_final = search_term
                    search_term = re.sub(r'\s+(of|at|in)\s+(ebl|eastern\s+bank|eastern\s+bank\s+plc)[\s.]*$', '', search_term, flags=re.IGNORECASE).strip()
                    search_term = re.sub(r'\bdivision\b', '', search_term, flags=re.IGNORECASE).strip()
                    search_term = re.sub(r'\s+', ' ', search_term).strip()
                    if original_final != search_term:
                        logger.info(f"[PHONEBOOK] Final cleanup: '{original_final}' -> '{search_term}'")
                        # If we cleaned the term and haven't searched yet, try searching with cleaned term
                        if not results:
                            results = phonebook_db.smart_search(search_term, limit=5)
                
                if results:
                    logger.info(f"[OK] Found {len(results)} results in phonebook for: {search_term}")
                    
                    # Format and return results
                    if len(results) == 1:
                        # Single result - detailed format
                        response = phonebook_db.format_contact_info(results[0])
                        response += "\n\n(Source: Phone Book Database)"
                    else:
                        # Multiple results - list format
                        response = ""
                        for i, emp in enumerate(results[:5], 1):
                            response += f"{i}. {emp['full_name']}\n"
                            if emp.get('designation'):
                                response += f"   Designation: {emp['designation']}\n"
                            if emp.get('department'):
                                response += f"   Department: {emp['department']}\n"
                            if emp.get('email'):
                                response += f"   Email: {emp['email']}\n"
                            if emp.get('employee_id'):
                                response += f"   Employee ID: {emp['employee_id']}\n"
                            if emp.get('mobile'):
                                response += f"   Mobile: {emp['mobile']}\n"
                            if emp.get('ip_phone'):
                                response += f"   IP Phone: {emp['ip_phone']}\n"
                            response += "\n"
                        
                        total_count = phonebook_db.count_search_results(search_term)
                        response += f"We found {total_count} matching contact(s) in total. Showing only the top 5 results.\n\n"
                        if total_count > 5:
                            response += "Please provide more details to narrow down the search.\n\n"
                        response += "(Source: Phone Book Database)"

                    # Save to memory
                    await self._persist_turn(session_id, query, response, knowledge_base=None, client_ip=client_ip)
                    
                    return {
                        "response": response,
                        "session_id": session_id
                    }  # DO NOT query LightRAG for contact queries
                    
                else:
                    # No results in phonebook - return helpful message (DO NOT use LightRAG)
                    logger.info(f"[INFO] No results in phonebook for '{search_term}' (contact query - NOT using LightRAG)")
                    response = f"I couldn't find any contact information for '{search_term}' in the employee directory. "
                    response += "Please try:\n"
                    response += "- Providing the full name\n"
                    response += "- Using the employee ID\n"
                    response += "- Specifying the department or designation\n"
                    response += "\n(Source: Phone Book Database)"

                    # Save to memory
                    await self._persist_turn(session_id, query, response, knowledge_base=None, client_ip=client_ip)
                    
                    return {
                        "response": response,
                        "session_id": session_id
                    }  # DO NOT query LightRAG for contact queries
                    
            except Exception as e:
                # For contact queries, even if phonebook has an error, don't use LightRAG
                logger.error(f"[ERROR] Phonebook error for contact query (NOT using LightRAG): {e}")
                response = "I'm having trouble accessing the employee directory right now. "
                response += "Please try again in a moment, or contact support for assistance."
                response += "\n\n(Source: Phone Book Database)"

                # Save to memory
                await self._persist_turn(session_id, query, response, knowledge_base=None, client_ip=client_ip)
                
                return {
                    "response": response,
                    "session_id": session_id
                }  # DO NOT query LightRAG for contact queries
        
        # Determine if we need LightRAG context (only for non-contact queries)
        context = ""
        sources = []
        card_rates_context = ""
        is_card_rates_query = False  # Initialize to avoid UnboundLocalError
        
        if not is_small_talk:
            # Check for policy queries and validate required entities
            if is_compliance_query:
                has_entities, clarification = self._check_policy_entities(query)
                if not has_entities and clarification:
                    logger.info(f"[POLICY] Policy query missing required entities, asking for clarification")
                    # Save to memory
                    await self._persist_turn(session_id, query, clarification, knowledge_base=None, client_ip=client_ip)
                    
                    return {
                        "response": clarification,
                        "session_id": session_id
                    }  # Don't query LightRAG if entities are missing
            
            # If it's a fee schedule query, call fee engine for deterministic numbers
            # CRITICAL: For fee schedule queries, use fee engine ONLY - never fall back to LightRAG
            # Note: This check is redundant if fee query was already handled above, but kept for safety
            is_card_rates_query = self._is_fee_schedule_query(query)
            if is_card_rates_query:
                logger.info(f"[CARD_RATES] Detected card rates query: '{query}' - using card rates microservice ONLY (no LightRAG fallback)")
                card_rates_context = await self._get_card_rates_context(query, session_id=session_id)
                if card_rates_context:
                    logger.info(f"[CARD_RATES] Card rates context added (length: {len(card_rates_context)} chars)")
                    # Add card rates source
                    if "Card Charges and Fees Schedule" not in sources:
                        sources.append("Card Charges and Fees Schedule (Effective from 01st January, 2026)")
                    # Skip LightRAG for card rates queries
                    context = ""  # Don't use LightRAG for card rates queries
                    logger.info(f"[CARD_RATES] Using ONLY card rates microservice data, skipping LightRAG")
                else:
                    # Fee engine returned empty - this should not happen if _get_card_rates_context is updated correctly
                    # But handle it gracefully with a deterministic not-found message
                    logger.warning(f"[CARD_RATES] Fee engine returned empty context for query: '{query}' - returning not-found message, NOT using LightRAG")
                    # Set a deterministic not-found message
                    card_rates_context = (
                        "=" * 70 + "\n"
                        f"{self.OFFICIAL_CARD_RATES_HEADER}\n"
                        f"{self.FEE_ENGINE_SOURCE}\n"
                        "=" * 70 + "\n\n"
                        "The requested fee information is not found in the Card Charges and Fees Schedule (effective 01 Jan 2026).\n"
                        "Please verify the card details and try again.\n\n"
                        "=" * 70
                    )
                    context = ""  # Do NOT use LightRAG
                    if "Card Charges and Fees Schedule" not in sources:
                        sources.append("Card Charges and Fees Schedule (Effective from 01st January, 2026)")
                    logger.info(f"[CARD_RATES] No data from fee engine - returning not-found message, NOT using LightRAG")
            else:
                # For non-card-rates queries, use LightRAG as normal
                # Smart routing: determine which knowledge base to use based on query content
                # This prevents confusion between financial reports and user documents
                if knowledge_base is None:
                    knowledge_base = self._get_knowledge_base(query)
                
                logger.info(f"[ROUTING] Calling LightRAG with knowledge_base='{knowledge_base}' for query: '{query[:100]}'")
                # CRITICAL: Filter financial documents for organizational overview queries
                filter_financial = self._is_organizational_overview_query(query)
                context, lightrag_sources = await self._get_lightrag_context(query, knowledge_base, filter_financial_docs=filter_financial)
                sources.extend(lightrag_sources)  # Add LightRAG sources
                if context:
                    logger.info(f"[ROUTING] LightRAG returned context (length: {len(context)} chars, sources: {len(lightrag_sources)}, filtered_financial={filter_financial})")
                else:
                    logger.warning(f"[ROUTING] LightRAG returned empty context")
                
                # If no sources found but we have context, add knowledge base name as fallback source
                if not sources and context and knowledge_base:
                    sources.append(f"Knowledge Base: {knowledge_base}")
                    logger.info(f"[SOURCES] Added knowledge base name as fallback source: {knowledge_base}")
        
        # Combine card rates context (if any) with LightRAG context
        # CRITICAL: For card rates queries, use ONLY card rates context (never LightRAG)
        combined_context = ""
        if is_card_rates_query:
            # For card rates queries, use ONLY fee engine data (never LightRAG)
            if card_rates_context:
                combined_context = card_rates_context
                logger.info(f"[CARD_RATES] Using ONLY card rates context: {len(card_rates_context)} chars (LightRAG skipped)")
            else:
                # This should not happen if _get_card_rates_context is updated correctly
                # But handle gracefully with a not-found message
                combined_context = (
                    "=" * 70 + "\n"
                    f"{self.OFFICIAL_CARD_RATES_HEADER}\n"
                    f"{self.FEE_ENGINE_SOURCE}\n"
                    "=" * 70 + "\n\n"
                    "The requested fee information is not found in the Card Charges and Fees Schedule (effective 01 Jan 2026).\n"
                    "Please verify the card details and try again.\n\n"
                    "=" * 70
                )
                logger.warning(f"[CARD_RATES] No context available from fee engine - using not-found message")
        elif card_rates_context and context:
            # For non-card-rates queries, combine both if available
            combined_context = f"{card_rates_context}\n\n{context}"
            logger.info(f"[CARD_RATES] Combined context: card_rates={len(card_rates_context)} chars, lightrag={len(context)} chars")
        elif card_rates_context:
            combined_context = card_rates_context
            logger.info(f"[CARD_RATES] Using only card rates context: {len(card_rates_context)} chars")
        else:
            combined_context = context
        
        # Store combined context for currency fixing
        self._last_combined_context = combined_context
        
        # Build messages
        messages = self._build_messages(query, combined_context, conversation_history)
        
        # Get response from OpenAI
        try:
            # Calculate max_tokens dynamically to avoid context length errors
            # Reserve tokens for response, but cap at model limit
            # For gpt-4 models, max context is 8192 tokens
            # Estimate: system message ~2000 tokens, context ~4000 tokens, user query ~100 tokens
            # Reserve ~1500 tokens for response to be safe
            max_response_tokens = min(settings.OPENAI_MAX_TOKENS, 1500)
            
            response = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=max_response_tokens,
                stream=False
            )
            
            full_response = response.choices[0].message.content
            # Clean markdown formatting from response
            full_response = self._clean_markdown_formatting(full_response)
            # Fix currency symbols as a safety net
            full_response = self._fix_currency_symbols(full_response, combined_context)
            # Fix bank name (replace "Eastern Bank Limited" with "Eastern Bank PLC")
            full_response = self._fix_bank_name(full_response)
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            full_response = "I apologize, but I'm experiencing technical difficulties. Please try again later."
        
        # Save to memory (user message was saved earlier before OpenAI call)
        await self._persist_turn(session_id, query, full_response, knowledge_base=knowledge_base, client_ip=client_ip)
        
        return {
            "response": full_response,
            "session_id": session_id,
            "sources": sources
        }

