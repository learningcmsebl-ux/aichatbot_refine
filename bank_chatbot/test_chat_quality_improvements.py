"""
Unit tests for chatbot output-quality improvements (P0–P2).

Run (from repo root):
  python bank_chatbot/test_chat_quality_improvements.py
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

from app.services.handlers.query_classifier import QueryClassifier
from app.services.routing_engine import RoutingEngine


def _mock_orchestrator(**overrides: Any) -> Any:
    orch = MagicMock()
    orch._get_conversation_key.return_value = "conv-test"
    orch._get_knowledge_base.return_value = "ebl_products"

    async def _no_disambiguation(_k: Optional[str]) -> None:
        return None

    orch._get_disambiguation_state_any = _no_disambiguation

    defaults = {
        "_is_location_query": False,
        "_is_retail_asset_fee_query": False,
        "_is_skybanking_fee_query": False,
        "_is_fee_schedule_query": False,
        "_is_small_talk": False,
        "_is_contact_info_query": False,
        "_is_phonebook_query": False,
        "_is_employee_query": False,
        "_is_organizational_overview_query": False,
        "_is_banking_product_query": False,
        "_is_compliance_query": False,
        "_is_management_query": False,
        "_is_financial_report_query": False,
        "_is_milestone_query": False,
        "_is_user_document_query": False,
        "_is_datetime_query": False,
    }
    for name, value in {**defaults, **overrides}.items():
        getattr(orch, name).return_value = value
    return orch


async def _route_target(query: str, **orch_kwargs: Any) -> str:
    engine = RoutingEngine(_mock_orchestrator(**orch_kwargs), phonebook_db_available=True)
    decision = await engine.decide(query)
    return decision.target


def test_small_talk_greetings() -> None:
    qc = QueryClassifier()
    assert qc.is_small_talk("hi")
    assert qc.is_small_talk("Hello!")
    assert qc.is_small_talk("hey there")
    assert not qc.is_small_talk("how to get a ebl credit card?")


def test_datetime_classifier_word_boundaries() -> None:
    qc = QueryClassifier()
    assert qc.is_datetime_query("What time is it?")
    assert qc.is_datetime_query("What is today's date?")
    assert not qc.is_datetime_query("account upgrade policy")
    assert not qc.is_datetime_query("external confirmation process")


def test_compliance_classifier_not_product_policy() -> None:
    qc = QueryClassifier()
    assert qc.is_compliance_query("What is the AML policy for sensitive customers?")
    assert not qc.is_compliance_query("What is the credit card annual fee policy?")


def test_grounding_threshold() -> None:
    from app.services.chat_orchestrator import ChatOrchestrator

    orch = ChatOrchestrator.__new__(ChatOrchestrator)
    assert not orch._has_sufficient_grounding("")
    assert not orch._has_sufficient_grounding("short")
    assert orch._has_sufficient_grounding("x" * 120)


def test_routing_target_follow_up_hint() -> None:
    from app.services.chat_orchestrator import ChatOrchestrator

    orch = ChatOrchestrator.__new__(ChatOrchestrator)
    history = [
        {"role": "user", "message": "Super HPA account interest"},
        {"role": "assistant", "message": "...", "routing_target": "LIGHTRAG"},
    ]
    assert orch._extract_last_routing_target(history) == "LIGHTRAG"


async def test_datetime_routing_target() -> None:
    target = await _route_target(
        "What time is it now?",
        _is_datetime_query=True,
    )
    assert target == "DATETIME"


async def main() -> int:
    failures: list[str] = []

    sync_tests = [
        ("small_talk_greetings", test_small_talk_greetings),
        ("datetime_classifier_word_boundaries", test_datetime_classifier_word_boundaries),
        ("compliance_classifier_not_product_policy", test_compliance_classifier_not_product_policy),
        ("grounding_threshold", test_grounding_threshold),
        ("routing_target_follow_up_hint", test_routing_target_follow_up_hint),
    ]
    for name, fn in sync_tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            print(f"FAIL {name}: {exc}")

    async_tests = [
        ("datetime_routing_target", test_datetime_routing_target),
    ]
    for name, fn in async_tests:
        try:
            await fn()
            print(f"PASS {name}")
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            print(f"FAIL {name}: {exc}")

    if failures:
        print(f"\n{len(failures)} test(s) failed.")
        return 1
    print(f"\nAll {len(sync_tests) + len(async_tests)} tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
