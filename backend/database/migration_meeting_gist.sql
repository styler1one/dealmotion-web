-- Migration: Add meeting_gist field to followups table
-- Date: 2024-12-16
-- Description: Adds an ultra-short TL;DR field for notifications, lists, and quick scanning

-- Add meeting_gist column to followups
ALTER TABLE followups 
ADD COLUMN IF NOT EXISTS meeting_gist TEXT;

-- Add comment for documentation
COMMENT ON COLUMN followups.meeting_gist IS 
'Ultra-short TL;DR (max ~15 words) for notifications and list views. Format: "[Company] - [Topic] - [Outcome]"';

-- Create index for potential future searching/filtering
CREATE INDEX IF NOT EXISTS idx_followups_meeting_gist 
ON followups USING GIN (to_tsvector('english', COALESCE(meeting_gist, '')));
