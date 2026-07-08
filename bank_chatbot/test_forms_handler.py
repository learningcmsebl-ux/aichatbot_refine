"""
Unit tests for FormsHandler and EBL Home form routing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

_REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO))

from app.services.handlers.forms_handler import FormsHandler
from app.services.handlers.query_classifier import QueryClassifier


class MockFormsDB:
    def __init__(
        self,
        *,
        results: Optional[List[Dict]] = None,
        total_count: int = 0,
        total_forms: int = 1,
    ) -> None:
        self.results = list(results or [])
        self.total_count = total_count
        self._total_forms = total_forms
        self.search_calls: List[str] = []

    def total_forms(self) -> int:
        return self._total_forms

    def search(self, term: str, limit: int = 5) -> List[Dict]:
        self.search_calls.append(term)
        return list(self.results)

    def count_search_results(self, term: str) -> int:
        return self.total_count or len(self.results)


def test_classifier_detects_asset_movement_form() -> None:
    classifier = QueryClassifier()
    assert classifier.is_eblhome_form_query("download asset movement form")
    assert classifier.is_eblhome_form_query("Where can I get the ICT asset requisition form?")


def test_classifier_rejects_credit_card_application_form() -> None:
    classifier = QueryClassifier()
    assert not classifier.is_eblhome_form_query("credit card application form requirements")


def test_extract_search_term() -> None:
    handler = FormsHandler()
    term = handler.extract_search_term("Download the asset movement form")
    assert "asset" in term and "movement" in term, term


def test_lookup_single_form() -> None:
    handler = FormsHandler()
    db = MockFormsDB(
        results=[
            {
                "title": "Admin Asset Movement Form",
                "department": "Administration",
                "subject": "01.Administration Documents",
                "source_post_id": 18580,
                "download_url": "http://eblhome/wp-content/uploads/2018/07/Asset-Movement-Form.doc",
                "page_url": "http://eblhome/?post_type=forms_download&p=18580",
            }
        ]
    )
    result = handler.lookup("download asset movement form", db)
    assert result.found
    assert "Admin Asset Movement Form" in result.response_text
    assert "/forms/download/18580" in result.response_text
    assert "Asset-Movement-Form.doc" in result.response_text
    assert "EBL Home Forms" in result.response_text


def test_lookup_not_found() -> None:
    handler = FormsHandler()
    db = MockFormsDB(results=[])
    result = handler.lookup("download unknown xyz form", db)
    assert not result.found
    assert "couldn't find" in result.response_text.lower()


def test_lookup_empty_index() -> None:
    handler = FormsHandler()
    db = MockFormsDB(total_forms=0)
    result = handler.lookup("download asset movement form", db)
    assert result.unavailable
    assert "not been loaded" in result.response_text.lower()


def test_routing_target_for_form_query() -> None:
    orchestrator = MagicMock()
    orchestrator._is_location_query.return_value = False
    orchestrator._is_retail_asset_fee_query.return_value = False
    orchestrator._is_skybanking_fee_query.return_value = False
    orchestrator._is_fee_schedule_query.return_value = False
    orchestrator._is_small_talk.return_value = False
    orchestrator._is_contact_info_query.return_value = False
    orchestrator._is_phonebook_query.return_value = False
    orchestrator._is_employee_query.return_value = False
    orchestrator._is_organizational_overview_query.return_value = False
    orchestrator._is_banking_product_query.return_value = False
    orchestrator._is_compliance_query.return_value = False
    orchestrator._is_management_query.return_value = False
    orchestrator._is_financial_report_query.return_value = False
    orchestrator._is_milestone_query.return_value = False
    orchestrator._is_user_document_query.return_value = False
    orchestrator._is_eblhome_form_query.return_value = True
    orchestrator._is_datetime_query.return_value = False
    orchestrator._get_knowledge_base.return_value = "ebl_website"
    orchestrator._get_disambiguation_state_any = AsyncMock(return_value=None)

    from app.services.routing_engine import RoutingEngine

    engine = RoutingEngine(orchestrator, phonebook_db_available=True, forms_db_available=True)

    import asyncio

    decision = asyncio.run(engine.decide("download asset movement form"))
    assert decision.target == "EBLHOME_FORMS"


if __name__ == "__main__":
    test_classifier_detects_asset_movement_form()
    test_classifier_rejects_credit_card_application_form()
    test_extract_search_term()
    test_lookup_single_form()
    test_lookup_not_found()
    test_lookup_empty_index()
    test_routing_target_for_form_query()
    print("All forms tests passed.")
