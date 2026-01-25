"""
Seed curated POIs/Landmarks for offline nearby search.

Usage (host):
  python location_service/seed_pois.py

This script is safe to run multiple times (UPSERT by name).
"""

import os
from urllib.parse import quote_plus

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


def main() -> None:
    engine = create_engine(get_db_url())
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        # Ensure table exists (if location_service hasn't been started yet)
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS poi_landmarks (
                  poi_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                  name VARCHAR(200) NOT NULL,
                  aliases TEXT[] NULL,
                  area VARCHAR(100) NULL,
                  city VARCHAR(100) NULL,
                  region VARCHAR(100) NULL,
                  latitude DOUBLE PRECISION NULL,
                  longitude DOUBLE PRECISION NULL,
                  geom geography(Point, 4326) NULL,
                  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        )

        # Seed example: JamJam Tower Uttara (coordinates can be adjusted to your canonical point)
        # Keep idempotent by removing existing name matches first (no unique constraint assumed).
        conn.execute(
            text("DELETE FROM poi_landmarks WHERE lower(name) = lower(:name)"),
            {"name": "JamJam Tower Uttara"},
        )
        conn.execute(
            text(
                """
                INSERT INTO poi_landmarks (name, aliases, area, city, region, latitude, longitude, geom)
                VALUES (:name, :aliases, :area, :city, :region, :lat, :lon, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)
                ;
                """
            ),
            {
                "name": "JamJam Tower Uttara",
                "aliases": ["Jam Jam Tower Uttara", "JamJam Tower", "Jam Jam Tower"],
                "area": "Uttara",
                "city": "Dhaka",
                "region": "Dhaka",
                "lat": 23.875,
                "lon": 90.398,
            },
        )

        count = conn.execute(text("SELECT COUNT(*) FROM poi_landmarks")).scalar() or 0
        print(f"Seed complete. poi_landmarks total rows: {count}")


if __name__ == "__main__":
    main()

