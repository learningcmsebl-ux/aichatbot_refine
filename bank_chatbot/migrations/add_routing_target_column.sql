-- Migration: Add routing_target column to analytics_conversations table
-- Date: 2026-01-28
-- Description: Adds routing_target column to track which service handled each query

-- Add the column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'analytics_conversations' 
        AND column_name = 'routing_target'
    ) THEN
        ALTER TABLE analytics_conversations 
        ADD COLUMN routing_target VARCHAR(50);
        
        -- Create index for efficient filtering
        CREATE INDEX IF NOT EXISTS idx_analytics_routing_target 
        ON analytics_conversations(routing_target);
        
        RAISE NOTICE 'Added routing_target column to analytics_conversations';
    ELSE
        RAISE NOTICE 'Column routing_target already exists';
    END IF;
END $$;

-- Verify the change
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name = 'analytics_conversations'
ORDER BY ordinal_position;
