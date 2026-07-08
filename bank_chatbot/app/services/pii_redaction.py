"""
Sensitive banking data redaction for stored chat history.

This module scrubs highly sensitive values from message text *before* it is
persisted to the database (chat history and analytics). It is intentionally
conservative so that legitimate banking content (fee amounts like "BDT 2,300",
interest rates, phone/branch numbers) is preserved while true secrets are masked.

Security requirement: we must NEVER store OTPs, passwords, PINs, CVVs, full card
numbers, or full account numbers. When in doubt we mask, keeping only enough of
the value (e.g. last 4 digits of a card) for the conversation to still read
naturally.

The redaction is one-way and applied on write, so redacted secrets are never
recoverable from the datastore even by an authorized reader.
"""

from __future__ import annotations

import re
from typing import List, Tuple

# Ordered list of (compiled_pattern, replacement_builder). Each replacement
# receives the regex match and returns the masked string.
_MASK = "[REDACTED]"


def _mask_keep_last4(digits: str) -> str:
    """Mask a numeric secret, keeping only the final 4 digits for readability."""
    cleaned = re.sub(r"\D", "", digits)
    if len(cleaned) <= 4:
        return "****"
    return "*" * (len(cleaned) - 4) + cleaned[-4:]


# --- Keyword-driven secrets (OTP / password / PIN / CVV) --------------------
# Match "<keyword> [is/:/=] <value>" and mask the value only.
_KEYWORD_SECRET_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # One-time passwords / verification codes: 4-8 digits after the keyword.
    (
        re.compile(
            r"\b(otp|one[\s-]?time[\s-]?password|verification code|security code|passcode)\b"
            r"\s*(?:is|:|=|-)?\s*['\"]?\d{4,8}['\"]?",
            re.IGNORECASE,
        ),
        r"\1: " + _MASK,
    ),
    # Passwords / passphrases: mask the following non-space token.
    (
        re.compile(
            r"\b(password|passwd|pwd|passphrase)\b\s*(?:is|:|=|-)?\s*\S+",
            re.IGNORECASE,
        ),
        r"\1: " + _MASK,
    ),
    # PIN: 3-6 digits.
    (
        re.compile(
            r"\b(pin(?:\s*(?:code|number|no))?)\b\s*(?:is|:|=|-)?\s*['\"]?\d{3,6}['\"]?",
            re.IGNORECASE,
        ),
        r"\1: " + _MASK,
    ),
    # CVV / CVC / CVN: 3-4 digits.
    (
        re.compile(
            r"\b(cvv|cvc|cvv2|cvn|card verification (?:value|code))\b\s*(?:is|:|=|-)?\s*['\"]?\d{3,4}['\"]?",
            re.IGNORECASE,
        ),
        r"\1: " + _MASK,
    ),
]

# --- Account number: keyword-driven (avoids masking fee amounts) ------------
# e.g. "account number 1234567890", "a/c no: 0011-2233-4455". Requires >= 8 digits.
_ACCOUNT_PATTERN = re.compile(
    r"\b(a/?c|acct|account)\b(?:\s*(?:no\.?|number|#))?\s*(?:is|:|=|-)?\s*"
    r"((?:\d[\s-]?){8,20})",
    re.IGNORECASE,
)

# --- Card number: 13-19 digits, optionally grouped by spaces/dashes ---------
# Card PANs are long (13-19 digits); this length window avoids matching money
# amounts or phone numbers. We keep the last 4 digits.
_CARD_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def _redact_account(match: re.Match) -> str:
    keyword = match.group(1)
    return f"{keyword} {_mask_keep_last4(match.group(2))}"


def _redact_card(match: re.Match) -> str:
    return _mask_keep_last4(match.group(0))


def redact_sensitive(text: str) -> str:
    """
    Return a copy of ``text`` with sensitive banking secrets masked.

    Safe to call on any message; returns the input unchanged when nothing
    sensitive is detected. Never raises — redaction failures must not block
    a chat turn, but callers should treat a failure as "do not store raw".
    """
    if not text:
        return text

    result = text

    # 1) Keyword-driven secrets (OTP, password, PIN, CVV).
    for pattern, replacement in _KEYWORD_SECRET_PATTERNS:
        result = pattern.sub(replacement, result)

    # 2) Card numbers (long digit runs) — mask keeping last 4.
    result = _CARD_PATTERN.sub(_redact_card, result)

    # 3) Account numbers (keyword-driven) — mask keeping last 4.
    result = _ACCOUNT_PATTERN.sub(_redact_account, result)

    return result
