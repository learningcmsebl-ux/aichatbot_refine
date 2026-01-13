"""
DB-driven intensive card-fee anti-hallucination tests.

This script:
1) Reads ACTIVE CREDIT_CARDS rules from Postgres (card_fee_master)
2) Generates a natural-language query for each rule
3) Calls bank-chatbot-api (/api/chat, non-stream)
4) Asserts the response contains the authoritative answer_text (or special invariants)
5) Flags common hallucination artifacts

Run:
  python bank_chatbot/test_card_fee_hallucination_db_driven.py

Env overrides (optional):
  CHATBOT_URL=http://localhost:8001/api/chat
  PGHOST=localhost
  PGPORT=5432
  PGDATABASE=chatbot_db
  PGUSER=chatbot_user
  PGPASSWORD=chatbot_password_123
  MAX_CASES=0            # 0 = all (default)
  CONCURRENCY=12
  FAIL_FAST=0            # 1 = stop on first failure
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
import psycopg2


CHATBOT_URL = os.getenv("CHATBOT_URL", "http://localhost:8001/api/chat")

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "chatbot_db")
PGUSER = os.getenv("PGUSER", "chatbot_user")
PGPASSWORD = os.getenv("PGPASSWORD", "chatbot_password_123")

MAX_CASES = int(os.getenv("MAX_CASES", "0"))  # 0 = all
CONCURRENCY = int(os.getenv("CONCURRENCY", "4"))
FAIL_FAST = os.getenv("FAIL_FAST", "0") == "1"


FORBIDDEN_SUBSTRINGS = [
    "Migrated from card_charges.json",
    "₹",  # wrong currency symbol
    "{note_ref}",  # formatting bug
]


@dataclass(frozen=True)
class Rule:
    fee_id: str
    charge_type: str
    card_category: str
    card_network: str
    card_product: str
    full_card_name: str
    fee_value: float
    fee_unit: str
    condition_type: str
    note_reference: Optional[str]
    answer_text: str


def _pg_connect():
    return psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        dbname=PGDATABASE,
        user=PGUSER,
        password=PGPASSWORD,
    )


def load_rules() -> List[Rule]:
    sql = """
    SELECT
      fee_id::text,
      charge_type,
      card_category,
      card_network,
      card_product,
      COALESCE(full_card_name, '') AS full_card_name,
      fee_value,
      fee_unit,
      condition_type,
      note_reference,
      COALESCE(answer_text, '') AS answer_text
    FROM card_fee_master
    WHERE status = 'ACTIVE'
      AND product_line = 'CREDIT_CARDS'
    ORDER BY
      charge_type,
      card_category,
      card_network,
      card_product,
      priority DESC,
      fee_value DESC;
    """
    with _pg_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()

    rules: List[Rule] = []
    has_specific_product: set[Tuple[str, str, str]] = set()
    for r in rows:
        ct = r[1]
        cat = r[2]
        net = r[3]
        prod = (r[4] or "").strip()
        if prod and prod.upper() != "ANY":
            has_specific_product.add((ct, cat, net))

    seen_keys: set[Tuple[str, str, str, str]] = set()
    for r in rows:
        full_card_name = (r[5] or "").strip()

        # Skip legacy FX rows that were canonicalized to VISA network but don't behave like VISA
        # (these cause false-failures when generating "VISA ..." queries).
        if "fx" in full_card_name.lower():
            continue

        # Skip "ANY" product rows when more specific products exist for the same charge/category/network.
        # With card-product disambiguation enabled, these generic rows are not reliably reachable
        # from a natural-language query (and are primarily for fallback/legacy).
        prod = (r[4] or "ANY").strip() or "ANY"
        if prod.upper() == "ANY" and (r[1], r[2], r[3]) in has_specific_product:
            continue

        # De-dupe exact lookup collisions to mirror fee-engine selection:
        # fee-engine orders by priority DESC, then fee_value DESC.
        # If multiple ACTIVE rows collide on lookup keys, only the "winning" row can ever be returned.
        key = (r[1], r[2], r[3], prod)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        rules.append(
            Rule(
                fee_id=r[0],
                charge_type=r[1],
                card_category=r[2],
                card_network=r[3],
                card_product=prod,
                full_card_name=full_card_name,
                fee_value=float(r[6]) if r[6] is not None else 0.0,
                fee_unit=str(r[7] or ""),
                condition_type=r[8],
                note_reference=r[9],
                answer_text=(r[10] or "").strip(),
            )
        )
    return rules


CHARGE_TYPE_QUERY_PHRASE: Dict[str, str] = {
    "ISSUANCE_ANNUAL_PRIMARY": "annual fee for primary cardholder",
    "SUPPLEMENTARY_FREE_ENTITLEMENT": "how many free supplementary cards",
    "SUPPLEMENTARY_ANNUAL": "supplementary card annual fee",
    "TRANSACTION_ALERT_ANNUAL": "annual transaction alert fee",
    "CASH_WITHDRAWAL_EBL_ATM": "EBL ATM cash withdrawal fee",
    "CASH_WITHDRAWAL_OTHER_ATM": "other bank ATM cash withdrawal fee",
    "CARD_REPLACEMENT": "card replacement fee",
    "PIN_REPLACEMENT": "PIN replacement fee",
    "OVERLIMIT": "overlimit fee",
    "LATE_PAYMENT": "late payment fee",
    "CERTIFICATE_FEE": "certificate fee",
    "DUPLICATE_ESTATEMENT": "duplicate e-statement fee per month",
    "GLOBAL_LOUNGE_ACCESS_FEE": "global lounge access fee per individual",
    "GLOBAL_LOUNGE_FREE_VISITS_ANNUAL": "number of global lounge free visit annual",
    "SKYLOUNGE_FREE_VISITS_DOM_ANNUAL": "number of domestic skylounge free visit annual",
    "SKYLOUNGE_FREE_VISITS_INTL_ANNUAL": "number of international skylounge free visit annual",
    "ATM_RECEIPT_EBL": "ATM receipt fee",
    "ATM_CCTV_FOOTAGE_INSIDE_DHAKA": "ATM CCTV footage fee inside Dhaka",
    "ATM_CCTV_FOOTAGE_OUTSIDE_DHAKA": "ATM CCTV footage fee outside Dhaka",
    "CARD_CHEQUE_PROCESSING": "card cheque processing fee",
    "CARD_CHEQUBOOK": "card chequebook fee 10 leaves",
    "CUSTOMER_VERIFICATION_CIB": "customer verification CIB fee",
    "SALES_VOUCHER_RETRIEVAL": "sales voucher retrieval fee",
    "RETURN_CHEQUE_FEE": "return cheque fee",
    "UNDELIVERED_CARD_FEE": "undelivered card pin destruction fee",
    "RISK_ASSURANCE_FEE": "risk assurance fee on outstanding balance 100000 BDT",
    "FUND_TRANSFER_FEE": "fund transfer fee",
    "WALLET_TRANSFER_FEE": "wallet transfer fee add money",
    "INTEREST_RATE": "interest rate annual",
}


def build_query(rule: Rule) -> str:
    # Category words
    category_phrase = {
        "CREDIT": "credit card",
        "DEBIT": "debit card",
        "PREPAID": "prepaid card",
        "ANY": "card",
    }.get(rule.card_category.upper(), "card")

    # Network words
    network_phrase = {
        "VISA": "VISA",
        "MASTERCARD": "Mastercard",
        "DINERS": "Diners",
        "UNIONPAY": "UnionPay",
        "TAKAPAY": "TakaPay",
        "ANY": "",
    }.get(rule.card_network.upper(), rule.card_network)

    # Product words
    product_phrase = "" if (rule.card_product or "").upper() in ["ANY", ""] else rule.card_product

    # Charge phrase
    charge_phrase = CHARGE_TYPE_QUERY_PHRASE.get(rule.charge_type, rule.charge_type.replace("_", " ").lower() + " fee")

    currency_hint = ""
    # If the rule is USD-based, force the chatbot to request USD explicitly.
    if (rule.fee_unit or "").upper() == "USD":
        currency_hint = "in USD"

    parts = [p for p in [network_phrase, product_phrase, category_phrase, charge_phrase, currency_hint] if p and p.strip()]
    return " ".join(parts)


def _normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def assert_expected(rule: Rule, response_text: str) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    resp = response_text or ""

    for bad in FORBIDDEN_SUBSTRINGS:
        if bad in resp:
            issues.append(f"forbidden_substring:{bad}")

    # Special invariants
    if rule.charge_type == "CASH_WITHDRAWAL_EBL_ATM":
        if "2.5% or BDT 345" not in resp:
            issues.append("missing_invariant:EBL_ATM_withdrawal_format")

    # Primary check: answer_text should appear (for almost all rules now).
    ans = rule.answer_text
    if ans:
        if _normalize_text(ans) not in _normalize_text(resp):
            # For NOTE_BASED, allow match on Note Reference line when answer_text is a note text.
            if rule.condition_type == "NOTE_BASED" and rule.note_reference:
                if f"Note Reference: {rule.note_reference}" not in resp and f"Note {rule.note_reference}" not in resp:
                    issues.append("missing_answer_text_or_note_ref")
            else:
                issues.append("missing_answer_text")
    else:
        issues.append("db_answer_text_empty")

    return (len(issues) == 0), issues


async def call_chat(client: httpx.AsyncClient, query: str, session_id: str) -> str:
    # IMPORTANT: Always provide a unique session_id so disambiguation state
    # (stored by conversation_key/session_id) does not leak across test cases.
    payload = {"query": query, "stream": False, "session_id": session_id}
    last_err: Optional[Exception] = None
    for attempt in range(1, 7):
        try:
            r = await client.post(CHATBOT_URL, json=payload)
            r.raise_for_status()
            data = r.json()
            return data.get("response", "")
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as e:
            last_err = e
            # brief backoff for transient read/connection errors
            await asyncio.sleep(0.2 * attempt)
            continue
    raise RuntimeError(f"chat_call_failed after retries: {type(last_err).__name__}: {last_err}")


async def run() -> int:
    rules = load_rules()
    if MAX_CASES and MAX_CASES > 0:
        rules = rules[:MAX_CASES]

    sem = asyncio.Semaphore(max(1, CONCURRENCY))

    failures: List[Dict[str, Any]] = []
    passed = 0

    async with httpx.AsyncClient(timeout=60) as client:
        async def one(rule: Rule):
            nonlocal passed
            q = build_query(rule)
            resp = ""
            try:
                async with sem:
                    resp = await call_chat(client, q, session_id=f"dbdriven:{rule.fee_id}")
            except Exception as e:
                failure = {
                    "fee_id": rule.fee_id,
                    "charge_type": rule.charge_type,
                    "card_category": rule.card_category,
                    "card_network": rule.card_network,
                    "card_product": rule.card_product,
                    "condition_type": rule.condition_type,
                    "note_reference": rule.note_reference,
                    "query": q,
                    "answer_text": rule.answer_text,
                    "issues": [f"http_error:{type(e).__name__}"],
                    "response_preview": "",
                }
                failures.append(failure)
                if FAIL_FAST:
                    raise RuntimeError(json.dumps(failure, ensure_ascii=False, indent=2))
                return

            ok, issues = assert_expected(rule, resp)
            if ok:
                passed += 1
                return

            failure = {
                "fee_id": rule.fee_id,
                "charge_type": rule.charge_type,
                "card_category": rule.card_category,
                "card_network": rule.card_network,
                "card_product": rule.card_product,
                "condition_type": rule.condition_type,
                "note_reference": rule.note_reference,
                "query": q,
                "answer_text": rule.answer_text,
                "issues": issues,
                "response_preview": (resp or "")[:1200],
            }
            failures.append(failure)
            if FAIL_FAST:
                raise RuntimeError(json.dumps(failure, ensure_ascii=False, indent=2))

        tasks = [asyncio.create_task(one(r)) for r in rules]
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            # fail-fast already printed via exception message
            print("[FAIL_FAST_TRIGGERED]")
            print(str(e))
            return 1

    total = len(rules)
    print(f"\nSummary: {passed}/{total} passed, {len(failures)} failed.")

    if failures:
        # Print grouped summary by charge_type
        by_ct: Dict[str, int] = {}
        for f in failures:
            by_ct[f["charge_type"]] = by_ct.get(f["charge_type"], 0) + 1
        print("\nFailures by charge_type:")
        for ct in sorted(by_ct.keys()):
            print(f"- {ct}: {by_ct[ct]}")

        print("\n=== Sample failures (up to 20) ===")
        print(json.dumps(failures[:20], ensure_ascii=False, indent=2))
        return 1

    return 0


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())

