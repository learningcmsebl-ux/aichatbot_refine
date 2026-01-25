"""
Retry failed geocodes with alternate query strategies.

Usage:
  python location_service/geocode_failed_addresses.py

Notes:
- Reads failed address_ids from geocode_failures.csv
- Tries multiple query shapes per address (street/area/city/region)
- Writes new failures to geocode_failures_retry.csv
"""

from __future__ import annotations

import csv
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlencode, quote_plus
from urllib.request import Request, urlopen

from sqlalchemy import create_engine, text


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "EBL-Location-Geocoder/1.0 (admin@ebl.com)"
REQUEST_DELAY_SEC = 1.0
TIMEOUT_SEC = 15

FAILURES_CSV = os.path.join(os.path.dirname(__file__), "geocode_failures.csv")
RETRY_FAILURES_CSV = os.path.join(os.path.dirname(__file__), "geocode_failures_retry.csv")
PROGRESS_JSON = os.path.join(os.path.dirname(__file__), "geocode_progress_retry.json")


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


def geocode_address(query: str) -> tuple[float | None, float | None, str | None]:
    params = {"q": query, "format": "json", "limit": 1}
    url = f"{NOMINATIM_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        if not data:
            return None, None, "no_result"
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        return lat, lon, None
    except Exception as exc:
        return None, None, f"error: {exc}"


def build_queries(street: str | None, area: str | None, city: str | None, region: str | None) -> list[str]:
    def join(parts: list[str]) -> str:
        return ", ".join([p.strip() for p in parts if p and p.strip()])

    # Prefer more specific queries first, then fall back to broader ones
    return [
        join([street, area, city, region, "Bangladesh"]),
        join([street, city, region, "Bangladesh"]),
        join([street, city, "Bangladesh"]),
        join([area, city, region, "Bangladesh"]),
        join([area, city, "Bangladesh"]),
        join([street, "Bangladesh"]),
        join([area, "Bangladesh"]),
    ]


def read_failed_address_ids() -> list[str]:
    if not os.path.exists(FAILURES_CSV):
        return []
    ids: list[str] = []
    with open(FAILURES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            address_id = (row.get("address_id") or "").strip()
            if address_id:
                ids.append(address_id)
    return ids


def write_progress(total: int, done: int, success: int, failed: int) -> None:
    payload = {
        "total": total,
        "done": done,
        "success": success,
        "failed": failed,
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    with open(PROGRESS_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    failed_ids = read_failed_address_ids()
    if not failed_ids:
        print("No failed rows found to retry.")
        return

    engine = create_engine(get_db_url())
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT a.address_id, a.street_address, a.area, c.city_name, r.region_name
                FROM addresses a
                JOIN cities c ON c.city_id = a.city_id
                JOIN regions r ON r.region_id = c.region_id
                WHERE a.address_id = ANY(CAST(:ids AS uuid[]))
                  AND (a.latitude IS NULL OR a.longitude IS NULL)
                ORDER BY a.address_id
                """
            ),
            {"ids": failed_ids},
        ).fetchall()

    total = len(rows)
    done = 0
    success = 0
    failed = 0

    with open(RETRY_FAILURES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["address_id", "query", "reason"])

        for address_id, street, area, city, region in rows:
            queries = build_queries(street, area, city, region)
            lat = lon = None
            last_error = None
            used_query = None

            for q in queries:
                if not q:
                    continue
                used_query = q
                lat, lon, last_error = geocode_address(q)
                if lat is not None and lon is not None:
                    break

            if lat is None or lon is None:
                failed += 1
                writer.writerow([str(address_id), used_query or "", last_error or "no_result"])
            else:
                success += 1
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            """
                            UPDATE addresses
                            SET latitude=:lat,
                                longitude=:lon,
                                geom=ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                            WHERE address_id=:address_id
                            """
                        ),
                        {"lat": lat, "lon": lon, "address_id": address_id},
                    )

            done += 1
            if done % 10 == 0 or done == total:
                write_progress(total, done, success, failed)

            time.sleep(REQUEST_DELAY_SEC)

    write_progress(total, done, success, failed)
    print(f"Done. total={total} success={success} failed={failed}")
    print(f"Failures CSV: {RETRY_FAILURES_CSV}")
    print(f"Progress JSON: {PROGRESS_JSON}")


if __name__ == "__main__":
    main()
