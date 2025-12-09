-- ============================================================================
-- Migration: Calendar Integration
-- SPEC: SPEC-038-Meetings-Calendar-Integration
-- TASK: TASK-044 - Sprint 1.1: Database Foundation
-- Date: 2025-12-07
-- ============================================================================
-- 
-- This migration creates 4 new tables:
-- 1. calendar_connections - OAuth tokens and sync status
-- 2. calendar_meetings - Synchronized meetings from external calendars
-- 3. recording_integrations - Configuration for recording services
-- 4. external_recordings - Imported recordings before processing
--
-- It also adds foreign keys to the followups table.
-- ============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- TABLE 1: calendar_connections
-- ============================================================================
-- Stores OAuth tokens and sync status per user per provider.
-- Tokens are stored encrypted using Supabase Vault.

CREATE TABLE IF NOT EXISTS calendar_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Provider (google or microsoft)
    provider TEXT NOT NULL CHECK (provider IN ('google', 'microsoft')),
    
    -- OAuth tokens (encrypted via Supabase Vault or pgcrypto)
    -- IMPORTANT: Application code must encrypt tokens before insert
    -- and decrypt after select using pgsodium.crypto_secretbox
    access_token_encrypted BYTEA NOT NULL,
    refresh_token_encrypted BYTEA,
    token_expires_at TIMESTAMPTZ,
    encryption_key_id UUID,  -- Reference to key in vault.secrets (if using Vault)
    
    -- Account info (for display in UI)
    email TEXT,
    
    -- Sync status
    last_sync_at TIMESTAMPTZ,
    last_sync_status TEXT CHECK (last_sync_status IN ('success', 'failed', 'partial')),
    last_sync_error TEXT,
    needs_reauth BOOLEAN DEFAULT false,  -- True if token refresh failed
    
    -- Settings
    sync_enabled BOOLEAN DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(user_id, provider)
);

-- Indexes for calendar_connections
CREATE INDEX IF NOT EXISTS idx_calendar_connections_org 
    ON calendar_connections(organization_id);
CREATE INDEX IF NOT EXISTS idx_calendar_connections_user 
    ON calendar_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_calendar_connections_sync 
    ON calendar_connections(sync_enabled, last_sync_at);
CREATE INDEX IF NOT EXISTS idx_calendar_connections_needs_reauth 
    ON calendar_connections(needs_reauth) WHERE needs_reauth = true;

-- RLS for calendar_connections
ALTER TABLE calendar_connections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own connections" 
    ON calendar_connections FOR SELECT 
    USING (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can insert own connections" 
    ON calendar_connections FOR INSERT 
    WITH CHECK (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can update own connections" 
    ON calendar_connections FOR UPDATE 
    USING (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can delete own connections" 
    ON calendar_connections FOR DELETE 
    USING (user_id = (SELECT auth.uid()));

-- ============================================================================
-- TABLE 2: calendar_meetings
-- ============================================================================
-- Synchronized meetings from external calendars (Google, Microsoft).
-- Note: This is separate from the existing `meetings` table which stores
-- manually created meetings linked to deals.

CREATE TABLE IF NOT EXISTS calendar_meetings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- External reference
    calendar_connection_id UUID NOT NULL REFERENCES calendar_connections(id) ON DELETE CASCADE,
    external_event_id TEXT NOT NULL,
    
    -- Meeting info
    title TEXT NOT NULL,
    description TEXT,  -- May be null for privacy
    
    -- Times (always stored in UTC)
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    original_timezone TEXT DEFAULT 'UTC',  -- Original calendar timezone for display
    
    -- Location
    location TEXT,
    meeting_url TEXT,  -- Video call URL if present
    
    -- Recurring events
    is_recurring BOOLEAN DEFAULT false,
    recurrence_rule TEXT,           -- RRULE format (e.g., "RRULE:FREQ=WEEKLY;BYDAY=MO")
    recurring_event_id TEXT,        -- Parent event ID for recurring instances
    
    -- Status
    status TEXT DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'tentative', 'cancelled')),
    
    -- Attendees (JSONB array)
    -- Format: [{"email": "...", "name": "...", "response": "accepted|declined|tentative|needsAction", "organizer": true|false}]
    attendees JSONB DEFAULT '[]',
    
    -- Linking to DealMotion entities
    prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
    prospect_link_type TEXT CHECK (prospect_link_type IN ('auto', 'manual')),
    
    -- Related items
    preparation_id UUID REFERENCES meeting_preps(id) ON DELETE SET NULL,
    followup_id UUID REFERENCES followups(id) ON DELETE SET NULL,
    
    -- Optional link to legacy meetings table (for future migration/unification)
    legacy_meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL,
    
    -- Sync metadata
    etag TEXT,  -- For incremental sync (Google uses ETags)
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(calendar_connection_id, external_event_id)
);

