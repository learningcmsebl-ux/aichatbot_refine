CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at
    ON chat_messages (created_at);
