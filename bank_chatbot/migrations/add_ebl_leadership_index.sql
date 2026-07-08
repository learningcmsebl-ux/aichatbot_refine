-- EBL Home leadership index (management committee + board of directors)
CREATE TABLE IF NOT EXISTS ebl_leadership_index (
    id SERIAL PRIMARY KEY,
    source_post_id INTEGER NOT NULL UNIQUE,
    full_name VARCHAR(500) NOT NULL,
    designation VARCHAR(500),
    category VARCHAR(32) NOT NULL,
    post_type VARCHAR(64) NOT NULL,
    priority INTEGER,
    level_priority INTEGER,
    photo_url TEXT,
    page_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ebl_leadership_name ON ebl_leadership_index (full_name);
CREATE INDEX IF NOT EXISTS idx_ebl_leadership_designation ON ebl_leadership_index (designation);
CREATE INDEX IF NOT EXISTS idx_ebl_leadership_category ON ebl_leadership_index (category);
