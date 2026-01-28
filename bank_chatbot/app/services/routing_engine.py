"""
Routing engine for chat queries.
Separates routing decisions from ChatOrchestrator execution logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class RoutingDecision:
    query: str
    conversation_key: str
    effective_session_id: str
    knowledge_base: str
    target: str
    pending_disambiguation: bool
    should_check_phonebook: bool
    will_use_lightrag: bool
    # Signals (flattened for convenience)
    is_location_query: bool
    is_retail_asset_fee_query: bool
    is_skybanking_fee_query: bool
    is_fee_schedule_query: bool
    is_small_talk: bool
    is_contact_query: bool
    is_phonebook_query: bool
    is_employee_query: bool
    is_org_overview_query: bool
    is_banking_product_query: bool
    is_compliance_query: bool
    is_management_query: bool
    is_financial_query: bool
    is_milestone_query: bool
    is_user_doc_query: bool
    signals: Dict[str, bool]


class RoutingEngine:
    """Compute routing decisions using ChatOrchestrator's detectors."""

    def __init__(self, orchestrator: Any, phonebook_db_available: bool) -> None:
        self.orchestrator = orchestrator
        self.phonebook_db_available = phonebook_db_available

    async def decide(
        self,
        query: str,
        session_id: Optional[str] = None,
        knowledge_base: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> RoutingDecision:
        query = (query or "").strip()
        query_lower = query.lower()
        conversation_key = self.orchestrator._get_conversation_key(session_id, client_ip)
        effective_session_id = session_id if session_id else conversation_key

        pending_disambiguation = await self.orchestrator._get_disambiguation_state_any(conversation_key)

        # Signals
        is_location_query = self.orchestrator._is_location_query(query)
        is_retail_asset_fee_query = self.orchestrator._is_retail_asset_fee_query(query)
        is_skybanking_fee_query = self.orchestrator._is_skybanking_fee_query(query)
        is_fee_schedule_query = self.orchestrator._is_fee_schedule_query(query)

        is_small_talk = self.orchestrator._is_small_talk(query)
        is_contact_query = self.orchestrator._is_contact_info_query(query)
        is_phonebook_query = self.orchestrator._is_phonebook_query(query)
        is_employee_query = self.orchestrator._is_employee_query(query)

        is_org_overview_query = self.orchestrator._is_organizational_overview_query(query)
        is_banking_product_query = self.orchestrator._is_banking_product_query(query)
        is_compliance_query = self.orchestrator._is_compliance_query(query)
        is_management_query = self.orchestrator._is_management_query(query)
        is_financial_query = self.orchestrator._is_financial_report_query(query)
        is_milestone_query = self.orchestrator._is_milestone_query(query)
        is_user_doc_query = self.orchestrator._is_user_document_query(query)

        # Phonebook intent override: manager/contact/number patterns should favor phonebook.
        # Use word-boundaries to avoid false positives (e.g., "external" contains "ext").
        import re
        phonebook_intent_patterns = [
            r"\bmanager\b",
            r"\bcontact\b",
            r"\bphone\b",
            r"\bmobile\b",
            r"\bemail\b",
            r"\bip phone\b",
            r"\bextension\b",
            r"\bext\b",
            r"\b(phone|mobile|contact)\s+number\b",
        ]
        phonebook_intent_override = any(re.search(pat, query_lower) for pat in phonebook_intent_patterns)
        numeric_limit_phrases = [
            "number of",
            "how many",
            "count of",
            "maximum number",
            "max number",
            "limit on the number",
            "limit on number",
        ]
        has_contact_term = any(
            re.search(pat, query_lower)
            for pat in [
                r"\bcontact\b",
                r"\bphone\b",
                r"\bmobile\b",
                r"\bemail\b",
                r"\bip phone\b",
                r"\bextension\b",
                r"\bext\b",
            ]
        )
        if phonebook_intent_override and any(phrase in query_lower for phrase in numeric_limit_phrases) and not has_contact_term:
            phonebook_intent_override = False
        # Guardrail: only allow override if a contact/employee/phonebook signal exists.
        # This prevents policy/process queries like "email confirmation policy" from hitting phonebook.
        if phonebook_intent_override and not (is_contact_query or is_employee_query or is_phonebook_query):
            phonebook_intent_override = False

        # Knowledge base selection
        chosen_kb = knowledge_base or self.orchestrator._get_knowledge_base(query)

        # Final target (mirrors orchestrator precedence)
        if pending_disambiguation:
            target = "DISAMBIGUATION"
        elif phonebook_intent_override and not is_small_talk:
            target = "PHONEBOOK"
        elif is_location_query:
            target = "LOCATION_SERVICE"
        elif is_retail_asset_fee_query:
            target = "FEE_ENGINE_RETAIL_ASSETS"
        elif is_skybanking_fee_query:
            target = "FEE_ENGINE_SKYBANKING"
        elif is_fee_schedule_query:
            target = "FEE_ENGINE_CARDS"
        elif (is_phonebook_query or is_contact_query or is_employee_query) and not is_small_talk:
            target = "PHONEBOOK"
        elif is_small_talk:
            target = "OPENAI_SMALL_TALK"
        else:
            target = "LIGHTRAG"

        should_check_phonebook = (
            (is_phonebook_query or is_contact_query or is_employee_query or phonebook_intent_override)
            and not is_small_talk
            and self.phonebook_db_available
        )
        will_use_lightrag = not should_check_phonebook and not is_small_talk

        signals = {
            "is_location_query": is_location_query,
            "is_retail_asset_fee_query": is_retail_asset_fee_query,
            "is_skybanking_fee_query": is_skybanking_fee_query,
            "is_fee_schedule_query": is_fee_schedule_query,
            "is_small_talk": is_small_talk,
            "is_contact_query": is_contact_query,
            "is_phonebook_query": is_phonebook_query,
            "is_employee_query": is_employee_query,
            "is_org_overview_query": is_org_overview_query,
            "is_banking_product_query": is_banking_product_query,
            "is_compliance_query": is_compliance_query,
            "is_management_query": is_management_query,
            "is_financial_query": is_financial_query,
            "is_milestone_query": is_milestone_query,
            "is_user_doc_query": is_user_doc_query,
        }

        return RoutingDecision(
            query=query,
            conversation_key=conversation_key,
            effective_session_id=effective_session_id,
            knowledge_base=chosen_kb,
            target=target,
            pending_disambiguation=bool(pending_disambiguation),
            should_check_phonebook=should_check_phonebook,
            will_use_lightrag=will_use_lightrag,
            is_location_query=is_location_query,
            is_retail_asset_fee_query=is_retail_asset_fee_query,
            is_skybanking_fee_query=is_skybanking_fee_query,
            is_fee_schedule_query=is_fee_schedule_query,
            is_small_talk=is_small_talk,
            is_contact_query=is_contact_query,
            is_phonebook_query=is_phonebook_query,
            is_employee_query=is_employee_query,
            is_org_overview_query=is_org_overview_query,
            is_banking_product_query=is_banking_product_query,
            is_compliance_query=is_compliance_query,
            is_management_query=is_management_query,
            is_financial_query=is_financial_query,
            is_milestone_query=is_milestone_query,
            is_user_doc_query=is_user_doc_query,
            signals=signals,
        )
