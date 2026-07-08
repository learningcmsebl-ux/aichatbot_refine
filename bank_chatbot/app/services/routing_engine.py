"""
Routing engine for chat queries.
Separates routing decisions from ChatOrchestrator execution logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Dict, Any

# Policy/compliance phrasing that must not be treated as phonebook lookups even when
# "who is", "manager", or "contact" appear in the question.
_POLICY_PHONEBOOK_BLOCKLIST = (
    "beneficial owner",
    "bo of a limited",
    "limited company",
    "ict security",
    "information security",
    "cyber security",
    "responsible for upholding",
    "code of conduct",
    "gap policy",
    "dress code",
    "aml policy",
    "kyc policy",
    "compliance policy",
    "regulatory requirement",
    "regulatory requirements",
    "internal policy",
    "operational policy",
)


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
    is_eblhome_form_query: bool
    is_eblhome_app_link_query: bool
    is_eblhome_leadership_query: bool
    is_eblhome_soc_query: bool
    is_eblhome_proposal_query: bool
    is_eblhome_circular_query: bool
    is_datetime_query: bool
    signals: Dict[str, bool]


class RoutingEngine:
    """Compute routing decisions using ChatOrchestrator's detectors."""

    def __init__(
        self,
        orchestrator: Any,
        phonebook_db_available: bool,
        forms_db_available: bool = False,
        apps_db_available: bool = False,
        leadership_db_available: bool = False,
        soc_db_available: bool = False,
        proposals_db_available: bool = False,
        circulars_db_available: bool = False,
    ) -> None:
        self.orchestrator = orchestrator
        self.phonebook_db_available = phonebook_db_available
        self.forms_db_available = forms_db_available
        self.apps_db_available = apps_db_available
        self.leadership_db_available = leadership_db_available
        self.soc_db_available = soc_db_available
        self.proposals_db_available = proposals_db_available
        self.circulars_db_available = circulars_db_available

    @staticmethod
    def _is_primary_contact_lookup(query_lower: str, is_contact_query: bool) -> bool:
        """True when the user is asking for someone's contact details (not policy wording with 'email')."""
        if not is_contact_query:
            return False
        contact_lookup_patterns = (
            r"\b(phone|mobile|telephone|email|ip phone)\s+(number|no\.?)\b",
            r"\bcontact\s+(info|information|details|number)\b",
            r"\b(get|find|search|lookup).*\b(phone|mobile|email|contact)\b",
        )
        return any(re.search(pat, query_lower) for pat in contact_lookup_patterns)

    @staticmethod
    def _is_role_people_lookup(query_lower: str, is_employee_query: bool) -> bool:
        """True for manager/head/director lookups that should use phonebook, not location."""
        if not is_employee_query:
            return False
        return bool(
            re.search(
                r"\b(manager|head|director|officer|executive|md|ceo|cfo|cto)\b",
                query_lower,
            )
        )

    @staticmethod
    def _prefers_lightrag_over_phonebook(
        *,
        query_lower: str,
        is_compliance_query: bool,
        is_banking_product_query: bool,
        is_management_query: bool,
        is_financial_query: bool,
        is_milestone_query: bool,
        is_user_doc_query: bool,
        is_org_overview_query: bool,
    ) -> bool:
        """Knowledge-base queries (policy, products, etc.) must not route to phonebook."""
        if any(
            (
                is_compliance_query,
                is_banking_product_query,
                is_management_query,
                is_financial_query,
                is_milestone_query,
                is_user_doc_query,
                is_org_overview_query,
            )
        ):
            return True
        return any(phrase in query_lower for phrase in _POLICY_PHONEBOOK_BLOCKLIST)

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
        is_eblhome_form_query = getattr(self.orchestrator, "_is_eblhome_form_query", lambda _q: False)(query)
        is_eblhome_app_link_query = getattr(self.orchestrator, "_is_eblhome_app_link_query", lambda _q: False)(query)
        is_eblhome_leadership_query = getattr(
            self.orchestrator, "_is_eblhome_leadership_query", lambda _q: False
        )(query)
        is_eblhome_soc_query = getattr(self.orchestrator, "_is_eblhome_soc_query", lambda _q: False)(query)
        is_eblhome_proposal_query = getattr(
            self.orchestrator, "_is_eblhome_proposal_query", lambda _q: False
        )(query)
        is_eblhome_circular_query = getattr(
            self.orchestrator, "_is_eblhome_circular_query", lambda _q: False
        )(query)
        is_datetime_query = self.orchestrator._is_datetime_query(query)

        # Phonebook intent override:
        # Use word-boundaries to avoid false positives (e.g., "external" contains "ext").
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

        prefers_lightrag = self._prefers_lightrag_over_phonebook(
            query_lower=query_lower,
            is_compliance_query=is_compliance_query,
            is_banking_product_query=is_banking_product_query,
            is_management_query=is_management_query,
            is_financial_query=is_financial_query,
            is_milestone_query=is_milestone_query,
            is_user_doc_query=is_user_doc_query,
            is_org_overview_query=is_org_overview_query,
        )
        if prefers_lightrag:
            phonebook_intent_override = False

        # Genuine contact/role lookups must stay on phonebook even when banking_product misfires.
        if prefers_lightrag and self._is_primary_contact_lookup(query_lower, is_contact_query):
            prefers_lightrag = False
        role_people_lookup = (
            self._is_role_people_lookup(query_lower, is_employee_query)
            and not is_compliance_query
        )
        if role_people_lookup:
            prefers_lightrag = False

        # Knowledge base selection
        chosen_kb = knowledge_base or self.orchestrator._get_knowledge_base(query)

        # Final target (mirrors orchestrator precedence)
        if pending_disambiguation:
            target = "DISAMBIGUATION"
        elif is_eblhome_leadership_query and self.leadership_db_available and not is_small_talk:
            target = "EBLHOME_LEADERSHIP"
        elif role_people_lookup and not is_small_talk:
            target = "PHONEBOOK"
        elif is_location_query:
            target = "LOCATION_SERVICE"
        elif is_retail_asset_fee_query:
            target = "FEE_ENGINE_RETAIL_ASSETS"
        elif is_skybanking_fee_query:
            target = "FEE_ENGINE_SKYBANKING"
        elif is_fee_schedule_query:
            target = "FEE_ENGINE_CARDS"
        elif is_eblhome_circular_query and self.circulars_db_available and not is_small_talk:
            target = "EBLHOME_CIRCULARS"
        elif is_eblhome_soc_query and self.soc_db_available and not is_small_talk:
            target = "EBLHOME_SOC"
        elif is_eblhome_proposal_query and self.proposals_db_available and not is_small_talk:
            target = "EBLHOME_PROPOSALS"
        elif is_eblhome_app_link_query and self.apps_db_available and not is_small_talk:
            target = "EBLHOME_APPS"
        elif is_eblhome_form_query and self.forms_db_available and not is_small_talk:
            target = "EBLHOME_FORMS"
        elif prefers_lightrag and not is_small_talk:
            target = "LIGHTRAG"
        elif phonebook_intent_override and not is_small_talk:
            target = "PHONEBOOK"
        elif (is_phonebook_query or is_contact_query or is_employee_query) and not is_small_talk:
            target = "PHONEBOOK"
        elif is_datetime_query and not is_small_talk:
            target = "DATETIME"
        elif is_small_talk:
            target = "OPENAI_SMALL_TALK"
        else:
            target = "LIGHTRAG"

        should_check_phonebook = target == "PHONEBOOK" and self.phonebook_db_available
        should_check_forms = target == "EBLHOME_FORMS" and self.forms_db_available
        should_check_apps = target == "EBLHOME_APPS" and self.apps_db_available
        should_check_leadership = target == "EBLHOME_LEADERSHIP" and self.leadership_db_available
        should_check_circulars = target == "EBLHOME_CIRCULARS" and self.circulars_db_available
        should_check_soc = target == "EBLHOME_SOC" and self.soc_db_available
        should_check_proposals = target == "EBLHOME_PROPOSALS" and self.proposals_db_available
        # will_use_lightrag is only True when target is actually LIGHTRAG
        will_use_lightrag = target == "LIGHTRAG"

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
            "is_eblhome_form_query": is_eblhome_form_query,
            "is_eblhome_app_link_query": is_eblhome_app_link_query,
            "is_eblhome_leadership_query": is_eblhome_leadership_query,
            "is_eblhome_soc_query": is_eblhome_soc_query,
            "is_eblhome_proposal_query": is_eblhome_proposal_query,
            "is_eblhome_circular_query": is_eblhome_circular_query,
            "is_datetime_query": is_datetime_query,
            "prefers_lightrag_over_phonebook": prefers_lightrag,
            "role_people_lookup": role_people_lookup,
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
            is_eblhome_form_query=is_eblhome_form_query,
            is_eblhome_app_link_query=is_eblhome_app_link_query,
            is_eblhome_leadership_query=is_eblhome_leadership_query,
            is_eblhome_soc_query=is_eblhome_soc_query,
            is_eblhome_proposal_query=is_eblhome_proposal_query,
            is_eblhome_circular_query=is_eblhome_circular_query,
            is_datetime_query=is_datetime_query,
            signals=signals,
        )
