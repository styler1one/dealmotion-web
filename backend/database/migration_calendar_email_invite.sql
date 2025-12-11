-- Migration: Support email invites in calendar_meetings
-- Purpose: Allow calendar_meetings to be created from email invites (not just calendar sync)
-- 
-- Changes:
-- 1. Make calendar_connection_id nullable (email invites don't have a connection)
-- 2. Add source field to distinguish origin
-- 3. Add is_online and platform fields for better meeting info

-- =============================================================================
-- 1. Make calendar_connection_id nullable
-- =============================================================================

-- First drop the NOT NULL constraint
ALTER TABLE calendar_meetings 
ALTER COLUMN calendar_connection_id DROP NOT NULL;

-- Add comment explaining this
COMMENT ON COLUMN calendar_meetings.calendar_connection_id IS 
'Reference to calendar connection. NULL for email invites (source=email_invite)';

-- =============================================================================
-- 2. Add source field
-- =============================================================================

ALTER TABLE calendar_meetings
ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'calendar_sync' 
CHECK (source IN ('calendar_sync', 'email_invite', 'manual'));

COMMENT ON COLUMN calendar_meetings.source IS 
'Origin of the meeting: calendar_sync (from Google/Microsoft), email_invite (from notes@dealmotion.ai), manual (user created)';

-- =============================================================================
-- 3. Add is_online and platform fields (if not exists)
-- =============================================================================

ALTER TABLE calendar_meetings
ADD COLUMN IF NOT EXISTS is_online BOOLEAN DEFAULT false;

ALTER TABLE calendar_meetings
ADD COLUMN IF NOT EXISTS platform TEXT;

COMMENT ON COLUMN calendar_meetings.is_online IS 'Whether this is an online meeting with a video link';
COMMENT ON COLUMN calendar_meetings.platform IS 'Meeting platform: teams, meet, zoom, webex, etc.';

-- =============================================================================
-- 4. Add index for source filtering
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_calendar_meetings_source 
ON calendar_meetings(source);

-- =============================================================================
-- 5. Update existing records to have correct source
-- =============================================================================

UPDATE calendar_meetings 
SET source = 'calendar_sync' 
WHERE source IS NULL;

