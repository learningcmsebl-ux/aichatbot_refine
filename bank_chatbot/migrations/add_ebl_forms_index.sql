-- EBL Home forms metadata index (links only — no file storage)
CREATE TABLE IF NOT EXISTS ebl_forms_index (
    id SERIAL PRIMARY KEY,
    source_post_id INTEGER NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    department VARCHAR(255),
    subject VARCHAR(255),
    docorder INTEGER,
    post_type VARCHAR(64) NOT NULL DEFAULT 'forms_download',
    page_url TEXT NOT NULL,
    download_url TEXT,
    attachment_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ebl_forms_title ON ebl_forms_index (title);
CREATE INDEX IF NOT EXISTS idx_ebl_forms_department ON ebl_forms_index (department);
CREATE INDEX IF NOT EXISTS idx_ebl_forms_subject ON ebl_forms_index (subject);
