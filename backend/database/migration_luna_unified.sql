-- ============================================================
-- Migration: Luna Unified AI Assistant
-- Version: 1.0
-- Date: 15 December 2025
-- SPEC: SPEC-046-Luna-Unified-AI-Assistant
-- 
-- This migration adds tables for the Luna Unified AI Assistant:
-- - outreach_messages: Pre-meeting contact outreach (MUST be created FIRST due to FK)
-- - luna_messages: Luna action messages with canonical types
-- - luna_settings: User-specific Luna configuration
-- - luna_feedback: Learning data from user interactions
-- 
-- NOTE: outreach_messages is created BEFORE luna_messages because
--       luna_messages has an FK reference to outreach_messages.
-- ============================================================

-- ============================================================
-- 1. OUTREACH_MESSAGES (Pre-meeting contact outreach)
-- MUST be created FIRST due to FK dependency from luna_messages
-- ============================================================
CREATE TABLE IF NOT EXISTS outreach_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Related Entities
    prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES prospect_contacts(id) ON DELETE SET NULL,
    research_id UUID REFERENCES research_briefs(id) ON DELETE SET NULL,

    -- Channel & Status
    channel TEXT NOT NULL CHECK (channel IN ('linkedin_connect', 'linkedin_message', 'email', 'whatsapp', 'other')),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'sent', 'skipped')),
    sent_at TIMESTAMPTZ,

    -- Content
    subject TEXT,              -- For email channel
    body TEXT,                 -- Generated message content
    payload JSONB DEFAULT '{}', -- Channel-specific metadata

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for outreach_messages
CREATE INDEX IF NOT EXISTS idx_outreach_user_prospect ON outreach_messages(user_id, prospect_id);
CREATE INDEX IF NOT EXISTS idx_outreach_user_contact ON outreach_messages(user_id, contact_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach_messages(status);
CREATE INDEX IF NOT EXISTS idx_outreach_org ON outreach_messages(organization_id);
CREATE INDEX IF NOT EXISTS idx_outreach_created ON outreach_messages(user_id, created_at DESC);

-- RLS for outreach_messages
ALTER TABLE outreach_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own outreach"
    ON outreach_messages FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users can insert own outreach"
    ON outreach_messages FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own outreach"
    ON outreach_messages FOR UPDATE
    USING (user_id = auth.uid());

CREATE POLICY "Users can delete own outreach"
    ON outreach_messages FOR DELETE
    USING (user_id = auth.uid());

CREATE POLICY "Service role can manage all outreach"
    ON outreach_messages FOR ALL
    USING (auth.role() = 'service_role');

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_outreach_messages_updated_at ON outreach_messages;
CREATE TRIGGER update_outreach_messages_updated_at
    BEFORE UPDATE ON outreach_messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================
-- 2. LUNA_MESSAGES (Luna action messages)
-- ============================================================
CREATE TABLE IF NOT EXISTS luna_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Message Type (from canonical list in SPEC-046)
    message_type TEXT NOT NULL,
    
    -- Deduplication (CRITICAL for preventing duplicate messages)
    dedupe_key TEXT NOT NULL,
    
    -- Content
    title TEXT NOT NULL,
    description TEXT,
    luna_message TEXT NOT NULL,       -- What Luna says to the user
    
    -- Related Entities (nullable for flexibility)
    prospect_id UUID REFERENCES prospects(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES prospect_contacts(id) ON DELETE SET NULL,
    meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL,
    research_id UUID REFERENCES research_briefs(id) ON DELETE SET NULL,
    prep_id UUID REFERENCES meeting_preps(id) ON DELETE SET NULL,
    followup_id UUID REFERENCES followups(id) ON DELETE SET NULL,
    outreach_id UUID REFERENCES outreach_messages(id) ON DELETE SET NULL,
    
    -- Action Configuration
    action_type TEXT NOT NULL CHECK (action_type IN ('navigate', 'execute', 'inline')),
    action_route TEXT,           -- For navigate type: SSR-safe route
    action_data JSONB DEFAULT '{}', -- Additional data for inline/execute
    
    -- Priority (server-calculated, deterministic)
    priority INTEGER NOT NULL DEFAULT 50 CHECK (priority >= 0 AND priority <= 100),
    priority_inputs JSONB DEFAULT '{}',  -- Store calculation inputs for debugging
    
    -- Timing
    expires_at TIMESTAMPTZ,
    snooze_until TIMESTAMPTZ,
    
    -- Status (from SPEC-046 section 8.1)
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'executing', 'completed', 'dismissed', 'snoozed', 'expired', 'failed')),
    
    -- Error Handling
    error_code TEXT,
    error_message TEXT,
    retryable BOOLEAN DEFAULT false,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    viewed_at TIMESTAMPTZ,           -- Set ONCE on first luna_message_shown event
    acted_at TIMESTAMPTZ,            -- Set when user takes action
    
    -- CRITICAL: Deduplication constraint (per user, per dedupe_key)
    UNIQUE(user_id, dedupe_key)
);

