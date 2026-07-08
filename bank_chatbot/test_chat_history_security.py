"""
Tests for secure per-user chat history:
- Sensitive banking data redaction before storage.
- Stable AD identity resolution (objectGUID preferred over username).
- Optional encryption helper round-trips / plaintext passthrough.
"""

import sys

from app.services.pii_redaction import redact_sensitive
from app.services.message_crypto import encrypt_text, decrypt_text
from app.models.auth import EmployeeUser


def test_redacts_card_number_keeps_last4():
    text = "My card number is 4111 1111 1111 1111 please help"
    out = redact_sensitive(text)
    assert "4111 1111 1111 1111" not in out
    assert out.endswith("1111 please help") or "1111" in out
    assert "*" in out


def test_redacts_cvv_pin_otp_password():
    assert "123" not in redact_sensitive("my CVV is 123")
    assert "4567" not in redact_sensitive("PIN: 4567")
    assert "998877" not in redact_sensitive("the otp is 998877")
    assert "hunter2" not in redact_sensitive("password: hunter2")


def test_redacts_account_number_keyword():
    out = redact_sensitive("account number 001122334455")
    assert "001122334455" not in out
    assert "4455" in out  # last 4 preserved


def test_preserves_fee_amounts():
    text = "The card annual fee is BDT 2,300 and the rate is 27.00%"
    out = redact_sensitive(text)
    assert "2,300" in out
    assert "27.00%" in out


def test_stable_user_id_prefers_object_guid():
    u = EmployeeUser(username="islamtj", employee_id="2872", ad_object_id="abc-guid")
    assert u.stable_user_id == "abc-guid"
    assert set(u.legacy_identity_keys) == {"islamtj", "2872"}


def test_stable_user_id_falls_back_to_username():
    u = EmployeeUser(username="islamtj", employee_id="2872")
    assert u.stable_user_id == "islamtj"
    # employee_id is a legacy key; username equals stable key so excluded.
    assert u.legacy_identity_keys == ["2872"]


def test_encryption_plaintext_passthrough_when_disabled():
    # With no key configured (default), encrypt is a no-op and decrypt is stable.
    assert decrypt_text(encrypt_text("hello")) == "hello"
    assert decrypt_text("legacy plaintext row") == "legacy plaintext row"


def main():
    tests = [
        test_redacts_card_number_keeps_last4,
        test_redacts_cvv_pin_otp_password,
        test_redacts_account_number_keyword,
        test_preserves_fee_amounts,
        test_stable_user_id_prefers_object_guid,
        test_stable_user_id_falls_back_to_username,
        test_encryption_plaintext_passthrough_when_disabled,
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
