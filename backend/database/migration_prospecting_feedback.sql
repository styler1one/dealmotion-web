-- ============================================================
-- MIGRATION: Prospecting Feedback Tracking
-- Date: December 2025
-- 
-- Adds columns to track user feedback on prospecting results:
-- - rejected_at: When user rejected this prospect
-- - rejection_reason: Why (for ML training)
-- 
-- This data enables future ML improvements:
-- 1. Train classifier on import/reject patterns
-- 2. Improve scoring based on user preferences
-- 3. Reduce false positives over time
-- ============================================================

-- Add rejection tracking columns
ALTER TABLE prospecting_results 
ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ;

ALTER TABLE prospecting_results 
ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

-- Add feedback_type for easier querying
-- Values: null (no action), 'imported', 'rejected', 'ignored'
ALTER TABLE prospecting_results 
ADD COLUMN IF NOT EXISTS feedback_type TEXT 
CHECK (feedback_type IS NULL OR feedback_type IN ('imported', 'rejected', 'ignored'));

-- Update feedback_type when imported_at is set
-- (This can be done in application code, but adding trigger for consistency)
CREATE OR REPLACE FUNCTION update_prospecting_feedback_type()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.imported_at IS NOT NULL AND OLD.imported_at IS NULL THEN
        NEW.feedback_type := 'imported';
    ELSIF NEW.rejected_at IS NOT NULL AND OLD.rejected_at IS NULL THEN
        NEW.feedback_type := 'rejected';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Only create trigger if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trigger_update_prospecting_feedback'
    ) THEN
        CREATE TRIGGER trigger_update_prospecting_feedback
            BEFORE UPDATE ON prospecting_results
            FOR EACH ROW
            EXECUTE FUNCTION update_prospecting_feedback_type();
    END IF;
END;
$$;

-- Index for feedback analysis
CREATE INDEX IF NOT EXISTS idx_prospecting_results_feedback 
ON prospecting_results(feedback_type) 
WHERE feedback_type IS NOT NULL;

-- Index for rejection analysis (for ML training)
CREATE INDEX IF NOT EXISTS idx_prospecting_results_rejected 
ON prospecting_results(rejected_at) 
WHERE rejected_at IS NOT NULL;

-- ============================================================
-- COMMENTS for documentation
-- ============================================================

COMMENT ON COLUMN prospecting_results.rejected_at IS 
'Timestamp when user explicitly rejected this prospect. Used for ML training to reduce false positives.';

COMMENT ON COLUMN prospecting_results.rejection_reason IS 
'Optional reason for rejection (e.g., "wrong sector", "too small", "already customer"). Used for ML training.';

COMMENT ON COLUMN prospecting_results.feedback_type IS 
'Quick-access feedback status: imported, rejected, or ignored. Simplifies feedback analysis queries.';

-- ============================================================
-- END OF MIGRATION
-- ============================================================

