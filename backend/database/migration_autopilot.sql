-- ============================================================
-- Migration: DealMotion Autopilot
-- Version: 4.0
-- Date: 15 December 2025
-- SPEC: SPEC-045-Autopilot
-- 
-- This migration adds tables for the Autopilot feature:
-- - autopilot_proposals: Suggested actions for users
-- - autopilot_settings: User-specific autopilot configuration
-- - meeting_outcomes: Learning data from meeting results
-- - user_prep_preferences: Learned user preferences
-- ============================================================

-- ============================================================
-- 1. AUTOPILOT_PROPOSALS (Suggested actions)
-- ============================================================
CREATE TABLE IF NOT EXISTS autopilot_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Type & trigger
    proposal_type TEXT NOT NULL CHECK (proposal_type IN (
        'research_prep',      -- New meeting, unknown org
        'prep_only',          -- Known prospect, no prep
        'followup_pack',      -- Post-meeting
        'reactivation',       -- Silent prospect
        'complete_flow'       -- Research done, no next step
    )),
    
    trigger_type TEXT NOT NULL CHECK (trigger_type IN (
        'calendar_new_org',
        'calendar_known_prospect',
        'meeting_ended',
        'transcript_ready',
        'prospect_silent',
        'flow_incomplete',
        'manual'
    )),
    trigger_entity_id UUID,           -- calendar_meeting_id, research_id, etc.
    trigger_entity_type TEXT,         -- 'calendar_meeting', 'research', 'followup'
    
    -- Content
    title TEXT NOT NULL,
    description TEXT,
    luna_message TEXT NOT NULL,       -- What Luna says
    
    -- Actions
    suggested_actions JSONB NOT NULL DEFAULT '[]',
    -- Example: [{"action": "research", "params": {"company": "..."}}, ...]
    
    -- State
    status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN (
        'proposed',
        'accepted',
        'executing',
        'completed',
        'declined',
        'snoozed',
        'expired',
        'failed'           -- Execution failed (pipeline error)
    )),
    priority INTEGER DEFAULT 50 CHECK (priority >= 0 AND priority <= 100),
    
    -- Decision
    decided_at TIMESTAMPTZ,
    decision_reason TEXT,
    snoozed_until TIMESTAMPTZ,
    
    -- Execution
    execution_started_at TIMESTAMPTZ,
    execution_completed_at TIMESTAMPTZ,
    execution_result JSONB,
    execution_error TEXT,             -- Error message if failed
    artifacts JSONB DEFAULT '[]',     -- [{type: 'research', id: '...'}, ...]
    
    -- Expiry
    expires_at TIMESTAMPTZ,
    expired_reason TEXT,
    
    -- Metadata
    context_data JSONB DEFAULT '{}',  -- Additional context for display
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for autopilot_proposals
CREATE INDEX IF NOT EXISTS idx_proposals_user_status ON autopilot_proposals(user_id, status);
CREATE INDEX IF NOT EXISTS idx_proposals_org ON autopilot_proposals(organization_id);
CREATE INDEX IF NOT EXISTS idx_proposals_expires ON autopilot_proposals(expires_at) WHERE status = 'proposed';
CREATE INDEX IF NOT EXISTS idx_proposals_trigger ON autopilot_proposals(trigger_entity_id, trigger_entity_type);
CREATE INDEX IF NOT EXISTS idx_proposals_created ON autopilot_proposals(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposals_priority ON autopilot_proposals(user_id, priority DESC) WHERE status = 'proposed';

-- CRITICAL: Prevent duplicate proposals for same trigger
-- Without this, calendar sync every 15 min creates duplicate proposals
CREATE UNIQUE INDEX IF NOT EXISTS idx_proposals_unique_trigger 
ON autopilot_proposals(trigger_entity_id, trigger_entity_type, user_id) 
WHERE status IN ('proposed', 'accepted', 'executing');

-- RLS for autopilot_proposals
ALTER TABLE autopilot_proposals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own proposals"
    ON autopilot_proposals FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users can update own proposals"
    ON autopilot_proposals FOR UPDATE
    USING (user_id = auth.uid());

CREATE POLICY "Users can insert own proposals"
    ON autopilot_proposals FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- ============================================================
-- 2. AUTOPILOT_SETTINGS (User configuration)
-- ============================================================
CREATE TABLE IF NOT EXISTS autopilot_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Master toggle
    enabled BOOLEAN DEFAULT true,
    
    -- Detection settings
    auto_research_new_meetings BOOLEAN DEFAULT true,
    auto_prep_known_prospects BOOLEAN DEFAULT true,
    auto_followup_after_meeting BOOLEAN DEFAULT true,
    reactivation_days_threshold INTEGER DEFAULT 14,
    
    -- Timing
    prep_hours_before_meeting INTEGER DEFAULT 24,
    
    -- Notification style
    notification_style TEXT DEFAULT 'balanced' CHECK (notification_style IN (
        'eager',      -- Notify immediately
        'balanced',   -- Smart timing
        'minimal'     -- Only urgent
    )),
    
    -- Exclusions
    excluded_meeting_keywords TEXT[] DEFAULT '{}',  -- e.g., ['intern', '1:1', 'standup']
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_id)
);

