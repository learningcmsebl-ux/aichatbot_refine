"""
Optional application-layer encryption-at-rest for stored chat message content.

Behaviour:
- If ``settings.CHAT_HISTORY_ENCRYPTION_KEY`` is set (a valid Fernet key) and the
  ``cryptography`` package is installed, message text is encrypted on write and
  transparently decrypted on read.
- If no key is configured (default), text is stored/returned as plaintext. This
  keeps the feature opt-in and preserves all existing rows.
- Decryption is tolerant: rows that were written as plaintext (legacy or when the
  feature was disabled) are returned unchanged, so mixed datastores keep working.

Encrypted values are tagged with a short prefix so we can distinguish them from
plaintext without a schema change.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Marker prepended to ciphertext so reads can detect encrypted vs plaintext rows.
_ENC_PREFIX = "enc:v1:"

_fernet = None
_init_done = False


def _get_fernet():
    """Lazily build the Fernet cipher from settings; cache the result."""
    global _fernet, _init_done
    if _init_done:
        return _fernet
    _init_done = True

    key = (settings.CHAT_HISTORY_ENCRYPTION_KEY or "").strip()
    if not key:
        _fernet = None
        return None
    try:
        from cryptography.fernet import Fernet

        _fernet = Fernet(key.encode("utf-8"))
        logger.info("[CRYPTO] Chat history encryption-at-rest is ENABLED")
    except Exception as exc:  # invalid key or missing dependency
        logger.error(
            "[CRYPTO] CHAT_HISTORY_ENCRYPTION_KEY is set but encryption could not "
            "be initialised (%s); storing plaintext. Fix the key or install "
            "'cryptography' to enable encryption.",
            exc,
        )
        _fernet = None
    return _fernet


def encryption_enabled() -> bool:
    return _get_fernet() is not None


def encrypt_text(text: Optional[str]) -> Optional[str]:
    """Encrypt text for storage. No-op (returns input) when encryption is off."""
    if text is None:
        return None
    fernet = _get_fernet()
    if fernet is None:
        return text
    try:
        token = fernet.encrypt(text.encode("utf-8")).decode("utf-8")
        return _ENC_PREFIX + token
    except Exception as exc:
        logger.error("[CRYPTO] Encryption failed, storing plaintext: %s", exc)
        return text


def decrypt_text(value: Optional[str]) -> Optional[str]:
    """
    Decrypt a stored value. Returns plaintext values unchanged so legacy/mixed
    rows keep working even after encryption is enabled.
    """
    if value is None:
        return None
    if not value.startswith(_ENC_PREFIX):
        return value  # plaintext row (feature was off when written)
    fernet = _get_fernet()
    if fernet is None:
        # Key was removed/rotated away — cannot decrypt; avoid leaking ciphertext.
        logger.warning("[CRYPTO] Encrypted row found but no key configured to decrypt")
        return "[unavailable]"
    try:
        token = value[len(_ENC_PREFIX):]
        return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        logger.error("[CRYPTO] Decryption failed: %s", exc)
        return "[unavailable]"
