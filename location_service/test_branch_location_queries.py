"""
Smoke test: branch locations with user-like queries.

Usage:
  python location_service/test_branch_location_queries.py

Environment:
  LOCATION_SERVICE_URL (default: http://localhost:8004)
  LOCATION_SERVICE_DB_URL / POSTGRES_* (for sampling values)
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode, quote_plus
from urllib.request import Request, urlopen

from sqlalchemy import create_engine, text


def get_db_url() -> str:
    url = os.getenv("LOCATION_SERVICE_DB_URL") or os.getenv("POSTGRES_DB_URL")
    if url:
        return url
    user = os.getenv("POSTGRES_USER", "chatbot_user")
    password = os.getenv("POSTGRES_PASSWORD", "chatbot_password_123")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "chatbot_db")
    return f"postgresql://{user}:{quote_plus(password)}@{host}:{port}/{db}"


def fetch_samples() -> dict[str, Any]:
    engine = create_engine(get_db_url())
    samples: dict[str, Any] = {}
    with engine.begin() as conn:
        samples["city"] = conn.execute(
            text(
                """
                SELECT c.city_name
                FROM branches b
                JOIN addresses a ON a.address_id = b.address_id
                JOIN cities c ON c.city_id = a.city_id
                ORDER BY c.city_name
                LIMIT 1
                """
            )
        ).scalar()
        samples["region"] = conn.execute(
            text(
                """
                SELECT r.region_name
                FROM branches b
                JOIN addresses a ON a.address_id = b.address_id
                JOIN cities c ON c.city_id = a.city_id
                JOIN regions r ON r.region_id = c.region_id
                ORDER BY r.region_name
                LIMIT 1
                """
            )
        ).scalar()
        samples["area"] = conn.execute(
            text(
                """
                SELECT a.area
                FROM branches b
                JOIN addresses a ON a.address_id = b.address_id
                WHERE a.area IS NOT NULL AND a.area <> ''
                ORDER BY a.area
                LIMIT 1
                """
            )
        ).scalar()
        samples["branch_name"] = conn.execute(
            text("SELECT branch_name FROM branches ORDER BY branch_name LIMIT 1")
        ).scalar()
        samples["street_word"] = conn.execute(
            text(
                """
                SELECT split_part(a.street_address, ' ', 1)
                FROM branches b
                JOIN addresses a ON a.address_id = b.address_id
                WHERE a.street_address IS NOT NULL AND a.street_address <> ''
                LIMIT 1
                """
            )
        ).scalar()
    return samples


def call_locations(params: dict[str, Any]) -> dict[str, Any]:
    base_url = os.getenv("LOCATION_SERVICE_URL", "http://localhost:8004")
    url = f"{base_url}/locations?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "EBL-Location-SmokeTest/1.0"})
    with urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def print_result(label: str, params: dict[str, Any], data: dict[str, Any]) -> None:
    total = data.get("total")
    locations = data.get("locations") or []
    sample = locations[:3]
    sample_names = [loc.get("name") for loc in sample]
    print(f"{label}: total={total} params={params}")
    if sample_names:
        print(f"  sample: {sample_names}")


def main() -> None:
    samples = fetch_samples()
    city = samples.get("city")
    region = samples.get("region")
    area = samples.get("area")
    branch_name = samples.get("branch_name")
    street_word = samples.get("street_word")

    queries: list[tuple[str, dict[str, Any]]] = [
        ("All branches (default)", {"type": "branch", "limit": 5}),
    ]

    if city:
        queries.append(("By city", {"type": "branch", "city": city, "limit": 5}))
    if region:
        queries.append(("By region", {"type": "branch", "region": region, "limit": 5}))
    if area:
        queries.append(("By area", {"type": "branch", "area": area, "limit": 5}))
    if branch_name:
        queries.append(("Search by branch name", {"type": "branch", "search": branch_name, "limit": 5}))
    if street_word:
        queries.append(("Search by street keyword", {"type": "branch", "search": street_word, "limit": 5}))

    # Combined filters
    if city and street_word:
        queries.append(("City + search", {"type": "branch", "city": city, "search": street_word, "limit": 5}))

    # Pagination check
    queries.append(("Pagination offset", {"type": "branch", "limit": 5, "offset": 5}))

    for label, params in queries:
        data = call_locations(params)
        print_result(label, params, data)


if __name__ == "__main__":
    main()
