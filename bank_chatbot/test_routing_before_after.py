"""Compare old vs new RoutingEngine precedence on representative queries."""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO))

from app.services.handlers.query_classifier import QueryClassifier
from app.services.routing_engine import RoutingEngine

qc = QueryClassifier()


class Orch:
    def _get_conversation_key(self, session_id, client_ip):
        return "t"

    def _get_knowledge_base(self, query):
        return "ebl_products"

    async def _get_disambiguation_state_any(self, key):
        return None

    _is_location_query = lambda self, q: qc.is_location_query(q)
    _is_retail_asset_fee_query = lambda self, q: qc.is_retail_asset_fee_query(q)
    _is_skybanking_fee_query = lambda self, q: qc.is_skybanking_fee_query(q)
    _is_fee_schedule_query = lambda self, q: qc.is_fee_schedule_query(q)
    _is_small_talk = lambda self, q: qc.is_small_talk(q)
    _is_contact_info_query = lambda self, q: qc.is_contact_info_query(q)
    _is_phonebook_query = lambda self, q: qc.is_phonebook_query(q)
    _is_employee_query = lambda self, q: qc.is_employee_query(q)
    _is_organizational_overview_query = lambda self, q: qc.is_organizational_overview_query(q)
    _is_banking_product_query = lambda self, q: qc.is_banking_product_query(q)
    _is_compliance_query = lambda self, q: qc.is_compliance_query(q)
    _is_management_query = lambda self, q: qc.is_management_query(q)
    _is_financial_report_query = lambda self, q: qc.is_financial_report_query(q)
    _is_milestone_query = lambda self, q: qc.is_milestone_query(q)
    _is_user_document_query = lambda self, q: qc.is_user_document_query(q)


def _old_target(decision, query_lower: str) -> str:
    """Pre-fix precedence: phonebook_intent_override before location/fees."""
    patterns = [
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
    pio = any(re.search(p, query_lower) for p in patterns)
    numeric = [
        "number of",
        "how many",
        "count of",
        "maximum number",
        "max number",
        "limit on the number",
        "limit on number",
    ]
    has_contact = any(
        re.search(p, query_lower)
        for p in [r"\bcontact\b", r"\bphone\b", r"\bmobile\b", r"\bemail\b", r"\bip phone\b", r"\bextension\b", r"\bext\b"]
    )
    if pio and any(x in query_lower for x in numeric) and not has_contact:
        pio = False
    if pio and not (decision.is_contact_query or decision.is_employee_query or decision.is_phonebook_query):
        pio = False

    if decision.pending_disambiguation:
        return "DISAMBIGUATION"
    if pio and not decision.is_small_talk:
        return "PHONEBOOK"
    if decision.is_location_query:
        return "LOCATION_SERVICE"
    if decision.is_retail_asset_fee_query:
        return "FEE_ENGINE_RETAIL_ASSETS"
    if decision.is_skybanking_fee_query:
        return "FEE_ENGINE_SKYBANKING"
    if decision.is_fee_schedule_query:
        return "FEE_ENGINE_CARDS"
    if (decision.is_phonebook_query or decision.is_contact_query or decision.is_employee_query) and not decision.is_small_talk:
        return "PHONEBOOK"
    if decision.is_small_talk:
        return "OPENAI_SMALL_TALK"
    return "LIGHTRAG"


QUERIES = [
    "Who is the beneficial owner of a limited company?",
    "Who is primarily responsible for upholding ICT Security at EBL?",
    "What is the email confirmation policy for account processing?",
    "How many staff are required for customer service and cash transactions from the Agent side?",
    "What is the AML policy for high risk customers?",
    "What is the maximum number of daily Cash Withdrawal transactions allowed for a Savings Account?",
    "Who is the branch manager of Gulshan branch?",
    "What is the mobile number of John Ahmed?",
    "What is the dress code for employees?",
    "Who is head of brand and marketing at EBL?",
    "Explain the KYC requirements for corporate accounts",
    "What is the procedure for account opening?",
    "Find employee john_doe in phonebook",
    "How does a Master Agent differ from a Unit Agent based on outlets?",
    "What is the regulatory requirement for CTR reporting?",
]


async def main() -> int:
    engine = RoutingEngine(Orch(), phonebook_db_available=True)
    fixed = legit_pb = regress = 0

    print(f"{'OLD':22} -> {'NEW':22} | prefers_lr | note")
    print("-" * 95)
    for query in QUERIES:
        decision = await engine.decide(query)
        old = _old_target(decision, query.lower())
        new = decision.target
        plr = decision.signals.get("prefers_lightrag_over_phonebook")

        if old == "PHONEBOOK" and new == "LIGHTRAG":
            fixed += 1
            note = "FIXED"
        elif old == "PHONEBOOK" and new == "PHONEBOOK":
            legit_pb += 1
            note = "legit PB"
        elif new == "PHONEBOOK" and old != "PHONEBOOK":
            regress += 1
            note = "REGRESSION"
        else:
            note = "ok"

        print(f"{old:22} -> {new:22} | {str(plr):5} | {note:10} | {query[:45]}")

    print(f"\nfixed={fixed} legit_phonebook={legit_pb} regressions={regress}")
    return 0 if regress == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
