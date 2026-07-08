"""
P1 classifier regression tests (employee + banking_product false positives).

Run (from repo root):
  python bank_chatbot/test_query_classifier_p1.py
"""

from __future__ import annotations

import asyncio
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


CLASSIFIER_CASES = [
    # query, expected_employee, expected_banking_product
    ("What is the mobile number of John Ahmed?", False, False),
    ("Who is the beneficial owner of a limited company?", False, False),
    ("Who is primarily responsible for upholding ICT Security at EBL?", False, False),
    ("Who is the branch manager of Gulshan branch?", True, False),
    ("What is the email confirmation policy for account processing?", False, True),
    (
        "What is the maximum number of daily Cash Withdrawal transactions allowed for a Savings Account?",
        False,
        True,
    ),
    ("Find employee john_doe in phonebook", True, False),
    ("Who is head of brand and marketing at EBL?", True, False),
]

ROUTING_CASES = [
    ("What is the mobile number of John Ahmed?", "PHONEBOOK"),
    ("Who is the beneficial owner of a limited company?", "LIGHTRAG"),
    ("Who is primarily responsible for upholding ICT Security at EBL?", "LIGHTRAG"),
    ("Who is the branch manager of Gulshan branch?", "PHONEBOOK"),
    ("What is the email confirmation policy for account processing?", "LIGHTRAG"),
    (
        "What is the maximum number of daily Cash Withdrawal transactions allowed for a Savings Account?",
        "LIGHTRAG",
    ),
    ("Who is head of brand and marketing at EBL?", "PHONEBOOK"),
]


async def main() -> int:
    failures = []

    print("=== Classifier signals ===")
    for query, exp_emp, exp_bp in CLASSIFIER_CASES:
        emp = qc.is_employee_query(query)
        bp = qc.is_banking_product_query(query)
        ok = emp == exp_emp and bp == exp_bp
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] emp={emp} bp={bp} | {query[:60]}")
        if not ok:
            failures.append(
                {
                    "query": query,
                    "expected": {"employee": exp_emp, "banking_product": exp_bp},
                    "actual": {"employee": emp, "banking_product": bp},
                }
            )

    print("\n=== End-to-end routing ===")
    engine = RoutingEngine(Orch(), phonebook_db_available=True)
    for query, expected_target in ROUTING_CASES:
        decision = await engine.decide(query)
        ok = decision.target == expected_target
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {decision.target:22} (expected {expected_target}) | {query[:55]}")
        if not ok:
            failures.append(
                {
                    "query": query,
                    "expected_target": expected_target,
                    "actual_target": decision.target,
                    "signals": decision.signals,
                }
            )

    if failures:
        print("\n=== FAILURES ===")
        for item in failures:
            print(item)
        return 1

    print("\nAll P1 classifier tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
