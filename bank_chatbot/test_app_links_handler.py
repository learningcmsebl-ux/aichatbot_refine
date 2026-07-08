"""Unit tests for AppLinksHandler and application link routing."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

_REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO))

from app.services.handlers.app_links_handler import AppLinksHandler
from app.services.handlers.query_classifier import QueryClassifier


class MockAppsDB:
    def __init__(self, *, results: Optional[List[Dict]] = None, total_forms: int = 1) -> None:
        self.results = list(results or [])
        self._total = total_forms

    def total_apps(self) -> int:
        return self._total

    def search(self, term: str, limit: int = 5) -> List[Dict]:
        return list(self.results)

    def count_search_results(self, term: str) -> int:
        return len(self.results)


def test_classifier_detects_requisition_hub() -> None:
    classifier = QueryClassifier()
    assert classifier.is_eblhome_app_link_query("open ICT Requisition Hub")
    assert classifier.is_eblhome_app_link_query("where is the SME portal link")


def test_classifier_prefers_forms_over_apps_for_download() -> None:
    classifier = QueryClassifier()
    assert classifier.is_eblhome_form_query("download ICT asset requisition form")
    assert not classifier.is_eblhome_app_link_query("download ICT asset requisition form")


def test_lookup_requisition_hub() -> None:
    handler = AppLinksHandler()
    db = MockAppsDB(
        results=[
            {
                "title": "ICT Requisition Hub",
                "app_url": "http://192.168.222.42/login/",
                "page_url": "http://eblhome/?post_type=ebllinks&p=17741",
            }
        ]
    )
    result = handler.lookup("open ICT Requisition Hub", db)
    assert result.found
    assert "192.168.222.42/login/" in result.response_text
    assert "EBL Home Applications" in result.response_text


def test_routing_target_for_app_query() -> None:
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
    orchestrator._is_eblhome_form_query.return_value = False
    orchestrator._is_eblhome_app_link_query.return_value = True
    orchestrator._is_datetime_query.return_value = False
    orchestrator._get_knowledge_base.return_value = "ebl_website"
    orchestrator._get_disambiguation_state_any = AsyncMock(return_value=None)

    from app.services.routing_engine import RoutingEngine
    import asyncio

    engine = RoutingEngine(
        orchestrator,
        phonebook_db_available=True,
        forms_db_available=True,
        apps_db_available=True,
    )
    decision = asyncio.run(engine.decide("open ICT Requisition Hub"))
    assert decision.target == "EBLHOME_APPS"


if __name__ == "__main__":
    test_classifier_detects_requisition_hub()
    test_classifier_prefers_forms_over_apps_for_download()
    test_lookup_requisition_hub()
    test_routing_target_for_app_query()
    print("All app links tests passed.")
