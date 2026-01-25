"""
Minimal smoke test for offline nearby search.

Prereqs:
- Postgres has PostGIS enabled
- `poi_landmarks` has a POI (use seed_pois.py)
- At least some addresses have latitude/longitude or geom set

Usage:
  python location_service/test_nearby_smoke.py
"""

import json
import os

import httpx


def main() -> None:
    base_url = os.getenv("LOCATION_SERVICE_URL", "http://localhost:8004").rstrip("/")
    params = {
        "type": "atm",
        "near": "JamJam Tower Uttara",
        "radius_km": 5,
        "limit": 10,
    }
    r = httpx.get(f"{base_url}/locations", params=params, timeout=10)
    print("status:", r.status_code)
    payload = r.json()
    print(json.dumps(payload, indent=2))
    if payload.get("total", 0) == 0:
        print(
            "\nNOTE: total=0 usually means your ATM/branch addresses don't have "
            "latitude/longitude (or geom) filled yet. Add coordinates from the admin panel, "
            "then re-run this smoke test."
        )


if __name__ == "__main__":
    main()

