"""
Geocode all addresses using Nominatim (online) and store lat/lon/geom.

Usage:
  python location_service/geocode_addresses.py

Notes:
- Runs ~1 request/second to respect Nominatim usage policy.
- Overwrites existing coordinates.
- Writes failures to location_service/geocode_failures.csv
- Writes progress to location_service/geocode_progress.json
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
PROGRESS_JSON = os.path.join(os.path.dirname(__file__), "geocode_progress.json")


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


def build_query(street: str, area: str | None, city: str | None, region: str | None) -> str:
    parts = [street.strip()]
    if area:
        parts.append(area.strip())
    if city:
        parts.append(city.strip())
    if region and (not city or region.strip().lower() != city.strip().lower()):
        parts.append(region.strip())
    parts.append("Bangladesh")
    return ", ".join([p for p in parts if p])


def geocode_address(query: str) -> tuple[float | None, float | None, str | None]:
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
    }
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
    engine = create_engine(get_db_url())

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT a.address_id, a.street_address, a.area, c.city_name, r.region_name
                FROM addresses a
                JOIN cities c ON c.city_id = a.city_id
                JOIN regions r ON r.region_id = c.region_id
                ORDER BY a.address_id
                """
            )
        ).fetchall()

    total = len(rows)
    done = 0
    success = 0
    failed = 0

    # Resume support: if progress file exists, skip already processed rows
    if os.path.exists(PROGRESS_JSON):
        try:
            with open(PROGRESS_JSON, "r", encoding="utf-8") as f:
                progress = json.load(f)
            done = int(progress.get("done", 0))
            success = int(progress.get("success", 0))
            failed = int(progress.get("failed", 0))
            if done > 0 and done < total:
                rows = rows[done:]
                print(f"Resuming from progress: done={done} remaining={len(rows)}")
        except Exception:
            # If progress can't be read, continue from start
            done = 0
            success = 0
            failed = 0

    # Prepare failures CSV
    with open(FAILURES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["address_id", "query", "reason"])

        for address_id, street, area, city, region in rows:
            query = build_query(street, area, city, region)
            lat, lon, error = geocode_address(query)

            if lat is None or lon is None:
                failed += 1
                writer.writerow([str(address_id), query, error or "no_result"])
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
    print(f"Failures CSV: {FAILURES_CSV}")
    print(f"Progress JSON: {PROGRESS_JSON}")


if __name__ == "__main__":
    main()

