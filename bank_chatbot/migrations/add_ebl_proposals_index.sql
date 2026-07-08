-- EBL Home proposal/status update documents index
CREATE TABLE IF NOT EXISTS ebl_proposals_index (
    id SERIAL PRIMARY KEY,
    source_post_id INTEGER NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    post_type VARCHAR(64) NOT NULL DEFAULT 'proposal_update',
    page_url TEXT NOT NULL,
    download_url TEXT,
    attachment_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ebl_proposals_title ON ebl_proposals_index (title);
