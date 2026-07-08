"""Tests for follow-up card-product option number recovery."""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_orchestrator import ChatOrchestrator


def _orch() -> ChatOrchestrator:
    return ChatOrchestrator(
        openai_client=MagicMock(),
        redis_cache=MagicMock(),
        lightrag_client=MagicMock(),
        fee_engine_client=MagicMock(),
        location_client=MagicMock(),
    )


def test_is_bare_option_number():
    o = _orch()
    assert o._is_bare_option_number("9")
    assert o._is_bare_option_number("11.")
    assert o._is_bare_option_number(" 2) ")
    assert not o._is_bare_option_number("tell me about fees")
    assert not o._is_bare_option_number("9 titanium")


def test_extract_card_products_from_disambiguation_text():
    o = _orch()
    text = """
Interest Rate is BDT 0.25 per year for all listed card products.

Which card would you like details for? Reply with the number or product name:

1. Army/Air Force/ Navy Platinum
2. Classic
9. Titanium
11. World

Reply with the number (e.g., 1) or the product name.
"""
    numbered = o._extract_numbered_card_products(text)
    assert numbered[1] == "Army/Air Force/ Navy Platinum"
    assert numbered[9] == "Titanium"
    assert numbered[11] == "World"
    products = o._extract_card_products_from_disambiguation_text(text)
    assert products[0] == "Army/Air Force/ Navy Platinum"
    assert products[8] == "Titanium"
    assert products[10] == "World"


def test_recover_from_history_after_cleared_state():
    o = _orch()
    history = [
        {"role": "user", "message": "tell me about credit card interest rate"},
        {
            "role": "assistant",
            "message": (
                "Please specify which card product you mean.\n\n"
                "Which card would you like details for?\n\n"
                "1. Classic\n"
                "2. Gold\n"
                "9. Titanium\n"
                "11. World\n"
            ),
        },
        {"role": "user", "message": "11"},
        {"role": "assistant", "message": "2.08% per month (25.00% per annum)"},
    ]
    recovered = o._recover_card_product_options_from_history(history, "9")
    assert recovered is not None
    assert recovered["chosen_product"] == "Titanium"
    assert "interest rate" in recovered["base_query"].lower()


def test_recover_skips_non_numeric_queries():
    o = _orch()
    history = [
        {"role": "user", "message": "interest rate"},
        {
            "role": "assistant",
            "message": "Which card?\n1. Classic\n2. Gold\n",
        },
    ]
    assert o._recover_card_product_options_from_history(history, "how to apply") is None


async def _test_card_product_keeps_state_after_selection():
    o = _orch()
    o._get_card_rates_context = AsyncMock(return_value="FEE ANSWER FOR WORLD")
    o._store_disambiguation_state_any = AsyncMock()
    o._persist_turn = AsyncMock()
    o._clear_disambiguation_state_any = AsyncMock()

    pending = {
        "product_line": "CREDIT_CARDS",
        "charge_type": "INTEREST_RATE",
        "disambiguation_type": "CARD_PRODUCT",
        "options": [
            {"card_product": "World", "card_product_name": "World"},
            {"card_product": "Titanium", "card_product_name": "Titanium"},
        ],
        "prompt_message": "pick a card",
        "extra": {"base_query": "credit card interest rate"},
    }
    # Force resolve_selection path via number 1 → World
    result = await o._handle_disambiguation_resolution(
        query="1",
        conversation_key="ck",
        session_id="sid",
        pending_disambiguation=pending,
        user_id="alice",
    )
    assert result is not None
    assert "FEE ANSWER FOR WORLD" in result["response"]
    # Must refresh state, not wipe it, so follow-up "2" still works
    o._clear_disambiguation_state_any.assert_not_called()
    o._store_disambiguation_state_any.assert_awaited()


def test_card_product_keeps_state_after_selection():
    asyncio.run(_test_card_product_keeps_state_after_selection())


def main():
    tests = [
        test_is_bare_option_number,
        test_extract_card_products_from_disambiguation_text,
        test_recover_from_history_after_cleared_state,
        test_recover_skips_non_numeric_queries,
        test_card_product_keeps_state_after_selection,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL: {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