-- Indexes for luna_messages
CREATE INDEX IF NOT EXISTS idx_luna_messages_user_status ON luna_messages(user_id, status);
CREATE INDEX IF NOT EXISTS idx_luna_messages_user_pending ON luna_messages(user_id) 
    WHERE status IN ('pending', 'snoozed');
CREATE INDEX IF NOT EXISTS idx_luna_messages_expires ON luna_messages(expires_at) 
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_luna_messages_dedupe ON luna_messages(user_id, dedupe_key);
CREATE INDEX IF NOT EXISTS idx_luna_messages_org ON luna_messages(organization_id);
CREATE INDEX IF NOT EXISTS idx_luna_messages_prospect ON luna_messages(prospect_id);
CREATE INDEX IF NOT EXISTS idx_luna_messages_meeting ON luna_messages(meeting_id);
CREATE INDEX IF NOT EXISTS idx_luna_messages_type ON luna_messages(user_id, message_type);
CREATE INDEX IF NOT EXISTS idx_luna_messages_priority ON luna_messages(user_id, priority DESC) 
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_luna_messages_created ON luna_messages(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_luna_messages_snooze ON luna_messages(snooze_until) 
    WHERE status = 'snoozed';

-- RLS for luna_messages
ALTER TABLE luna_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own messages"
    ON luna_messages FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users can update own messages"
    ON luna_messages FOR UPDATE
    USING (user_id = auth.uid());

CREATE POLICY "Users can insert own messages"
    ON luna_messages FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Service role can manage all messages"
    ON luna_messages FOR ALL
    USING (auth.role() = 'service_role');

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_luna_messages_updated_at ON luna_messages;
CREATE TRIGGER update_luna_messages_updated_at
    BEFORE UPDATE ON luna_messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================
-- 3. LUNA_SETTINGS (User configuration)
-- ============================================================
CREATE TABLE IF NOT EXISTS luna_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Master Toggle
    enabled BOOLEAN DEFAULT true,
    
    -- Feature Toggles
    show_widget BOOLEAN DEFAULT true,
    show_contextual_tips BOOLEAN DEFAULT true,
    
    -- Timing Preferences
    prep_reminder_hours INTEGER DEFAULT 24,
    
    -- Outreach Settings (per SPEC-046 section 10.4)
    outreach_cooldown_days INTEGER DEFAULT 14,
    
    -- Excluded Meeting Keywords (don't create prep for these)
    excluded_meeting_keywords TEXT[] DEFAULT ARRAY['internal', '1:1', 'standup', 'sync'],
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- One settings row per user
    UNIQUE(user_id)
);

-- Indexes for luna_settings
CREATE INDEX IF NOT EXISTS idx_luna_settings_user ON luna_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_luna_settings_org ON luna_settings(organization_id);

-- RLS for luna_settings
ALTER TABLE luna_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own settings"
    ON luna_settings FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users can insert own settings"
    ON luna_settings FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own settings"
    ON luna_settings FOR UPDATE
    USING (user_id = auth.uid());

CREATE POLICY "Users can delete own settings"
    ON luna_settings FOR DELETE
    USING (user_id = auth.uid());

CREATE POLICY "Service role can manage all luna settings"
    ON luna_settings FOR ALL
    USING (auth.role() = 'service_role');

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_luna_settings_updated_at ON luna_settings;
CREATE TRIGGER update_luna_settings_updated_at
    BEFORE UPDATE ON luna_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================
-- 4. LUNA_FEEDBACK (Learning data from user interactions)
-- ============================================================
CREATE TABLE IF NOT EXISTS luna_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    message_id UUID REFERENCES luna_messages(id) ON DELETE SET NULL,
    
    -- Feedback type matches message lifecycle
    feedback_type TEXT NOT NULL 
        CHECK (feedback_type IN ('accepted', 'dismissed', 'snoozed', 'completed', 'failed', 'expired')),
    
    -- Message context for analytics
    message_type TEXT NOT NULL,
    
    -- Timing metrics
    time_to_action_seconds INTEGER,    -- Time from viewed_at to acted_at
    time_shown_seconds INTEGER,        -- Time message was visible before action
    
    -- Snooze details (if applicable)
    snooze_duration_hours INTEGER,
    
    -- Surface where action was taken
    surface TEXT CHECK (surface IN ('home', 'widget')),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for luna_feedback
CREATE INDEX IF NOT EXISTS idx_luna_feedback_user ON luna_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_luna_feedback_user_type ON luna_feedback(user_id, message_type);
CREATE INDEX IF NOT EXISTS idx_luna_feedback_org ON luna_feedback(organization_id);
CREATE INDEX IF NOT EXISTS idx_luna_feedback_message ON luna_feedback(message_id);
CREATE INDEX IF NOT EXISTS idx_luna_feedback_feedback_type ON luna_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_luna_feedback_created ON luna_feedback(created_at DESC);

-- RLS for luna_feedback
ALTER TABLE luna_feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own feedback"
    ON luna_feedback FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users can insert own feedback"
    ON luna_feedback FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Service role can manage all feedback"
    ON luna_feedback FOR ALL
    USING (auth.role() = 'service_role');


-- ============================================================
-- 5. LUNA FEATURE FLAGS TABLE
-- Simple feature flag storage for Luna rollout
-- ============================================================
CREATE TABLE IF NOT EXISTS luna_feature_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flag_name TEXT NOT NULL UNIQUE,
    flag_value BOOLEAN DEFAULT false,
    description TEXT,
    
    -- Targeting (optional - for percentage rollouts)
    user_percentage INTEGER DEFAULT 0 CHECK (user_percentage >= 0 AND user_percentage <= 100),
    enabled_user_ids UUID[] DEFAULT '{}',  -- Specific users who have the flag enabled
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default Luna feature flags
INSERT INTO luna_feature_flags (flag_name, flag_value, description, user_percentage) VALUES
    ('luna_enabled', false, 'Master switch for Luna UI visibility', 0),
    ('luna_shadow_mode', true, 'Luna generates messages invisibly for validation', 100),
    ('luna_widget_enabled', false, 'Luna floating widget visibility', 0),
    ('luna_p1_features', false, 'P1 features: deal analysis, sales coaching', 0)
ON CONFLICT (flag_name) DO NOTHING;

-- RLS for luna_feature_flags (admin only via service role)
ALTER TABLE luna_feature_flags ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read feature flags"
    ON luna_feature_flags FOR SELECT
    USING (true);

CREATE POLICY "Service role can manage feature flags"
    ON luna_feature_flags FOR ALL
    USING (auth.role() = 'service_role');

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_luna_feature_flags_updated_at ON luna_feature_flags;
CREATE TRIGGER update_luna_feature_flags_updated_at
    BEFORE UPDATE ON luna_feature_flags
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================
-- 6. HELPER FUNCTION: Check if Luna is enabled for user
-- ============================================================
CREATE OR REPLACE FUNCTION is_luna_enabled_for_user(p_user_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_master_enabled BOOLEAN;
    v_user_percentage INTEGER;
    v_enabled_users UUID[];
    v_user_hash INTEGER;
BEGIN
    -- Get the master flag and user percentage
    SELECT flag_value, user_percentage, enabled_user_ids
    INTO v_master_enabled, v_user_percentage, v_enabled_users
    FROM public.luna_feature_flags
    WHERE flag_name = 'luna_enabled';
    
    -- If master is enabled, everyone gets it
    IF v_master_enabled = true THEN
        RETURN true;
    END IF;
    
    -- Check if user is in explicit enabled list
    IF p_user_id = ANY(v_enabled_users) THEN
        RETURN true;
    END IF;
    
    -- Check percentage rollout (deterministic hash based on user_id)
    IF v_user_percentage > 0 THEN
        -- Create a deterministic hash 0-99 from user_id
        v_user_hash := abs(hashtext(p_user_id::text)) % 100;
        IF v_user_hash < v_user_percentage THEN
            RETURN true;
        END IF;
    END IF;
    
    RETURN false;
END;
$$;


-- ============================================================
-- 7. HELPER FUNCTION: Check if Luna shadow mode is active
-- ============================================================
CREATE OR REPLACE FUNCTION is_luna_shadow_mode()
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_shadow_mode BOOLEAN;
BEGIN
    SELECT flag_value INTO v_shadow_mode
    FROM public.luna_feature_flags
    WHERE flag_name = 'luna_shadow_mode';
    
    RETURN COALESCE(v_shadow_mode, false);
END;
$$;


-- ============================================================
-- DONE
-- ============================================================
-- Tables created: 5
--   - outreach_messages (pre-meeting contact outreach)
--   - luna_messages (Luna action messages)
--   - luna_settings (user configuration)
--   - luna_feedback (learning data)
--   - luna_feature_flags (rollout control)
-- 
-- Indexes created: ~25
-- RLS policies created: ~20
-- Triggers created: 4
-- Helper functions: 2
-- 
-- NOTE: This migration depends on the existing update_updated_at_column() 
--       trigger function. If it doesn't exist, create it first.
