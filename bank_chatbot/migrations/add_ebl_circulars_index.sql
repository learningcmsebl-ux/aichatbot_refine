-- EBL Home compliance circular / link_insert index
CREATE TABLE IF NOT EXISTS ebl_circulars_index (
    id SERIAL PRIMARY KEY,
    source_post_id INTEGER NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    department VARCHAR(255),
    link_url TEXT NOT NULL,
    post_type VARCHAR(64) NOT NULL DEFAULT 'link_insert',
    page_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ebl_circulars_title ON ebl_circulars_index (title);
CREATE INDEX IF NOT EXISTS idx_ebl_circulars_department ON ebl_circulars_index (department);
