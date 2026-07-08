-- Migration: Add Active Directory identity metadata to chat history tables.
-- Supports secure per-user chat history keyed by a stable AD identifier.
-- Run once. Safe to re-run (uses IF NOT EXISTS).
--
-- Notes:
--   * `user_id` (already present) remains the ownership key. Going forward it
--     holds the stable AD objectGUID when available, otherwise the Windows login.
--   * The columns below are metadata only and are NEVER used for authorization.

-- 1. chat_sessions metadata
ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS ad_object_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS user_email   VARCHAR(320),
    ADD COLUMN IF NOT EXISTS user_upn     VARCHAR(320),
    ADD COLUMN IF NOT EXISTS username     VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_ad_object_id
    ON chat_sessions (ad_object_id);

-- 2. chat_messages metadata
ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS ad_object_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS user_email   VARCHAR(320),
    ADD COLUMN IF NOT EXISTS user_upn     VARCHAR(320),
    ADD COLUMN IF NOT EXISTS username     VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_chat_messages_ad_object_id
    ON chat_messages (ad_object_id);
