-- Migration: Add mobile_recordings table
-- Description: Table for storing recordings uploaded from the mobile app
-- Date: 2024-12-08

-- ============================================================================
-- Mobile Recordings Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS mobile_recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Prospect link (optional)
    prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
    
    -- Storage
    storage_path TEXT NOT NULL,
    original_filename TEXT,
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    
    -- Mobile app reference
    local_recording_id TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'mobile_app',
    
    -- Processing status
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error TEXT,
    
    -- Link to processed followup (after transcription + analysis)
    followup_id UUID REFERENCES followups(id) ON DELETE SET NULL,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    
    -- Constraints
    UNIQUE(organization_id, local_recording_id)
);

-- ============================================================================
-- Indexes
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_mobile_recordings_org 
    ON mobile_recordings(organization_id);
    
CREATE INDEX IF NOT EXISTS idx_mobile_recordings_user 
    ON mobile_recordings(user_id);
    
CREATE INDEX IF NOT EXISTS idx_mobile_recordings_status 
    ON mobile_recordings(status);
    
CREATE INDEX IF NOT EXISTS idx_mobile_recordings_prospect 
    ON mobile_recordings(prospect_id);
    
CREATE INDEX IF NOT EXISTS idx_mobile_recordings_created 
    ON mobile_recordings(created_at DESC);

-- ============================================================================
-- RLS Policies
-- ============================================================================

ALTER TABLE mobile_recordings ENABLE ROW LEVEL SECURITY;

-- Users can only see their own organization's recordings
CREATE POLICY "Users can view own org recordings" ON mobile_recordings
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = auth.uid()
        )
    );

-- Users can insert recordings for their organization
CREATE POLICY "Users can insert recordings" ON mobile_recordings
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = auth.uid()
        )
    );

-- Users can update their own recordings
CREATE POLICY "Users can update own recordings" ON mobile_recordings
    FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Users can delete their own recordings
CREATE POLICY "Users can delete own recordings" ON mobile_recordings
    FOR DELETE
    USING (user_id = auth.uid());

-- ============================================================================
-- Storage Bucket
-- ============================================================================

-- Create recordings bucket if not exists (run in Supabase dashboard)
-- INSERT INTO storage.buckets (id, name, public)
-- VALUES ('recordings', 'recordings', false)
-- ON CONFLICT (id) DO NOTHING;

-- Storage policies for recordings bucket
-- CREATE POLICY "Users can upload recordings"
-- ON storage.objects FOR INSERT
-- WITH CHECK (
--     bucket_id = 'recordings' AND
--     auth.role() = 'authenticated' AND
--     (storage.foldername(name))[1] = (
--         SELECT id::text FROM organizations 
--         WHERE id IN (
--             SELECT organization_id FROM organization_members 
--             WHERE user_id = auth.uid()
--         )
--         LIMIT 1
--     )
-- );

-- CREATE POLICY "Users can read own recordings"
-- ON storage.objects FOR SELECT
-- USING (
--     bucket_id = 'recordings' AND
--     auth.role() = 'authenticated' AND
--     (storage.foldername(name))[1] = (
--         SELECT id::text FROM organizations 
--         WHERE id IN (
--             SELECT organization_id FROM organization_members 
--             WHERE user_id = auth.uid()
--         )
--         LIMIT 1
--     )
-- );

-- CREATE POLICY "Users can delete own recordings"
-- ON storage.objects FOR DELETE
-- USING (
--     bucket_id = 'recordings' AND
--     auth.role() = 'authenticated' AND
--     (storage.foldername(name))[1] = (
--         SELECT id::text FROM organizations 
--         WHERE id IN (
--             SELECT organization_id FROM organization_members 
--             WHERE user_id = auth.uid()
--         )
--         LIMIT 1
--     )
-- );

-- ============================================================================
-- Trigger for updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_mobile_recordings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_mobile_recordings_updated_at ON mobile_recordings;
CREATE TRIGGER trigger_mobile_recordings_updated_at
    BEFORE UPDATE ON mobile_recordings
    FOR EACH ROW
    EXECUTE FUNCTION update_mobile_recordings_updated_at();

