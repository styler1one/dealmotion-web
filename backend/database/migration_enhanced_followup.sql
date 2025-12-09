-- Migration: Enhanced Follow-up Agent
-- Adds columns for commercial signals, observations, coaching feedback
-- Date: 28 November 2025

-- Add new columns to followups table
ALTER TABLE followups ADD COLUMN IF NOT EXISTS include_coaching BOOLEAN DEFAULT false;
ALTER TABLE followups ADD COLUMN IF NOT EXISTS commercial_signals JSONB;
ALTER TABLE followups ADD COLUMN IF NOT EXISTS observations JSONB;
ALTER TABLE followups ADD COLUMN IF NOT EXISTS coaching_feedback JSONB;
ALTER TABLE followups ADD COLUMN IF NOT EXISTS full_summary_content TEXT;

-- Add comments for documentation
COMMENT ON COLUMN followups.include_coaching IS 'Whether user requested coaching feedback for this follow-up';
COMMENT ON COLUMN followups.commercial_signals IS 'Koopsignalen (BANT), cross-sell, upsell, and deal risks detected from transcript';
COMMENT ON COLUMN followups.observations IS 'Reflective observations: doubts, unspoken needs, opportunities, red flags';
COMMENT ON COLUMN followups.coaching_feedback IS 'Sales coaching analysis (opt-in): strengths, improvements, tips';
COMMENT ON COLUMN followups.full_summary_content IS 'Full markdown content of the generated summary for display';

-- Create index for coaching queries
CREATE INDEX IF NOT EXISTS idx_followups_include_coaching ON followups(include_coaching) WHERE include_coaching = true;

-- Verify columns exist
DO $$
BEGIN
    RAISE NOTICE 'Migration completed successfully!';
    RAISE NOTICE 'New columns added to followups table:';
    RAISE NOTICE '  - include_coaching (BOOLEAN)';
    RAISE NOTICE '  - commercial_signals (JSONB)';
    RAISE NOTICE '  - observations (JSONB)';
    RAISE NOTICE '  - coaching_feedback (JSONB)';
    RAISE NOTICE '  - full_summary_content (TEXT)';
END $$;

