"""Unit tests for AD username normalization (no LDAP server required)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.ldap_auth import normalize_username


def test_normalize_plain_username():
    assert normalize_username("jdoe") == "jdoe"


def test_normalize_domain_backslash():
    assert normalize_username("EBL\\jdoe") == "jdoe"


def test_normalize_email():
    assert normalize_username("jdoe@ebl-bd.com") == "jdoe"


def test_normalize_trim():
    assert normalize_username("  JDOE  ") == "JDOE"


if __name__ == "__main__":
    tests = [
        test_normalize_plain_username,
        test_normalize_domain_backslash,
        test_normalize_email,
        test_normalize_trim,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {test.__name__}: {exc}")
    raise SystemExit(1 if failed else 0)
