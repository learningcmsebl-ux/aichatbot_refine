-- EBL Home Schedule of Charges index (PDF metadata + download links only)
CREATE TABLE IF NOT EXISTS ebl_soc_index (
    id SERIAL PRIMARY KEY,
    source_post_id INTEGER NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    soc_type VARCHAR(500),
    post_type VARCHAR(64) NOT NULL DEFAULT 'schedule_of_charge',
    page_url TEXT NOT NULL,
    download_url TEXT,
    attachment_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ebl_soc_title ON ebl_soc_index (title);
CREATE INDEX IF NOT EXISTS idx_ebl_soc_type ON ebl_soc_index (soc_type);
