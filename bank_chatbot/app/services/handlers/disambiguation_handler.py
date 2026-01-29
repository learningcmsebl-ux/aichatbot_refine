"""
Disambiguation Handler - Manages disambiguation state and resolution.

Extracted from ChatOrchestrator to address the God Object anti-pattern.
This class is responsible for handling disambiguation flows when queries
are ambiguous and need user clarification.
"""

import re
import time
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class DisambiguationHandler:
    """
    Handles disambiguation state management and resolution.
    
    Responsibilities:
    - Store and retrieve disambiguation state
    - Resolve user selections from disambiguation prompts
    - Detect if user is abandoning disambiguation with a new query
    - Build disambiguation prompts
    
    Usage:
        handler = DisambiguationHandler(redis_cache)
        
        # Store state
        await handler.store_state(session_id, options, "fee_type")
        
        # Resolve selection
        selected = handler.resolve_selection("1", options)
        
        # Check if new query
        is_new = handler.looks_like_new_query("What is the interest rate?", options)
    """
    
    # Stopwords for keyword matching
    STOPWORDS = {
        "fee", "card", "bdt", "usd", "per", "transaction", "amount", "charge", 
        "on", "the", "a", "an", "for", "of", "in", "at", "to", "from", "with", 
        "by", "or", "and", "is", "are", "was", "were", "balance", "outstanding", 
        "year", "month", "day", "leaves", "leaf", "page", "schedule"
    }
    
    MIN_TOKEN_LENGTH = 3
    
    def __init__(self, redis_cache=None):
        """
        Initialize DisambiguationHandler.
        
        Args:
            redis_cache: Optional Redis cache instance for state persistence.
                        If not provided, uses local in-memory storage.
        """
        self.redis_cache = redis_cache
        # Fallback local storage when Redis is unavailable
        self._local_state: Dict[str, Dict[str, Any]] = {}
    
    def resolve_selection(
        self, 
        query: str, 
        options: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve user selection from query.
        
        Supports:
        - Number selection: "1", "1.", "1)"
        - Keyword matching: "fast cash", "enhanced"
        
        Args:
            query: User's query/message
            options: List of option dictionaries
            
        Returns:
            Selected option dict or None if no match
        """
        query_lower = query.strip().lower()
        
        # Try number selection first
        m = re.match(r"^\s*(\d+)\s*[\.\)]?\s*", query_lower)
        if m:
            try:
                selection_num = int(m.group(1))
                if 1 <= selection_num <= len(options):
                    selected = options[selection_num - 1]
                    logger.info(
                        f"[DISAMBIGUATION] Resolved by number {selection_num}: "
                        f"loan_product={selected.get('loan_product')}, "
                        f"charge_context={selected.get('charge_context')}"
                    )
                    return selected
            except (ValueError, IndexError):
                pass
        
        # Try keyword matching
        for option in options:
            keywords_to_check = self._extract_option_keywords(option)
            
            for keyword in keywords_to_check:
                if keyword and keyword in query_lower:
                    logger.info(
                        f"[DISAMBIGUATION] Resolved by keyword '{keyword}': "
                        f"loan_product={option.get('loan_product')}, "
                        f"charge_context={option.get('charge_context')}"
                    )
                    return option
        
        logger.info(f"[DISAMBIGUATION] Could not resolve selection from: '{query}'")
        return None
    
    def _extract_option_keywords(self, option: Dict[str, Any]) -> List[str]:
        """
        Extract searchable keywords from an option dictionary.
        
        Args:
            option: Option dictionary with loan_product, card_product, etc.
            
        Returns:
            List of keywords to check against user query
        """
        keywords_to_check = []
        
        # Extract fields
        loan_product = option.get("loan_product", "").lower()
        loan_product_name = option.get("loan_product_name", "").lower()
        card_product = option.get("card_product", "").lower()
        card_product_name = option.get("card_product_name", "").lower()
        charge_context = option.get("charge_context", "").lower()
        charge_description = option.get("charge_description", "").lower()
        label = option.get("label", "").lower()
        keywords = option.get("keywords") or []
        
        # Add full values
        if loan_product:
            keywords_to_check.append(loan_product)
        if loan_product_name:
            keywords_to_check.append(loan_product_name)
            self._add_filtered_words(loan_product_name, keywords_to_check)
        if card_product:
            keywords_to_check.append(card_product)
            self._add_filtered_words(card_product, keywords_to_check)
        if card_product_name:
            keywords_to_check.append(card_product_name)
            self._add_filtered_words(card_product_name, keywords_to_check)
        if charge_description:
            keywords_to_check.append(charge_description)
            self._add_filtered_words(charge_description, keywords_to_check)
        if label:
            keywords_to_check.append(label)
            self._add_filtered_words(label, keywords_to_check)
        
        # Add explicit keywords
        for kw in keywords:
            kw_lower = str(kw).lower().strip()
            if kw_lower and kw_lower not in self.STOPWORDS:
                keywords_to_check.append(kw_lower)
        
        # Add loan product keyword mappings
        loan_product_keywords = {
            "fast cash": ["fast cash", "fastcash"],
            "fast loan": ["fast loan", "fastloan"],
            "education loan": ["education loan", "edu loan", "education"],
            "home loan": ["home loan", "homeloan"],
            "auto loan": ["auto loan", "car loan", "auto", "car"],
            "executive loan": ["executive loan", "executive", "personal loan"],
        }
        
        for key, mapped_keywords in loan_product_keywords.items():
            if key in loan_product or key in loan_product_name:
                keywords_to_check.extend(mapped_keywords)
        
        # Add charge_context keywords
        if charge_context:
            context_keywords = {
                "on_limit": ["on limit", "on loan amount", "loan amount"],
                "on_enhanced_amount": ["enhanced", "enhancement", "enhance", "enhanced amount"],
                "on_reduced_amount": ["reduced", "reduction", "reduce", "reduced amount"],
                "on_category_a": ["category a", "cat a"],
                "on_category_b": ["category b", "cat b"],
                "on_category_a_b": ["category a and category b", "category a & b", "category a/b"],
                "on_category_c": ["category c", "cat c"],
                "general": ["general", "normal", "standard"]
            }
            if charge_context in context_keywords:
                keywords_to_check.extend(context_keywords[charge_context])
        
        return keywords_to_check
    
    def _add_filtered_words(self, text: str, keywords_list: List[str]):
        """Add individual words from text, filtering stopwords and short tokens."""
        for word in text.split():
            if len(word) >= self.MIN_TOKEN_LENGTH and word not in self.STOPWORDS:
                keywords_list.append(word)
    
    def looks_like_new_query(
        self, 
        query: str, 
        options: List[Dict[str, Any]]
    ) -> bool:
        """
        Detect if user is asking a new question instead of selecting from options.
        
        Args:
            query: User's query
            options: Current disambiguation options
            
        Returns:
            True if query appears to be a new question
        """
        query_lower = (query or "").strip().lower()
        if not query_lower:
            return False

        # If user replied with a leading option number, treat as selection
        if re.match(r"^\s*\d+\s*[\.\)]?\s*", query_lower):
            return False

        # If the query can be resolved to an option, it's a selection
        if self.resolve_selection(query, options):
            return False

        # If query contains intent keywords, it's likely a new question
        intent_keywords = [
            "fee", "fees", "charge", "charges", "cost", "pricing", "price",
            "loan", "retail asset", "skybanking", "card",
            "branch", "atm", "location", "address",
            "contact", "phone", "mobile", "email", "extension",
            "process", "procedure", "how to", "steps",
        ]
        if any(k in query_lower for k in intent_keywords):
            return True

        # Long queries are likely new questions
        if len(query_lower.split()) >= 5:
            return True

        return False
    
    def has_process_intent(self, query: str) -> bool:
        """
        Check if query has process/procedure intent.
        
        Args:
            query: User's query
            
        Returns:
            True if query asks about a process/procedure
        """
        query_lower = (query or "").lower()
        # Avoid treating "processing fee" as a process intent
        if any(k in query_lower for k in ["processing fee", "processing_fee"]):
            return False
        return any(k in query_lower for k in ["process", "procedure", "how to", "steps", "method"])
    
    def should_prompt_routing_disambiguation(
        self, 
        query: str, 
        decision: Any
    ) -> bool:
        """
        Determine if we need to ask user for routing clarification.
        
        Args:
            query: User's query
            decision: Routing decision object with boolean flags
            
        Returns:
            True if conflicting signals detected
        """
        if decision.is_small_talk:
            return False

        is_fee = (
            decision.is_fee_schedule_query or 
            decision.is_retail_asset_fee_query or 
            decision.is_skybanking_fee_query
        )
        is_contact = (
            decision.is_contact_query or 
            decision.is_employee_query or 
            decision.is_phonebook_query
        )
        is_location = decision.is_location_query
        has_process = self.has_process_intent(query)

        # Ask only when signals conflict
        if has_process and (is_fee or is_contact or is_location):
            return True
        if is_contact and (is_fee or is_location):
            return True
        if is_fee and is_location:
            return True
        return False
    
    def build_routing_disambiguation_prompt(self) -> str:
        """Build prompt for routing disambiguation."""
        return "\n".join([
            "Your question could refer to multiple things. Please choose one:",
            "1. Fees/charges (cards, loans, or Skybanking)",
            "2. Steps/process/how to do it",
            "3. Branch/ATM/location",
            "4. Contact information (phone/email)",
            "",
            "Please reply with a number (1-4)."
        ])
    
    def build_routing_disambiguation_options(self) -> List[Dict[str, Any]]:
        """Build options for routing disambiguation."""
        return [
            {"label": "Fees/charges", "route": "fee", "keywords": ["fee", "charge", "cost"]},
            {"label": "Process/steps", "route": "process", "keywords": ["process", "how to", "steps"]},
            {"label": "Location", "route": "location", "keywords": ["branch", "atm", "location"]},
            {"label": "Contact info", "route": "contact", "keywords": ["contact", "phone", "email"]},
        ]
    
    def build_fee_type_disambiguation_prompt(
        self, 
        fee_candidates: List[str]
    ) -> str:
        """
        Build prompt for fee type disambiguation.
        
        Args:
            fee_candidates: List of fee type labels
            
        Returns:
            Formatted prompt string
        """
        lines = ["Please specify which fee you're asking about:"]
        for idx, candidate in enumerate(fee_candidates, 1):
            lines.append(f"{idx}. {candidate}")
        lines.extend(["", "Please reply with a number."])
        return "\n".join(lines)
    
    def build_fee_type_disambiguation_options(
        self, 
        fee_candidates: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Build options for fee type disambiguation.
        
        Args:
            fee_candidates: List of fee type labels
            
        Returns:
            List of option dictionaries
        """
        return [
            {"label": candidate, "charge_type": candidate, "keywords": [candidate.lower()]}
            for candidate in fee_candidates
        ]
    
    # =========================================================================
    # State Persistence (Redis + Local Fallback)
    # =========================================================================
    
    async def store_state(
        self,
        state_key: str,
        state: Dict[str, Any],
        ttl_seconds: int = 300
    ) -> None:
        """
        Store disambiguation state.
        
        Tries Redis first, falls back to local storage.
        
        Args:
            state_key: Unique key for the state
            state: State dictionary to store
            ttl_seconds: Time-to-live in seconds
        """
        if self.redis_cache:
            try:
                await self.redis_cache.set_disambiguation_state(state_key, state, ttl=ttl_seconds)
                return
            except Exception as e:
                logger.warning(f"[DISAMBIGUATION] Redis store failed, using local: {e}")
        
        # Local fallback
        self._cleanup_local_state()
        self._local_state[state_key] = {
            "state": state,
            "expires_at": time.time() + ttl_seconds,
        }
    
    async def get_state(self, state_key: str) -> Optional[Dict[str, Any]]:
        """
        Get disambiguation state.
        
        Tries Redis first, falls back to local storage.
        
        Args:
            state_key: Unique key for the state
            
        Returns:
            State dictionary or None if not found/expired
        """
        if self.redis_cache:
            try:
                return await self.redis_cache.get_disambiguation_state(state_key)
            except Exception as e:
                logger.warning(f"[DISAMBIGUATION] Redis get failed, using local: {e}")
        
        # Local fallback
        self._cleanup_local_state()
        entry = self._local_state.get(state_key)
        if entry:
            return entry.get("state")
        return None
    
    async def clear_state(self, state_key: str) -> None:
        """
        Clear disambiguation state.
        
        Args:
            state_key: Unique key for the state
        """
        if self.redis_cache:
            try:
                await self.redis_cache.delete(f"disambiguation:{state_key}")
            except Exception as e:
                logger.warning(f"[DISAMBIGUATION] Redis delete failed: {e}")
        
        # Also clear local
        self._local_state.pop(state_key, None)
    
    def _cleanup_local_state(self) -> None:
        """Remove expired entries from local state."""
        now = time.time()
        expired = [k for k, v in self._local_state.items() if v.get("expires_at", 0) <= now]
        for k in expired:
            self._local_state.pop(k, None)
    
    async def store_structured_state(
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
        Store structured disambiguation state.
        
        Args:
            state_key: Session/conversation key
            product_line: Product line (CREDIT_CARDS, RETAIL_ASSETS, etc.)
            charge_type: Charge type being queried
            as_of_date: Date for fee lookup
            options: List of disambiguation options
            disambiguation_type: Type of disambiguation (loan_product, fee_type, etc.)
            prompt_message: Message shown to user
            extra: Additional data to store
            ttl_seconds: Time-to-live
        """
        state = {
            "product_line": product_line,
            "charge_type": charge_type,
            "as_of_date": as_of_date,
            "options": options,
            "disambiguation_type": disambiguation_type,
            "prompt_message": prompt_message,
            "extra": extra or {},
        }
        
        if self.redis_cache:
            try:
                await self.redis_cache.store_disambiguation_state(
                    session_id=state_key,
                    product_line=product_line,
                    charge_type=charge_type,
                    as_of_date=as_of_date,
                    options=options,
                    disambiguation_type=disambiguation_type,
                    prompt_message=prompt_message,
                    extra=extra,
                )
                return
            except Exception as e:
                logger.warning(f"[DISAMBIGUATION] Redis structured store failed: {e}")
        
        # Local fallback
        await self.store_state(state_key, state, ttl_seconds)
