-- EBL Home application links index (ebllinks metadata only)
CREATE TABLE IF NOT EXISTS ebl_apps_index (
    id SERIAL PRIMARY KEY,
    source_post_id INTEGER NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    app_url TEXT NOT NULL,
    page_url TEXT NOT NULL,
    post_type VARCHAR(64) NOT NULL DEFAULT 'ebllinks',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ebl_apps_title ON ebl_apps_index (title);
CREATE INDEX IF NOT EXISTS idx_ebl_apps_url ON ebl_apps_index (app_url);
