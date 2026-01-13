"""
Card-fee "anti-hallucination" regression tests.

These tests call the running bank-chatbot API and assert:
- The response contains authoritative fee text (from fee engine / answer_text / note text)
- The response does NOT contain common hallucination artifacts.

Run (from repo root):
  python bank_chatbot/test_card_fee_hallucination.py

Prereqs:
  - Docker containers running: bank-chatbot-api, fee-engine-service, chatbot_postgres
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import List, Optional

import httpx


CHATBOT_URL = "http://localhost:8001/api/chat"


FORBIDDEN_SUBSTRINGS = [
    "Migrated from card_charges.json",
    "₹",  # wrong currency symbol
    "{note_ref}",  # formatting bug
]


@dataclass(frozen=True)
class Case:
    name: str
    query: str
    must_contain: List[str]
    must_not_contain: List[str]
    session_id: Optional[str] = None


CASES: List[Case] = [
    Case(
        name="NavyPlatinumPrimaryAnnualFee",
        query="tell me Navy Platinum annual fee for primary cardholder",
        must_contain=["BDT 4,600.00 per year"],
        must_not_contain=["BDT 5,750", *FORBIDDEN_SUBSTRINGS],
    ),
    Case(
        name="VisaClassicDebitTransactionAlertNoteText",
        query="tell me annual Transaction Alert Fee for visa classic debit card",
        must_contain=[
            "Note Reference: 49",
            "EBL Account transaction alert fee",
            "Page-02 of the EBL Retail Banking Charges",
        ],
        must_not_contain=[*FORBIDDEN_SUBSTRINGS],
    ),
    Case(
        name="UnionPayPlatinumPrimaryAnnualFee",
        query="UnionPay Platinum annual fee for primary cardholder",
        must_contain=["BDT 5,750.00 per year"],
        must_not_contain=[*FORBIDDEN_SUBSTRINGS],
    ),
    Case(
        name="VisaClassicCreditAnnualFee",
        query="VISA Classic credit card annual fee",
        must_contain=["BDT 1,725.00 per year"],
        must_not_contain=[*FORBIDDEN_SUBSTRINGS],
    ),
    Case(
        name="UnionPayDebitIssuanceNoProduct",
        query="What is the issuance fee for a Union pay Debit card ?",
        must_contain=["BDT 575"],
        must_not_contain=[*FORBIDDEN_SUBSTRINGS],
    ),
    Case(
        name="VisaClassicCreditChequebook10Leaves",
        query="Card chequebook charge amount (10 leaves) for credit card VISA classic",
        must_contain=["BDT 287.50"],
        must_not_contain=[*FORBIDDEN_SUBSTRINGS],
    ),
    Case(
        name="VisaClassicRiskAssuranceRate",
        query="Risk Assurance charge amount on outstanding for credit card VISA classic",
        must_contain=["0.0035 on outstanding balance"],
        must_not_contain=[*FORBIDDEN_SUBSTRINGS],
    ),
    Case(
        name="MastercardTitaniumOverlimit",
        query="Over limit charge amount in EBL MASTERCARD TITANIUM CREDIT CARD",
        must_contain=["BDT 1,782.50 / USD 17.25 per transaction"],
        must_not_contain=["USD 0.00", *FORBIDDEN_SUBSTRINGS],
    ),
]


def _post_chat(query: str, session_id: Optional[str] = None) -> str:
    payload = {"query": query, "stream": False}
    if session_id:
        payload["session_id"] = session_id
    with httpx.Client(timeout=30) as client:
        r = client.post(CHATBOT_URL, json=payload)
        r.raise_for_status()
        data = r.json()
        return data.get("response", "")


def main() -> int:
    # Simple wait to reduce flakiness right after restarts
    time.sleep(1)

    failures = []
    for c in CASES:
        resp = _post_chat(c.query, session_id=c.session_id)

        missing = [s for s in c.must_contain if s not in resp]
        forbidden = [s for s in c.must_not_contain if s and s in resp]

        if missing or forbidden:
            failures.append(
                {
                    "case": c.name,
                    "query": c.query,
                    "missing": missing,
                    "forbidden_found": forbidden,
                    "response_preview": resp[:1200],
                }
            )
            print(f"[FAIL] {c.name}")
        else:
            print(f"[PASS] {c.name}")

    if failures:
        print("\n=== FAILURES (details) ===")
        print(json.dumps(failures, indent=2, ensure_ascii=False))
        return 1

    # Two-turn disambiguation test: missing card_product must ask, then resolve.
    disambig_session = "test_disambiguation_card_product"
    first = _post_chat("What is the issuance fee for a VISA credit card?", session_id=disambig_session)
    if "To answer, please specify the card product" not in first or "Classic" not in first:
        print("[FAIL] CardProductDisambiguationPrompt")
        print(first[:1200])
        return 1
    second = _post_chat("Classic", session_id=disambig_session)
    if "BDT 1,725.00 per year" not in second:
        print("[FAIL] CardProductDisambiguationResolved")
        print(second[:1200])
        return 1
    print("[PASS] CardProductDisambiguation (2-turn)")

    print("\nAll card-fee anti-hallucination tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

