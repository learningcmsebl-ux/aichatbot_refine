"""Tests for EBL Home phases 6–8: SOC, proposals, circulars."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

_REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO))

from app.services.handlers.circulars_handler import CircularsHandler
from app.services.handlers.proposals_handler import ProposalsHandler
from app.services.handlers.query_classifier import QueryClassifier
from app.services.handlers.soc_handler import SocHandler


class MockIndexDB:
    def __init__(self, results: Optional[List[Dict]] = None, total: int = 1) -> None:
        self.results = list(results or [])
        self._total = total

    def total_items(self) -> int:
        return self._total

    def search(self, term: str, limit: int = 5) -> List[Dict]:
        return list(self.results)

    def count_search_results(self, term: str) -> int:
        return len(self.results)


def test_classifier_soc_query() -> None:
    qc = QueryClassifier()
    assert qc.is_eblhome_soc_query("download Islamic banking schedule of charges")
    assert not qc.is_eblhome_soc_query("platinum credit card annual fee schedule")


def test_classifier_proposal_query() -> None:
    qc = QueryClassifier()
    assert qc.is_eblhome_proposal_query("credit card limit enhancement status")
    assert qc.is_eblhome_proposal_query("how to check fast cash status")


def test_classifier_circular_query() -> None:
    qc = QueryClassifier()
    assert qc.is_eblhome_circular_query("BFIU circulars link")
    assert qc.is_eblhome_circular_query("open Bangladesh Bank internal circulars")


def test_soc_lookup() -> None:
    handler = SocHandler()
    db = MockIndexDB(
        results=[
            {
                "title": "Islamic Banking SOC",
                "soc_type": "Islamic Schedule of Charges",
                "source_post_id": 400298,
            }
        ]
    )
    result = handler.lookup("Islamic banking schedule of charges", db)
    assert result.found
    assert "/api/soc/download/400298" in result.response_text


def test_proposals_lookup() -> None:
    handler = ProposalsHandler()
    db = MockIndexDB(
        results=[{"title": "Credit Card Limit Enhancement Status", "source_post_id": 76517}]
    )
    result = handler.lookup("credit card limit enhancement status", db)
    assert result.found
    assert "/api/proposals/download/76517" in result.response_text


def test_circulars_lookup() -> None:
    handler = CircularsHandler()
    db = MockIndexDB(
        results=[
            {
                "title": "BFIU Circulars",
                "department": "compliance",
                "link_url": "http://eblhome/bfiu-circulars",
            }
        ]
    )
    result = handler.lookup("BFIU circulars", db)
    assert result.found
    assert "BFIU Circulars" in result.response_text


def test_routing_soc_query() -> None:
    orchestrator = MagicMock()
    for attr in (
        "_is_location_query", "_is_retail_asset_fee_query", "_is_skybanking_fee_query",
        "_is_fee_schedule_query", "_is_small_talk", "_is_contact_info_query",
        "_is_phonebook_query", "_is_employee_query", "_is_organizational_overview_query",
        "_is_banking_product_query", "_is_compliance_query", "_is_management_query",
        "_is_financial_report_query", "_is_milestone_query", "_is_user_document_query",
        "_is_eblhome_form_query", "_is_eblhome_app_link_query", "_is_eblhome_leadership_query",
        "_is_eblhome_proposal_query", "_is_eblhome_circular_query", "_is_datetime_query",
    ):
        setattr(orchestrator, attr, MagicMock(return_value=False))
    orchestrator._is_eblhome_soc_query.return_value = True
    orchestrator._get_knowledge_base.return_value = "ebl_website"
    orchestrator._get_disambiguation_state_any = AsyncMock(return_value=None)

    from app.services.routing_engine import RoutingEngine

    engine = RoutingEngine(
        orchestrator, phonebook_db_available=True, soc_db_available=True,
    )
    import asyncio
    decision = asyncio.run(engine.decide("download Islamic banking schedule of charges"))
    assert decision.target == "EBLHOME_SOC"


if __name__ == "__main__":
    test_classifier_soc_query()
    test_classifier_proposal_query()
    test_classifier_circular_query()
    test_soc_lookup()
    test_proposals_lookup()
    test_circulars_lookup()
    test_routing_soc_query()
    print("All phases 6-8 tests passed.")
