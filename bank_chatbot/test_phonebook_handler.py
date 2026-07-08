"""
Unit tests for PhonebookHandler (Phase 1).

Run (from repo root):
  python bank_chatbot/test_phonebook_handler.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

_REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO))

from app.services.handlers.phonebook_handler import PhonebookHandler


class MockPhonebookDB:
    def __init__(
        self,
        *,
        smart_results: Optional[List[Dict]] = None,
        dept_results: Optional[List[Dict]] = None,
        total_count: int = 0,
    ) -> None:
        self.smart_results = list(smart_results or [])
        self.dept_results = list(dept_results or [])
        self.total_count = total_count
        self.smart_calls: List[str] = []
        self.dept_calls: List[str] = []

    def smart_search(self, term: str, limit: int = 10) -> List[Dict]:
        self.smart_calls.append(term)
        return list(self.smart_results)

    def search_by_department(self, term: str, limit: int = 50) -> List[Dict]:
        self.dept_calls.append(term)
        return list(self.dept_results)

    def count_search_results(self, term: str) -> int:
        return self.total_count

    def format_contact_info(self, employee: Dict) -> str:
        return f"Name: {employee.get('full_name', '')}\nEmail: {employee.get('email', '')}"


def test_extract_mobile_number_of_person() -> None:
    handler = PhonebookHandler()
    term = handler.extract_search_term("What is the mobile number of John Ahmed?")
    assert term.lower() == "john ahmed", term


def test_extract_branch_manager() -> None:
    handler = PhonebookHandler()
    term = handler.extract_search_term("Who is the branch manager of Gulshan branch?")
    assert "manager" in term and "gulshan" in term.lower(), term


def test_extract_find_employee() -> None:
    handler = PhonebookHandler()
    term = handler.extract_search_term("Find employee john_doe in phonebook")
    assert "john_doe" in term, term


def test_lookup_single_result() -> None:
    handler = PhonebookHandler()
    db = MockPhonebookDB(
        smart_results=[{"full_name": "John Ahmed", "email": "john@ebl.com"}],
    )
    result = handler.lookup("mobile number of John Ahmed", db)
    assert result.found
    assert "John Ahmed" in result.response_text
    assert "Phone Book Database" in result.response_text


def test_lookup_not_found() -> None:
    handler = PhonebookHandler()
    db = MockPhonebookDB(smart_results=[])
    result = handler.lookup("mobile number of Unknown Person", db)
    assert not result.found
    assert "couldn't find" in result.response_text.lower()
    assert "LightRAG" not in result.response_text


def test_lookup_unavailable_db() -> None:
    handler = PhonebookHandler()
    result = handler.lookup("phone number of Jane", None)
    assert result.unavailable
    assert "trouble accessing" in result.response_text


def test_lookup_multiple_results() -> None:
    handler = PhonebookHandler()
    db = MockPhonebookDB(
        smart_results=[
            {"full_name": "A", "designation": "Officer"},
            {"full_name": "B", "designation": "Manager"},
        ],
        total_count=7,
    )
    result = handler.lookup("manager Gulshan", db)
    assert result.found
    assert result.result_count == 2
    assert "We found 7 matching" in result.response_text
    assert "narrow down" in result.response_text


def test_division_head_fallback() -> None:
    handler = PhonebookHandler()
    db = MagicMock()
    db.smart_search.side_effect = [[], [{"full_name": "Dept Head", "email": "h@ebl.com"}]]
    db.search_by_department.return_value = []
    db.format_contact_info.return_value = "Name: Dept Head"
    db.count_search_results.return_value = 1

    result = handler.lookup("Who is Retail Banking department?", db)
    assert result.found
    assert db.smart_search.call_count >= 2


def test_substring_hr_in_through_no_department_fallback() -> None:
    handler = PhonebookHandler()
    db = MagicMock()
    db.smart_search.return_value = []

    handler._search_with_fallbacks(db, "walk through approval", limit=5)

    db.smart_search.assert_called_once_with("walk through approval", limit=5)
    db.search_by_department.assert_not_called()


def main() -> int:
    tests = [
        test_extract_mobile_number_of_person,
        test_extract_branch_manager,
        test_extract_find_employee,
        test_lookup_single_result,
        test_lookup_not_found,
        test_lookup_unavailable_db,
        test_lookup_multiple_results,
        test_division_head_fallback,
        test_substring_hr_in_through_no_department_fallback,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
        except Exception as exc:
            failures += 1
            print(f"[FAIL] {test.__name__}: {exc}")
    if failures:
        return 1
    print(f"\nAll {len(tests)} phonebook handler tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
