-- Migration: Add meeting history context to preparations
-- This allows users to select which previous conversations to include in their meeting prep

-- Add selected_followup_ids field to meeting_preps table
-- This stores the IDs of previous followups/conversations the user wants to include
ALTER TABLE meeting_preps 
ADD COLUMN IF NOT EXISTS selected_followup_ids UUID[] DEFAULT '{}';

-- Add comment for documentation
COMMENT ON COLUMN meeting_preps.selected_followup_ids IS 
'Array of followup IDs from previous meetings to include in preparation context. User can select which past conversations are relevant.';

-- Create index for efficient lookups when fetching selected followups
CREATE INDEX IF NOT EXISTS idx_meeting_preps_selected_followup_ids 
ON meeting_preps USING GIN (selected_followup_ids);
