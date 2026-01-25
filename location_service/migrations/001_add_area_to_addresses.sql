-- Add area column to addresses (nullable; manual backfill)
ALTER TABLE IF EXISTS addresses
  ADD COLUMN IF NOT EXISTS area TEXT;

-- Index for filtering/searching by area
CREATE INDEX IF NOT EXISTS idx_addresses_area ON addresses (area);

