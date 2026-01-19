"""
Routing regression tests (holistic).

This suite verifies that common operational/policy/location queries route to the right backend path:
- Fee Engine (deterministic) only for fee/charge/rate questions
- Location service for ATM/branch location/count questions
- Phonebook only for employee contact lookups (NOT staffing requirements)
- LightRAG for policies/procedures/eligibility/limits/etc.

Run (from repo root):
  python bank_chatbot/test_routing_regression.py
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Optional, List

import httpx


ROUTE_DEBUG_URL = "http://localhost:8001/api/debug/route"
HEALTH_URL = "http://localhost:8001/api/health"


@dataclass(frozen=True)
class RoutingCase:
    name: str
    query: str
    expected_target: str
    expected_kb: Optional[str] = None  # if set, must match


CASES: List[RoutingCase] = [
    RoutingCase(
        name="StaffingRequirement_AgentOutlet",
        query="How many staff are required for customer service and cash transactions from the Agent's side, and how many Bank staff are required at the outlet?",
        expected_target="LIGHTRAG",
        expected_kb="ebl_products",
    ),
    RoutingCase(
        name="SavingsCashWithdrawalDailyTxnLimit",
        query="What is the maximum number of daily Cash Withdrawal transactions allowed for a Savings Account?",
        expected_target="LIGHTRAG",
        expected_kb="ebl_products",
    ),
    RoutingCase(
        name="ATM_Location_HeadOffice",
        query="Give me location of EBL Head office ATM",
        expected_target="LOCATION_SERVICE",
    ),
    RoutingCase(
        name="ATM_Count_Shyamoli",
        query="Tell me number of ATM in Shyamoli area with Location",
        expected_target="LOCATION_SERVICE",
    ),
    RoutingCase(
        name="PayrollDebitCardIssuanceFee_CategoryB",
        query="What is the Debit Card Issuance Fee for Category B Payroll Banking?",
        expected_target="LIGHTRAG",
        expected_kb="ebl_products",
    ),
    RoutingCase(
        name="EasyCreditEarlySettlementProcess",
        query="EasyCredit Early Settlement process",
        expected_target="LIGHTRAG",
        expected_kb="ebl_products",
    ),
]


def _get_route(query: str) -> dict:
    with httpx.Client(timeout=30) as client:
        r = client.get(ROUTE_DEBUG_URL, params={"query": query})
        r.raise_for_status()
        return r.json()


def _wait_for_health(timeout_seconds: int = 30) -> None:
    """Wait until backend is healthy after restarts."""
    deadline = time.time() + timeout_seconds
    with httpx.Client(timeout=5) as client:
        while time.time() < deadline:
            try:
                r = client.get(HEALTH_URL)
                if r.status_code == 200:
                    return
            except Exception:
                pass
            time.sleep(1)
    raise RuntimeError("Backend did not become healthy in time")


def main() -> int:
    _wait_for_health(timeout_seconds=45)

    failures = []
    for c in CASES:
        decision = _get_route(c.query)
        target = decision.get("target")
        kb = decision.get("knowledge_base")

        ok = True
        if target != c.expected_target:
            ok = False
        if c.expected_kb is not None and kb != c.expected_kb:
            ok = False

        if ok:
            print(f"[PASS] {c.name}")
        else:
            print(f"[FAIL] {c.name}")
            failures.append(
                {
                    "case": c.name,
                    "query": c.query,
                    "expected_target": c.expected_target,
                    "actual_target": target,
                    "expected_kb": c.expected_kb,
                    "actual_kb": kb,
                    "signals": decision.get("signals", {}),
                }
            )

    if failures:
        print("\n=== FAILURES ===")
        print(json.dumps(failures, indent=2, ensure_ascii=False))
        return 1

    print("\nAll routing regression tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

