"""
Shared helpers for fee-schedule query intent and synonym normalization.

Users often say "rate" or "charge" where the official schedule uses "fee"
(e.g. "cib rate" means the same as "cib fee"). Normalization avoids
hardcoding every {charge_name} + rate variant.
"""

from __future__ import annotations

import re

_INTEREST_RATE_PATTERNS = (
    r"\binterest\s+rate\b",
    r"\brate\s+of\s+interest\b",
    r"\bapr\b",
    r"\bannual\s+percentage\s+rate\b",
)

# Bare "credit card rate" often means APR/interest — do not rewrite to "credit card fee".
_CREDIT_CARD_RATE = re.compile(r"\bcredit\s+card\s+rate\b")

_SCHEDULE_FEE_INTENT_WORDS = (
    "fee", "fees", "charge", "charges", "cost", "pricing", "price", "rate",
)


def is_interest_rate_query(query_lower: str) -> bool:
    return any(re.search(p, query_lower) for p in _INTEREST_RATE_PATTERNS)


def normalize_fee_query_for_matching(query: str) -> str:
    """
    Normalize phrasing for fee-schedule keyword matching.

    Examples:
        "cib rate for credit card" -> "cib fee for credit card"
        "interest rate for visa"   -> unchanged
    """
    q = (query or "").lower().strip()
    if not q:
        return q
    if is_interest_rate_query(q):
        return q
    if _CREDIT_CARD_RATE.search(q) and "interest" not in q:
        return q
    return re.sub(r"\brate\b", "fee", q)


def has_schedule_fee_intent(query_lower: str) -> bool:
    """True when the query asks about a schedule fee/charge/rate (incl. interest rate)."""
    q = (query_lower or "").lower().strip()
    if is_interest_rate_query(q):
        return True
    return any(w in q for w in _SCHEDULE_FEE_INTENT_WORDS)
