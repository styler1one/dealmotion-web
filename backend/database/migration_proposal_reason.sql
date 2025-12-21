-- Migration: Add proposal_reason column to autopilot_proposals
-- Purpose: Store the "why" explanation for each proposal
-- Date: 2024-12-15

-- Add proposal_reason column
ALTER TABLE autopilot_proposals
ADD COLUMN IF NOT EXISTS proposal_reason TEXT;

-- Add comment
COMMENT ON COLUMN autopilot_proposals.proposal_reason IS 'Explains why this proposal was created (shown to user)';
