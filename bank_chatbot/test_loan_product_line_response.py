"""
Regression test: broad loan queries should return loan product lines (not bank overview).

Run (from repo root):
  python bank_chatbot/test_loan_product_line_response.py
"""

from __future__ import annotations

import time
import httpx


HEALTH_URL = "http://localhost:8001/api/health"
CHAT_URL = "http://localhost:8001/api/chat"


def _wait_for_health(timeout_seconds: int = 30) -> None:
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

    query = "Tell me about EBL Loan product"
    with httpx.Client(timeout=30) as client:
        r = client.post(CHAT_URL, json={"query": query, "stream": False})
        r.raise_for_status()
        data = r.json()

    resp = (data.get("response") or "").strip()

    must_contain = [
        "loan product lines",
        "- Home Loan",
        "- Auto/Car Loan",
        "Which one do you want details on",
    ]
    missing = [s for s in must_contain if s not in resp]
    if missing:
        print("[FAIL] Missing expected substrings:")
        for m in missing:
            print(f"  - {m!r}")
        print("\nResponse was:\n" + resp)
        return 1

    # Ensure it isn't returning the generic org overview template.
    forbidden_markers = [
        "was established in",
        "operates in bangladesh",
        "core banking services including savings accounts",
    ]
    if any(m.lower() in resp.lower() for m in forbidden_markers):
        print("[FAIL] Response looks like bank overview (forbidden marker matched).")
        print("\nResponse was:\n" + resp)
        return 1

    print("[PASS] Broad loan query returned product-line list.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

