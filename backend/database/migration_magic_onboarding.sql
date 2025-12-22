-- ============================================================
-- Migration: Magic Onboarding Sessions
-- Version: 4.1
-- Date: 22 December 2025
-- 
-- Adds magic_onboarding_sessions table for tracking AI-powered
-- profile creation via Inngest background jobs.
-- ============================================================

-- Create magic_onboarding_sessions table
CREATE TABLE IF NOT EXISTS magic_onboarding_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Session type
    session_type TEXT NOT NULL CHECK (session_type IN ('sales', 'company')),
    
    -- Status tracking
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending',      -- Created, waiting for Inngest pickup
        'processing',   -- Being processed by Inngest
        'completed',    -- Successfully completed
        'failed'        -- Failed with error
    )),
    
    -- Input data (what user provided)
    input_data JSONB NOT NULL DEFAULT '{}',
    -- For sales: {linkedin_url, user_name, company_name}
    -- For company: {company_name, website, linkedin_url, country}
    
    -- Result data (AI-generated profile)
    result_data JSONB,
    
    -- Error tracking
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    
    -- TTL: Sessions expire after 24 hours
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 hours')
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_magic_sessions_user ON magic_onboarding_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_magic_sessions_org ON magic_onboarding_sessions(organization_id);
CREATE INDEX IF NOT EXISTS idx_magic_sessions_status ON magic_onboarding_sessions(status);
CREATE INDEX IF NOT EXISTS idx_magic_sessions_created ON magic_onboarding_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_magic_sessions_expires ON magic_onboarding_sessions(expires_at) 
    WHERE status = 'pending' OR status = 'processing';

-- RLS
ALTER TABLE magic_onboarding_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own sessions" ON magic_onboarding_sessions
    FOR SELECT USING (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can insert own sessions" ON magic_onboarding_sessions
    FOR INSERT WITH CHECK (user_id = (SELECT auth.uid()));

CREATE POLICY "Service role can manage all sessions" ON magic_onboarding_sessions
    FOR ALL USING (auth.role() = 'service_role');

-- Trigger for updated_at
CREATE TRIGGER update_magic_sessions_updated_at
    BEFORE UPDATE ON magic_onboarding_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Cleanup function for expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_magic_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM magic_onboarding_sessions
    WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- ============================================================
-- END OF MIGRATION
-- ============================================================

