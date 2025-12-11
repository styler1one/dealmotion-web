-- Migration: Auto-Record Settings for AI Notetaker
-- SPEC-043: Calendar Integration with Auto-Record
-- 
-- Run this migration in Supabase SQL Editor
-- 
-- NOTE: calendar_connections and calendar_meetings tables already exist!
-- This migration only adds auto_record_settings.

-- =============================================================================
-- 1. Auto-Record Settings Table
-- =============================================================================
-- Stores user preferences for automatic meeting recording

CREATE TABLE IF NOT EXISTS auto_record_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Master toggle
    enabled BOOLEAN DEFAULT false,
    
    -- Mode: 'all', 'filtered', 'none'
    mode TEXT DEFAULT 'filtered' CHECK (mode IN ('all', 'filtered', 'none')),
    
    -- Filter: External attendees only (not from user's domain)
    external_only BOOLEAN DEFAULT true,
    
    -- Filter: Minimum duration in minutes (0 = no minimum)
    min_duration_minutes INTEGER DEFAULT 15,
    
    -- Keywords to include (record if title contains any of these)
    -- Localized defaults for Dutch/English sales teams
    include_keywords TEXT[] DEFAULT ARRAY[
        'demo', 'sales', 'prospect', 'klant', 'client', 
        'presentatie', 'presentation', 'discovery', 'closing',
        'offerte', 'proposal', 'pitch', 'kennismaking', 'intro',
        'call', 'gesprek', 'meeting'
    ],
    
    -- Keywords to exclude (never record if title contains any of these)
    exclude_keywords TEXT[] DEFAULT ARRAY[
        'standup', 'daily', 'weekly', 'sync', '1:1', 'one-on-one', '1-on-1',
        'intern', 'internal', 'lunch', 'retro', 'planning', 
        'sprint', 'refinement', 'team meeting', 'teamoverleg',
        'sollicitatie', 'interview', 'hr', 'performance',
        'prive', 'privé', 'personal', 'dokter', 'tandarts'
    ],
    
    -- Notification preferences
    notify_before_join BOOLEAN DEFAULT true,
    notify_minutes_before INTEGER DEFAULT 2,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- One settings record per user
    UNIQUE(user_id)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_auto_record_settings_user ON auto_record_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_auto_record_settings_org ON auto_record_settings(organization_id);
CREATE INDEX IF NOT EXISTS idx_auto_record_settings_enabled ON auto_record_settings(enabled) WHERE enabled = true;

-- =============================================================================
-- 2. Extend scheduled_recordings for calendar tracking
-- =============================================================================

-- Add columns if they don't exist
ALTER TABLE scheduled_recordings
ADD COLUMN IF NOT EXISTS calendar_event_id TEXT,
ADD COLUMN IF NOT EXISTS auto_scheduled BOOLEAN DEFAULT false;

-- Update source check constraint to include calendar_sync
-- First drop the existing constraint if it exists
DO $$ 
BEGIN
    ALTER TABLE scheduled_recordings DROP CONSTRAINT IF EXISTS scheduled_recordings_source_check;
EXCEPTION WHEN undefined_object THEN
    NULL;
END $$;

-- Add updated constraint
ALTER TABLE scheduled_recordings
ADD CONSTRAINT scheduled_recordings_source_check 
CHECK (source IS NULL OR source IN ('manual', 'calendar_sync', 'email_invite'));

-- Index for finding calendar-synced recordings
CREATE INDEX IF NOT EXISTS idx_scheduled_recordings_calendar_event 
ON scheduled_recordings(calendar_event_id) WHERE calendar_event_id IS NOT NULL;

-- =============================================================================
-- 3. RLS Policies for auto_record_settings
-- =============================================================================

ALTER TABLE auto_record_settings ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (for re-running migration)
DROP POLICY IF EXISTS "Users can view own auto_record_settings" ON auto_record_settings;
DROP POLICY IF EXISTS "Users can insert own auto_record_settings" ON auto_record_settings;
DROP POLICY IF EXISTS "Users can update own auto_record_settings" ON auto_record_settings;
DROP POLICY IF EXISTS "Users can delete own auto_record_settings" ON auto_record_settings;

CREATE POLICY "Users can view own auto_record_settings"
ON auto_record_settings FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own auto_record_settings"
ON auto_record_settings FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own auto_record_settings"
ON auto_record_settings FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own auto_record_settings"
ON auto_record_settings FOR DELETE
USING (auth.uid() = user_id);

-- =============================================================================
-- 4. Updated_at trigger
-- =============================================================================

-- Create trigger function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Drop and recreate trigger
DROP TRIGGER IF EXISTS update_auto_record_settings_updated_at ON auto_record_settings;

CREATE TRIGGER update_auto_record_settings_updated_at
    BEFORE UPDATE ON auto_record_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Done!
-- =============================================================================
-- After running this migration, users can configure auto-record settings
-- and the system will automatically schedule AI Notetaker bots for matching meetings.

