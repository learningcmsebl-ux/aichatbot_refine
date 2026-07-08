-- Migration: Add chat_sessions table and evolve chat_messages
-- Run once. Safe to re-run (uses IF NOT EXISTS / DO).

-- 1. Drop old chat_messages data (fresh start as requested)
TRUNCATE TABLE chat_messages;

-- 2. chat_sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_reference_no VARCHAR(255) UNIQUE NOT NULL,
    user_id             VARCHAR(255) NOT NULL,
    title               VARCHAR(255) NOT NULL DEFAULT 'New Chat',
    preview             VARCHAR(300),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at         TIMESTAMPTZ,
    deleted_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id
    ON chat_sessions (user_id, deleted_at, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_ref
    ON chat_sessions (session_reference_no);

-- 3. Add new columns to chat_messages
ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS chat_session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS source_module   VARCHAR(100),
    ADD COLUMN IF NOT EXISTS user_id         VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id_fk
    ON chat_messages (chat_session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id
    ON chat_messages (user_id, created_at DESC);