-- Index for autopilot_settings
CREATE INDEX IF NOT EXISTS idx_autopilot_settings_user ON autopilot_settings(user_id);

-- RLS for autopilot_settings
ALTER TABLE autopilot_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own settings"
    ON autopilot_settings FOR ALL
    USING (user_id = auth.uid());

-- ============================================================
-- 3. MEETING_OUTCOMES (Learning data)
-- ============================================================
CREATE TABLE IF NOT EXISTS meeting_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Links
    calendar_meeting_id UUID REFERENCES calendar_meetings(id) ON DELETE SET NULL,
    preparation_id UUID REFERENCES meeting_preps(id) ON DELETE SET NULL,
    followup_id UUID REFERENCES followups(id) ON DELETE SET NULL,
    prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
    
    -- Outcome
    outcome_rating TEXT CHECK (outcome_rating IN ('positive', 'neutral', 'negative')),
    outcome_source TEXT CHECK (outcome_source IN ('user_input', 'followup_sentiment', 'inferred')),
    
    -- Prep engagement (implicit)
    prep_viewed BOOLEAN DEFAULT false,
    prep_view_duration_seconds INTEGER,
    prep_scroll_depth FLOAT,
    
    -- Context for learning
    had_contact_analysis BOOLEAN,
    had_kb_content BOOLEAN,
    prep_length_words INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for meeting_outcomes
CREATE INDEX IF NOT EXISTS idx_outcomes_user ON meeting_outcomes(user_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_prep ON meeting_outcomes(preparation_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_org ON meeting_outcomes(organization_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_prospect ON meeting_outcomes(prospect_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_calendar ON meeting_outcomes(calendar_meeting_id);

-- RLS for meeting_outcomes
ALTER TABLE meeting_outcomes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own outcomes"
    ON meeting_outcomes FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users can insert own outcomes"
    ON meeting_outcomes FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own outcomes"
    ON meeting_outcomes FOR UPDATE
    USING (user_id = auth.uid());

-- ============================================================
-- 4. USER_PREP_PREFERENCES (Learned preferences)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_prep_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    
    -- Learned preferences
    preferred_length TEXT CHECK (preferred_length IN ('short', 'medium', 'long')),
    valued_sections TEXT[] DEFAULT '{}',
    deemphasized_sections TEXT[] DEFAULT '{}',
    
    -- Stats
    avg_prep_view_duration_seconds INTEGER,
    prep_completion_rate FLOAT,
    positive_outcome_rate FLOAT,
    
    -- Confidence
    sample_size INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for user_prep_preferences
CREATE INDEX IF NOT EXISTS idx_prep_preferences_user ON user_prep_preferences(user_id);

-- RLS for user_prep_preferences
ALTER TABLE user_prep_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own preferences"
    ON user_prep_preferences FOR ALL
    USING (user_id = auth.uid());

-- ============================================================
-- 5. TRIGGERS for updated_at
-- ============================================================

-- Trigger function (reuse existing if available)
CREATE OR REPLACE FUNCTION update_autopilot_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for autopilot_proposals
DROP TRIGGER IF EXISTS autopilot_proposals_updated_at ON autopilot_proposals;
CREATE TRIGGER autopilot_proposals_updated_at
    BEFORE UPDATE ON autopilot_proposals
    FOR EACH ROW
    EXECUTE FUNCTION update_autopilot_updated_at();

-- Trigger for autopilot_settings
DROP TRIGGER IF EXISTS autopilot_settings_updated_at ON autopilot_settings;
CREATE TRIGGER autopilot_settings_updated_at
    BEFORE UPDATE ON autopilot_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_autopilot_updated_at();

-- Trigger for user_prep_preferences
DROP TRIGGER IF EXISTS user_prep_preferences_updated_at ON user_prep_preferences;
CREATE TRIGGER user_prep_preferences_updated_at
    BEFORE UPDATE ON user_prep_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_autopilot_updated_at();

-- ============================================================
-- 6. SERVICE ROLE POLICIES (for backend operations)
-- ============================================================

-- Allow service role to manage proposals (for Inngest functions)
CREATE POLICY "Service role can manage all proposals"
    ON autopilot_proposals FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role can manage all settings"
    ON autopilot_settings FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role can manage all outcomes"
    ON meeting_outcomes FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role can manage all preferences"
    ON user_prep_preferences FOR ALL
    USING (auth.role() = 'service_role');

-- ============================================================
-- DONE
-- ============================================================
-- Tables created: 4
-- Indexes created: 13
-- RLS policies created: 12
-- Triggers created: 3
