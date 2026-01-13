"""
Regression tests (script-based) for anti-hallucination retail-asset formatting.

Run:
  python test_fee_engine_verbatim.py
"""

import sys
from pathlib import Path


# Ensure `app/` is importable when running from repo root or this folder.
this_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(this_dir))


def _make_client():
    from app.services.fee_engine_client import FeeEngineClient

    return FeeEngineClient()


def test_retail_asset_found_uses_answer_text_verbatim():
    client = _make_client()
    answer = "Additional 1.50% interest on overdue amount"
    result = {
        "status": "FOUND",
        "charges": [
            {
                "loan_product": "OTHER_CHARGES",
                "loan_product_name": "Other Charges",
                "charge_type": "PENAL_INTEREST",
                "charge_title": "Penal Interest on loan",
                "charge_description": "Penal Interest",
                "answer_text": answer,
            }
        ],
    }

    text = client._format_retail_asset_charge_response(result, query="penal interest fee on loan")
    assert answer in text, f"Expected answer_text verbatim in output. Got: {text!r}"
    assert "Fee (as per schedule):" in text, f"Expected deterministic label in output. Got: {text!r}"


def test_retail_asset_found_missing_answer_text_is_deterministic_not_available():
    client = _make_client()
    result = {
        "status": "FOUND",
        "charges": [
            {
                "loan_product": "FAST_CASH_OD",
                "loan_product_name": "Fast Cash OD",
                "charge_type": "PROCESSING_FEE",
                "charge_title": "Processing Fee",
                "charge_description": "Processing Fee on loan amount",
                "answer_text": None,
                "fee_text": None,
                "original_charge_text": None,
            }
        ],
    }

    text = client._format_retail_asset_charge_response(result, query="processing fee on loan amount")
    assert "not available in the Retail Asset Charges Schedule" in text, f"Expected deterministic not-available. Got: {text!r}"


def test_retail_asset_disambiguation_prefers_answer_text_in_options():
    client = _make_client()
    result = {
        "status": "NEEDS_DISAMBIGUATION",
        "charges": [
            {
                "loan_product": "FAST_CASH_OD",
                "loan_product_name": "Fast Cash OD",
                "charge_type": "PROCESSING_FEE",
                "charge_description": "Processing Fee on limit",
                "answer_text": "0.50% on limit",
            },
            {
                "loan_product": "FAST_CASH_OD",
                "loan_product_name": "Fast Cash OD",
                "charge_type": "PROCESSING_FEE",
                "charge_description": "Processing Fee on enhanced amount",
                "answer_text": "0.75% on enhanced amount",
            },
        ],
        "message": "Multiple charges found.",
    }

    msg = client._format_retail_asset_disambiguation_response(result, query="processing fee fast cash")
    assert "0.50% on limit" in msg and "0.75% on enhanced amount" in msg, f"Expected answer_text in options. Got: {msg!r}"


if __name__ == "__main__":
    # Simple runner
    tests = [
        test_retail_asset_found_uses_answer_text_verbatim,
        test_retail_asset_found_missing_answer_text_is_deterministic_not_available,
        test_retail_asset_disambiguation_prefers_answer_text_in_options,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"[PASS] {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"[FAIL] {t.__name__}: {e}")
    raise SystemExit(1 if failed else 0)

