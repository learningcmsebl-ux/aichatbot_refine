-- Migration: Remove legacy chat-stub leads table
-- Safe to re-run.

DROP TABLE IF EXISTS leads CASCADE;
