"""
Unit tests: compliance/policy queries must route to LightRAG before phonebook.

Run (from repo root):
  python bank_chatbot/test_routing_engine_compliance.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "bank_chatbot"))

from app.services.routing_engine import RoutingEngine


def _mock_orchestrator(
  *,
  is_compliance_query: bool = False,
  is_banking_product_query: bool = False,
  is_employee_query: bool = False,
  is_contact_query: bool = False,
  is_phonebook_query: bool = False,
) -> Any:
    orch = MagicMock()
    orch._get_conversation_key.return_value = "conv-test"
    orch._get_knowledge_base.return_value = "ebl_products"

    async def _no_disambiguation(_k: Optional[str]) -> None:
        return None

    orch._get_disambiguation_state_any = _no_disambiguation

    orch._is_location_query.return_value = False
    orch._is_retail_asset_fee_query.return_value = False
    orch._is_skybanking_fee_query.return_value = False
    orch._is_fee_schedule_query.return_value = False
    orch._is_small_talk.return_value = False
    orch._is_contact_info_query.return_value = is_contact_query
    orch._is_phonebook_query.return_value = is_phonebook_query
    orch._is_employee_query.return_value = is_employee_query
    orch._is_organizational_overview_query.return_value = False
    orch._is_banking_product_query.return_value = is_banking_product_query
    orch._is_compliance_query.return_value = is_compliance_query
    orch._is_management_query.return_value = False
    orch._is_financial_report_query.return_value = False
    orch._is_milestone_query.return_value = False
    orch._is_user_document_query.return_value = False
    orch._is_datetime_query.return_value = False
    return orch


async def _decide(query: str, **orch_kwargs: Any) -> str:
    engine = RoutingEngine(_mock_orchestrator(**orch_kwargs), phonebook_db_available=True)
    decision = await engine.decide(query)
    return decision.target


async def main() -> int:
    failures = []

    cases = [
        (
            "BeneficialOwner_WithWhoIsEmployeeSignal",
            "Who is the beneficial owner of a limited company?",
            {"is_employee_query": True},
            "LIGHTRAG",
        ),
        (
            "ICTSecurity_WithWhoIsEmployeeSignal",
            "Who is primarily responsible for upholding ICT Security at EBL?",
            {"is_employee_query": True},
            "LIGHTRAG",
        ),
        (
            "CompliancePolicy_Explicit",
            "What is the AML policy for high risk customers?",
            {"is_compliance_query": True},
            "LIGHTRAG",
        ),
        (
            "RealPhonebook_ManagerLookup",
            "Who is the branch manager of Gulshan branch?",
            {"is_employee_query": True},
            "PHONEBOOK",
        ),
        (
            "ContactLookup_StillPhonebook",
            "What is the mobile number of John Ahmed?",
            {"is_contact_query": True, "is_employee_query": True},
            "PHONEBOOK",
        ),
    ]

    for name, query, orch_kwargs, expected in cases:
        actual = await _decide(query, **orch_kwargs)
        if actual != expected:
            failures.append({"case": name, "query": query, "expected": expected, "actual": actual})
            print(f"[FAIL] {name}: expected {expected}, got {actual}")
        else:
            print(f"[PASS] {name}")

    if failures:
        return 1
    print("\nAll routing engine compliance tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
