"""
Unit tests for shared location intent detection.

Run (from repo root):
  python bank_chatbot/test_location_intent.py
"""

from __future__ import annotations

import os
import sys

# Ensure bank_chatbot/ is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ""))

from app.services.location_client import LocationClient
from app.services.location_intent import get_location_intent_flags


def test_location_intent_flags() -> None:
    flags = get_location_intent_flags("Where is the Gulshan branch?")
    assert flags.has_location_cue is True
    assert flags.has_geo_token is True
    assert flags.has_in_location_phrase is False

    flags = get_location_intent_flags("branch in Basundhara")
    assert flags.has_location_cue is False
    assert flags.has_geo_token is True
    assert flags.has_in_location_phrase is True

    flags = get_location_intent_flags("controlling branch of agent outlet")
    assert flags.has_location_cue is False
    assert flags.has_geo_token is False
    assert flags.has_in_location_phrase is False


def test_detect_location_type_branch_requires_intent() -> None:
    client = LocationClient()

    assert client._detect_location_type("controlling branch of agent outlet") is None
    assert client._detect_location_type("branch location in gulshan") == "branch"
    assert client._detect_location_type("branch address") == "branch"


def _run() -> None:
    test_location_intent_flags()
    test_detect_location_type_branch_requires_intent()
    print("All location intent tests passed.")


if __name__ == "__main__":
    _run()
