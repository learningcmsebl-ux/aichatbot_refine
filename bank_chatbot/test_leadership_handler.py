"""
Unit tests for LeadershipHandler and EBL Home leadership routing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

_REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO))

from app.services.handlers.leadership_handler import LeadershipHandler
from app.services.handlers.query_classifier import QueryClassifier


class MockLeadershipDB:
    def __init__(
        self,
        *,
        results: Optional[List[Dict]] = None,
        list_results: Optional[List[Dict]] = None,
        total_leaders: int = 1,
    ) -> None:
        self.results = list(results or [])
        self.list_results = list(list_results or [])
        self._total_leaders = total_leaders
        self.smart_search_calls: List[str] = []

    def total_leaders(self) -> int:
        return self._total_leaders

    def smart_search(self, query: str, *, category: Optional[str] = None, limit: int = 5) -> List[Dict]:
        self.smart_search_calls.append(query)
        return list(self.results)

    def list_by_category(self, category: str, limit: int = 15) -> List[Dict]:
        return list(self.list_results)


def test_classifier_detects_cfo_query() -> None:
    classifier = QueryClassifier()
    assert classifier.is_eblhome_leadership_query("Who is the CFO?")
    assert classifier.is_eblhome_leadership_query("management committee members")


def test_classifier_rejects_head_of_department() -> None:
    classifier = QueryClassifier()
    assert not classifier.is_eblhome_leadership_query("Who is the head of brand and marketing?")


def test_classifier_rejects_contact_lookup() -> None:
    classifier = QueryClassifier()
    assert not classifier.is_eblhome_leadership_query("What is the CFO phone number?")


def test_lookup_single_profile() -> None:
    handler = LeadershipHandler()
    db = MockLeadershipDB(
        results=[
            {
                "source_post_id": 18035,
                "full_name": "Hassan O. Rashid",
                "designation": "Managing Director",
                "category": "management",
                "photo_url": "http://eblhome/wp-content/uploads/2018/06/Hasan-Sir-01.jpg",
                "page_url": "http://eblhome/?post_type=ebl_management&p=18035",
            }
        ]
    )
    result = handler.lookup("Who is the Managing Director?", db)
    assert result.found
    assert "Hassan O. Rashid" in result.response_text
    assert "Managing Director" in result.response_text
    assert "/leadership/photo/18035" in result.response_text
    assert "Profile:" not in result.response_text
    assert "EBL Home Leadership" in result.response_text


def test_managing_director_excludes_additional_md() -> None:
    from app.services.ebl_leadership_postgres import EblLeadershipDB

    assert EblLeadershipDB._designation_matches_precise_role("Managing Director", "md")
    assert not EblLeadershipDB._designation_matches_precise_role("Additional Managing Director", "md")
    assert not EblLeadershipDB._designation_matches_precise_role("Deputy Managing Director", "md")
    assert EblLeadershipDB._designation_matches_precise_role("Additional Managing Director", "additional_md")
    assert EblLeadershipDB._designation_matches_precise_role("Deputy Managing Director", "dmd")


def test_lookup_management_committee_list() -> None:
    handler = LeadershipHandler()
    db = MockLeadershipDB(
        list_results=[
            {
                "full_name": "Leader One",
                "designation": "DMD",
                "category": "management",
                "page_url": "http://eblhome/?post_type=ebl_management&p=1",
            },
            {
                "full_name": "Leader Two",
                "designation": "CFO",
                "category": "management",
                "page_url": "http://eblhome/?post_type=ebl_management&p=2",
            },
        ]
    )
    result = handler.lookup("show management committee", db)
    assert result.found
    assert "Leader One" in result.response_text
    assert "Leader Two" in result.response_text
    assert "Management Committee" in result.response_text


def test_lookup_not_found() -> None:
    handler = LeadershipHandler()
    db = MockLeadershipDB(results=[])
    result = handler.lookup("Who is the CFO?", db)
    assert not result.found
    assert "couldn't find" in result.response_text.lower()


def test_routing_target_for_leadership_query() -> None:
    orchestrator = MagicMock()
    orchestrator._is_location_query.return_value = False
    orchestrator._is_retail_asset_fee_query.return_value = False
    orchestrator._is_skybanking_fee_query.return_value = False
    orchestrator._is_fee_schedule_query.return_value = False
    orchestrator._is_small_talk.return_value = False
    orchestrator._is_contact_info_query.return_value = False
    orchestrator._is_phonebook_query.return_value = False
    orchestrator._is_employee_query.return_value = True
    orchestrator._is_organizational_overview_query.return_value = False
    orchestrator._is_banking_product_query.return_value = False
    orchestrator._is_compliance_query.return_value = False
    orchestrator._is_management_query.return_value = True
    orchestrator._is_financial_report_query.return_value = False
    orchestrator._is_milestone_query.return_value = False
    orchestrator._is_user_document_query.return_value = False
    orchestrator._is_eblhome_form_query.return_value = False
    orchestrator._is_eblhome_app_link_query.return_value = False
    orchestrator._is_eblhome_leadership_query.return_value = True
    orchestrator._is_datetime_query.return_value = False
    orchestrator._get_knowledge_base.return_value = "ebl_website"
    orchestrator._get_disambiguation_state_any = AsyncMock(return_value=None)

    from app.services.routing_engine import RoutingEngine

    engine = RoutingEngine(
        orchestrator,
        phonebook_db_available=True,
        forms_db_available=True,
        apps_db_available=True,
        leadership_db_available=True,
    )

    import asyncio

    decision = asyncio.run(engine.decide("Who is the CFO?"))
    assert decision.target == "EBLHOME_LEADERSHIP"


if __name__ == "__main__":
    test_classifier_detects_cfo_query()
    test_classifier_rejects_head_of_department()
    test_classifier_rejects_contact_lookup()
    test_lookup_single_profile()
    test_managing_director_excludes_additional_md()
    test_lookup_management_committee_list()
    test_lookup_not_found()
    test_routing_target_for_leadership_query()
    print("All leadership tests passed.")
