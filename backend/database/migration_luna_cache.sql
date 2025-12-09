-- ============================================================================
-- MIGRATION: Luna AI Coach Token Optimization
-- TASK-038: Cache AI-generated tips to reduce token usage
-- Date: 4 December 2025
-- ============================================================================

-- ============================================================================
-- 1. CREATE COACH DAILY TIPS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS coach_daily_tips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    tip_date DATE NOT NULL DEFAULT CURRENT_DATE,
    tip_data JSONB NOT NULL,
    -- tip_data structure:
    -- {
    --   "id": "ai_1234567890",
    --   "category": "research|contacts|preparation|followup|general",
    --   "title": "Short catchy title",
    --   "content": "Practical tip content",
    --   "icon": "emoji",
    --   "is_personalized": true
    -- }
    is_personalized BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- One AI tip per user per day
    UNIQUE(user_id, tip_date)
);

-- ============================================================================
-- 2. ADD INDEXES
-- ============================================================================

-- Fast lookup by user + date
CREATE INDEX IF NOT EXISTS idx_coach_daily_tips_user_date 
ON coach_daily_tips(user_id, tip_date);

-- Cleanup old tips (older than 30 days)
CREATE INDEX IF NOT EXISTS idx_coach_daily_tips_created 
ON coach_daily_tips(created_at);

-- ============================================================================
-- 3. ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE coach_daily_tips ENABLE ROW LEVEL SECURITY;

-- Users can only see their own tips
CREATE POLICY "Users can view own tips" ON coach_daily_tips
    FOR SELECT USING (auth.uid() = user_id);

-- Users can insert their own tips
CREATE POLICY "Users can insert own tips" ON coach_daily_tips
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Service role can do everything (for backend)
CREATE POLICY "Service role full access" ON coach_daily_tips
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================================
-- 4. CLEANUP FUNCTION (Optional - run periodically)
-- ============================================================================

CREATE OR REPLACE FUNCTION cleanup_old_coach_tips()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM coach_daily_tips
    WHERE tip_date < CURRENT_DATE - INTERVAL '30 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Check table exists
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_name = 'coach_daily_tips'
) AS table_exists;