-- Indexes for calendar_meetings
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_org 
    ON calendar_meetings(organization_id);
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_user 
    ON calendar_meetings(user_id);
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_time 
    ON calendar_meetings(start_time);
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_end_time 
    ON calendar_meetings(end_time);
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_prospect 
    ON calendar_meetings(prospect_id) WHERE prospect_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_status 
    ON calendar_meetings(status) WHERE status != 'cancelled';
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_recurring 
    ON calendar_meetings(recurring_event_id) WHERE is_recurring = true;
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_connection 
    ON calendar_meetings(calendar_connection_id);

-- RLS for calendar_meetings
ALTER TABLE calendar_meetings ENABLE ROW LEVEL SECURITY;

-- All org members can view meetings (for team visibility)
CREATE POLICY "Org members can view meetings" 
    ON calendar_meetings FOR SELECT 
    USING (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = (SELECT auth.uid())
        )
    );

-- Only meeting owner can insert/update/delete
CREATE POLICY "Users can insert own meetings" 
    ON calendar_meetings FOR INSERT 
    WITH CHECK (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can update own meetings" 
    ON calendar_meetings FOR UPDATE 
    USING (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can delete own meetings" 
    ON calendar_meetings FOR DELETE 
    USING (user_id = (SELECT auth.uid()));

-- ============================================================================
-- TABLE 3: recording_integrations
-- ============================================================================
-- Configuration for recording services (Fireflies, Zoom, Teams).
-- Stores API keys or OAuth tokens depending on the provider.

CREATE TABLE IF NOT EXISTS recording_integrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Provider
    provider TEXT NOT NULL CHECK (provider IN ('fireflies', 'zoom', 'teams')),
    
    -- Credentials (format depends on provider)
    -- Fireflies: {"api_key_encrypted": "..."}
    -- Zoom/Teams: {"access_token_encrypted": "...", "refresh_token_encrypted": "...", "expires_at": "..."}
    credentials JSONB NOT NULL,
    
    -- Account info (for display in UI)
    account_email TEXT,
    account_name TEXT,
    
    -- Sync status
    last_sync_at TIMESTAMPTZ,
    last_sync_status TEXT CHECK (last_sync_status IN ('success', 'failed')),
    last_sync_error TEXT,
    needs_reauth BOOLEAN DEFAULT false,
    
    -- Settings
    auto_import BOOLEAN DEFAULT true,  -- Automatically import new recordings
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(user_id, provider)
);

-- Indexes for recording_integrations
CREATE INDEX IF NOT EXISTS idx_recording_integrations_org 
    ON recording_integrations(organization_id);
CREATE INDEX IF NOT EXISTS idx_recording_integrations_user 
    ON recording_integrations(user_id);
CREATE INDEX IF NOT EXISTS idx_recording_integrations_provider 
    ON recording_integrations(provider);
CREATE INDEX IF NOT EXISTS idx_recording_integrations_auto_import 
    ON recording_integrations(auto_import) WHERE auto_import = true;

-- RLS for recording_integrations
ALTER TABLE recording_integrations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own integrations" 
    ON recording_integrations FOR ALL 
    USING (user_id = (SELECT auth.uid()));

-- ============================================================================
-- TABLE 4: external_recordings
-- ============================================================================
-- Imported recordings from external services (before processing into followups).
-- Tracks the import status and matching to meetings/prospects.

CREATE TABLE IF NOT EXISTS external_recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Source integration
    integration_id UUID NOT NULL REFERENCES recording_integrations(id) ON DELETE CASCADE,
    
    -- External reference
    external_id TEXT NOT NULL,
    provider TEXT NOT NULL CHECK (provider IN ('fireflies', 'zoom', 'teams', 'mobile')),
    
    -- Recording info
    title TEXT,
    recording_date TIMESTAMPTZ NOT NULL,
    duration_seconds INTEGER,
    participants JSONB DEFAULT '[]',  -- Array of email addresses or names
    
    -- Content (may be URLs or actual content)
    audio_url TEXT,
    transcript_url TEXT,
    transcript_text TEXT,  -- Full transcript if available
    
    -- Matching to DealMotion entities
    matched_meeting_id UUID REFERENCES calendar_meetings(id) ON DELETE SET NULL,
    matched_prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
    match_confidence DECIMAL(5,4) CHECK (match_confidence >= 0 AND match_confidence <= 1),
    -- Confidence scale: 0.0000 = no match, 1.0000 = perfect match
    
    -- Import status
    import_status TEXT DEFAULT 'pending' 
        CHECK (import_status IN ('pending', 'imported', 'skipped', 'failed')),
    imported_followup_id UUID REFERENCES followups(id) ON DELETE SET NULL,
    import_error TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(integration_id, external_id)
);

