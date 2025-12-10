-- Migration: Add context fields to scheduled_recordings
-- Version: 3.10
-- Date: 10 December 2024
-- Purpose: Allow AI Notetaker to link to preparation, contacts, deal, and calendar meeting
--          This enables the same context flow as regular meeting recordings

-- Add context fields to scheduled_recordings
ALTER TABLE scheduled_recordings 
ADD COLUMN IF NOT EXISTS meeting_prep_id UUID REFERENCES meeting_preps(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS contact_ids UUID[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS deal_id UUID REFERENCES deals(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS calendar_meeting_id UUID REFERENCES calendar_meetings(id) ON DELETE SET NULL;

-- Add indexes for the new foreign keys
CREATE INDEX IF NOT EXISTS idx_scheduled_recordings_prep ON scheduled_recordings(meeting_prep_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_recordings_deal ON scheduled_recordings(deal_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_recordings_calendar ON scheduled_recordings(calendar_meeting_id);

-- Comments
COMMENT ON COLUMN scheduled_recordings.meeting_prep_id IS 'Link to meeting preparation (for context in analysis)';
COMMENT ON COLUMN scheduled_recordings.contact_ids IS 'Array of contact person IDs attending the meeting';
COMMENT ON COLUMN scheduled_recordings.deal_id IS 'Optional deal this recording is related to';
COMMENT ON COLUMN scheduled_recordings.calendar_meeting_id IS 'Link to calendar meeting if scheduled from there';

