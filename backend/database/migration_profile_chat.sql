-- ============================================================
-- Profile Chat Sessions - Dynamic AI-powered profile completion
-- Version: 1.0
-- Created: December 2025
-- 
-- This enables a ChatGPT-like experience for profile onboarding:
-- 1. AI starts with LinkedIn data
-- 2. Dynamically asks questions based on what's missing
-- 3. Adapts questions based on user responses
-- 4. Completes when profile is rich enough
-- ============================================================

-- Profile Chat Sessions
CREATE TABLE IF NOT EXISTS profile_chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Session type
    profile_type TEXT NOT NULL CHECK (profile_type IN ('sales', 'company')),
    
    -- Initial data (what we started with)
    initial_data JSONB DEFAULT '{}'::jsonb,
    -- Current profile state (updated after each exchange)
    current_profile JSONB DEFAULT '{}'::jsonb,
    
    -- Conversation history
    -- Format: [{role: 'assistant'|'user', content: '...', timestamp: '...'}]
    messages JSONB DEFAULT '[]'::jsonb,
    
    -- Profile completeness tracking
    completeness_score FLOAT DEFAULT 0.0,
    fields_completed TEXT[] DEFAULT '{}',
    fields_remaining TEXT[] DEFAULT '{}',
    
    -- Session state
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN (
        'active',       -- Chat in progress
        'completed',    -- Profile finished
        'abandoned',    -- User left without completing
        'expired'       -- Session timed out
    )),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Link to resulting profile
    resulting_profile_id UUID
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_profile_chat_sessions_user ON profile_chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_profile_chat_sessions_org ON profile_chat_sessions(organization_id);
CREATE INDEX IF NOT EXISTS idx_profile_chat_sessions_status ON profile_chat_sessions(status);
CREATE INDEX IF NOT EXISTS idx_profile_chat_sessions_type ON profile_chat_sessions(profile_type);
CREATE INDEX IF NOT EXISTS idx_profile_chat_sessions_active ON profile_chat_sessions(user_id, status) 
    WHERE status = 'active';

-- RLS
ALTER TABLE profile_chat_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own chat sessions" ON profile_chat_sessions 
    FOR SELECT USING (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can insert own chat sessions" ON profile_chat_sessions 
    FOR INSERT WITH CHECK (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can update own chat sessions" ON profile_chat_sessions 
    FOR UPDATE USING (user_id = (SELECT auth.uid()));

CREATE POLICY "Service role can manage all sessions" ON profile_chat_sessions 
    FOR ALL USING (auth.role() = 'service_role');

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_profile_chat_sessions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    NEW.last_activity_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS profile_chat_sessions_updated_at ON profile_chat_sessions;
CREATE TRIGGER profile_chat_sessions_updated_at
    BEFORE UPDATE ON profile_chat_sessions
    FOR EACH ROW EXECUTE FUNCTION update_profile_chat_sessions_updated_at();

-- ============================================================
-- END OF MIGRATION
-- ============================================================

