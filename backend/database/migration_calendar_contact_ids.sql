-- Migration: Add contact_ids to calendar_meetings
-- Purpose: Link matched contacts to calendar meetings

-- Add contact_ids column
ALTER TABLE calendar_meetings
ADD COLUMN IF NOT EXISTS contact_ids UUID[] DEFAULT '{}';

-- Add index for efficient lookups
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_contact_ids 
ON calendar_meetings USING GIN(contact_ids);

-- Comment for documentation
COMMENT ON COLUMN calendar_meetings.contact_ids IS 'Array of matched prospect_contacts IDs attending the meeting';

