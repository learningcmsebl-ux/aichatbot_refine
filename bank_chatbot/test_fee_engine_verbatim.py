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


def test_card_context_wins_over_retail_cib_fee_keywords():
    client = _make_client()
    product_line = client._detect_product_line("cib fee for credit card")
    assert product_line == "CREDIT_CARDS", f"Expected CREDIT_CARDS, got {product_line}"


def test_cib_fee_for_credit_card_routes_to_fee_schedule():
    from app.services.handlers.query_classifier import QueryClassifier

    classifier = QueryClassifier()
    assert classifier.is_fee_schedule_query("tell me cib fee for credit card"), (
        "Card CIB fee query should route to fee engine, not LightRAG"
    )
    assert not classifier.is_retail_asset_fee_query("tell me cib fee for credit card"), (
        "Card CIB fee query should not route to retail asset fee engine"
    )
    assert classifier.is_retail_asset_fee_query("cib fee for executive loan"), (
        "Loan CIB fee query should still route to retail assets"
    )


def test_cib_verification_maps_to_customer_verification_charge_type():
    client = _make_client()
    charge_type = client._map_query_to_charge_type(
        "tell me about credit card cib verification fee",
        product_line="CREDIT_CARDS",
    )
    assert charge_type == "CUSTOMER_VERIFICATION_CIB", f"Expected CUSTOMER_VERIFICATION_CIB, got {charge_type}"


def test_card_replacement_disambiguation_shows_fee_tiers():
    client = _make_client()
    result = {
        "status": "NEEDS_DISAMBIGUATION",
        "charge_type": "CARD_REPLACEMENT",
        "options": [
            {
                "card_product": "Classic",
                "card_product_name": "Classic",
                "fee_amount": "1150.0000",
                "fee_currency": "BDT",
                "fee_basis": "PER_TXN",
                "fee_label": "BDT 1,150 per transaction",
            },
            {
                "card_product": "Platinum",
                "card_product_name": "Platinum",
                "fee_amount": "1380.0000",
                "fee_currency": "BDT",
                "fee_basis": "PER_TXN",
                "fee_label": "BDT 1,380 per transaction",
            },
        ],
    }
    text = client._format_card_fee_disambiguation_response(result)
    assert "varies by card product" in text
    assert "BDT 1,150" in text and "BDT 1,380" in text
    assert "Classic" in text and "Platinum" in text
    assert "Reply with the number" in text


def test_interest_rate_uniform_disambiguation_lists_products():
    client = _make_client()
    result = {
        "status": "NEEDS_DISAMBIGUATION",
        "charge_type": "INTEREST_RATE",
        "message": (
            "Interest Rate is 2.08% per month (25.00% per annum) for all listed card products. "
            "Please specify which card product you mean."
        ),
        "options": [
            {
                "card_product": "Classic",
                "card_product_name": "Classic",
                "fee_amount": "0.2500",
                "fee_currency": "BDT",
                "fee_basis": "PER_YEAR",
            },
            {
                "card_product": "Platinum",
                "card_product_name": "Platinum",
                "fee_amount": "0.2500",
                "fee_currency": "BDT",
                "fee_basis": "PER_YEAR",
            },
        ],
    }
    text = client._format_card_fee_disambiguation_response(
        result,
        query="tell me about credit card interest rate",
    )
    assert "Credit card Interest Rate:" in text
    assert "2.08% per month (25.00% per annum)" in text
    assert "Classic" in text and "Platinum" in text
    assert "Reply with the number" in text


def test_interest_rate_calculated_includes_product():
    client = _make_client()
    result = {
        "status": "CALCULATED",
        "charge_type": "INTEREST_RATE",
        "fee_amount": "0.2500",
        "fee_currency": "BDT",
        "fee_basis": "PER_YEAR",
        "card_product": "Platinum",
        "card_network": "VISA",
    }
    text = client.format_fee_response(result, query="visa platinum credit card interest rate")
    assert "For VISA Platinum credit card:" in text
    assert "2.08% per month (25.00% per annum)" in text


def test_interest_rate_uses_query_product_when_response_missing():
    client = _make_client()
    result = {
        "status": "CALCULATED",
        "charge_type": "INTEREST_RATE",
        "fee_amount": "0.2500",
        "fee_currency": "BDT",
        "fee_basis": "PER_YEAR",
        "card_product": None,
    }
    text = client.format_fee_response(
        result,
        query="tell me about credit card interest rate Corporate Platinum",
    )
    assert "Corporate Platinum" in text
    assert "2.08% per month (25.00% per annum)" in text


if __name__ == "__main__":
    tests = [
        test_retail_asset_found_uses_answer_text_verbatim,
        test_retail_asset_found_missing_answer_text_is_deterministic_not_available,
        test_retail_asset_disambiguation_prefers_answer_text_in_options,
        test_card_context_wins_over_retail_cib_fee_keywords,
        test_cib_fee_for_credit_card_routes_to_fee_schedule,
        test_cib_verification_maps_to_customer_verification_charge_type,
        test_card_replacement_disambiguation_shows_fee_tiers,
        test_interest_rate_uniform_disambiguation_lists_products,
        test_interest_rate_calculated_includes_product,
        test_interest_rate_uses_query_product_when_response_missing,
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