-- Indexes for external_recordings
CREATE INDEX IF NOT EXISTS idx_external_recordings_org 
    ON external_recordings(organization_id);
CREATE INDEX IF NOT EXISTS idx_external_recordings_user 
    ON external_recordings(user_id);
CREATE INDEX IF NOT EXISTS idx_external_recordings_status 
    ON external_recordings(import_status);
CREATE INDEX IF NOT EXISTS idx_external_recordings_date 
    ON external_recordings(recording_date);
CREATE INDEX IF NOT EXISTS idx_external_recordings_meeting 
    ON external_recordings(matched_meeting_id) WHERE matched_meeting_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_external_recordings_prospect 
    ON external_recordings(matched_prospect_id) WHERE matched_prospect_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_external_recordings_integration 
    ON external_recordings(integration_id);

-- RLS for external_recordings
ALTER TABLE external_recordings ENABLE ROW LEVEL SECURITY;

-- All org members can view recordings (for team visibility)
CREATE POLICY "Org members can view recordings" 
    ON external_recordings FOR SELECT 
    USING (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = (SELECT auth.uid())
        )
    );

-- Only recording owner can insert/update/delete
CREATE POLICY "Users can insert own recordings" 
    ON external_recordings FOR INSERT 
    WITH CHECK (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can update own recordings" 
    ON external_recordings FOR UPDATE 
    USING (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can delete own recordings" 
    ON external_recordings FOR DELETE 
    USING (user_id = (SELECT auth.uid()));

-- ============================================================================
-- ALTER EXISTING TABLES
-- ============================================================================

-- Add calendar_meeting and external_recording references to followups table
-- This allows linking a followup to its source (calendar meeting or recording)
ALTER TABLE followups 
    ADD COLUMN IF NOT EXISTS calendar_meeting_id UUID REFERENCES calendar_meetings(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS external_recording_id UUID REFERENCES external_recordings(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_followups_calendar_meeting 
    ON followups(calendar_meeting_id) WHERE calendar_meeting_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_followups_external_recording 
    ON followups(external_recording_id) WHERE external_recording_id IS NOT NULL;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for all new tables
DROP TRIGGER IF EXISTS update_calendar_connections_updated_at ON calendar_connections;
CREATE TRIGGER update_calendar_connections_updated_at
    BEFORE UPDATE ON calendar_connections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_calendar_meetings_updated_at ON calendar_meetings;
CREATE TRIGGER update_calendar_meetings_updated_at
    BEFORE UPDATE ON calendar_meetings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_recording_integrations_updated_at ON recording_integrations;
CREATE TRIGGER update_recording_integrations_updated_at
    BEFORE UPDATE ON recording_integrations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_external_recordings_updated_at ON external_recordings;
CREATE TRIGGER update_external_recordings_updated_at
    BEFORE UPDATE ON external_recordings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE calendar_connections IS 'OAuth connections to external calendars (Google, Microsoft)';
COMMENT ON TABLE calendar_meetings IS 'Meetings synchronized from external calendars';
COMMENT ON TABLE recording_integrations IS 'Connections to recording services (Fireflies, Zoom, Teams)';
COMMENT ON TABLE external_recordings IS 'Recordings imported from external services before processing';

COMMENT ON COLUMN calendar_connections.access_token_encrypted IS 'OAuth access token - MUST be encrypted before storage';
COMMENT ON COLUMN calendar_connections.refresh_token_encrypted IS 'OAuth refresh token - MUST be encrypted before storage';
COMMENT ON COLUMN calendar_connections.needs_reauth IS 'True if token refresh failed and user needs to reconnect';

COMMENT ON COLUMN calendar_meetings.prospect_link_type IS 'How the meeting was linked: auto (by matching) or manual (by user)';
COMMENT ON COLUMN calendar_meetings.original_timezone IS 'Original timezone from calendar for display purposes';
COMMENT ON COLUMN calendar_meetings.etag IS 'Google ETag for incremental sync';

COMMENT ON COLUMN external_recordings.match_confidence IS 'Confidence score for meeting/prospect match: 0.0 to 1.0';
COMMENT ON COLUMN external_recordings.import_status IS 'pending=not imported, imported=processed into followup, skipped=user skipped, failed=error';

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- 
-- After running this migration:
-- 1. Verify tables in Supabase dashboard
-- 2. Update complete_schema.sql with these changes
-- 3. Test RLS policies work correctly
-- 
-- To test RLS:
-- SELECT * FROM calendar_connections; -- Should only see own connections
-- ============================================================================

