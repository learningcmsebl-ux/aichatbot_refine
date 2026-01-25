-- Enable PostGIS + add geospatial columns + curated POIs (offline nearby search)

-- 1) Enable PostGIS extension (requires PostGIS-enabled Postgres image)
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2) Addresses: add area (if missing), add coordinates + geography point
ALTER TABLE IF EXISTS addresses
  ADD COLUMN IF NOT EXISTS area TEXT;

ALTER TABLE IF EXISTS addresses
  ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS geom geography(Point, 4326);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_addresses_area ON addresses (area);
CREATE INDEX IF NOT EXISTS idx_addresses_geom_gist ON addresses USING GIST (geom);

-- 3) Curated landmarks/POIs for offline “near X” resolution
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

CREATE INDEX IF NOT EXISTS idx_poi_landmarks_name ON poi_landmarks (name);
CREATE INDEX IF NOT EXISTS idx_poi_landmarks_area ON poi_landmarks (area);
CREATE INDEX IF NOT EXISTS idx_poi_landmarks_city ON poi_landmarks (city);
CREATE INDEX IF NOT EXISTS idx_poi_landmarks_region ON poi_landmarks (region);
CREATE INDEX IF NOT EXISTS idx_poi_landmarks_geom_gist ON poi_landmarks USING GIST (geom);

-- 4) Update trigger for poi_landmarks.updated_at (reuse existing trigger function if present)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc WHERE proname = 'update_updated_at_column'
  ) THEN
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $fn$
    BEGIN
      NEW.updated_at = CURRENT_TIMESTAMP;
      RETURN NEW;
    END;
    $fn$ language 'plpgsql';
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'update_poi_landmarks_updated_at'
  ) THEN
    CREATE TRIGGER update_poi_landmarks_updated_at
    BEFORE UPDATE ON poi_landmarks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
  END IF;
END$$;

