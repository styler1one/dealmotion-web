-- Migration: User Settings Table
-- Created: 29 November 2025
-- Purpose: Store user preferences including language settings

-- ==========================================
-- CREATE USER SETTINGS TABLE
-- ==========================================

CREATE TABLE IF NOT EXISTS user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Language preferences
    app_language VARCHAR(5) DEFAULT 'en',      -- UI language (default: English)
    output_language VARCHAR(5) DEFAULT 'en',   -- AI output language (default: English)
    email_language VARCHAR(5) DEFAULT 'en',    -- Email generation language (default: English)
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Ensure one settings record per user
    CONSTRAINT unique_user_settings UNIQUE (user_id)
);

-- ==========================================
-- INDEXES
-- ==========================================

CREATE INDEX IF NOT EXISTS idx_user_settings_user_id 
ON user_settings(user_id);

-- ==========================================
-- ROW LEVEL SECURITY
-- ==========================================

ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- Users can read their own settings
CREATE POLICY "Users can read own settings"
ON user_settings FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- Users can insert their own settings
CREATE POLICY "Users can insert own settings"
ON user_settings FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = user_id);

-- Users can update their own settings
CREATE POLICY "Users can update own settings"
ON user_settings FOR UPDATE
TO authenticated
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

-- Users can delete their own settings
CREATE POLICY "Users can delete own settings"
ON user_settings FOR DELETE
TO authenticated
USING (auth.uid() = user_id);

-- Service role can do everything (for backend API)
CREATE POLICY "Service role full access"
ON user_settings FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ==========================================
-- UPDATED_AT TRIGGER
-- ==========================================

CREATE OR REPLACE FUNCTION update_user_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_user_settings_updated_at ON user_settings;

CREATE TRIGGER trigger_user_settings_updated_at
BEFORE UPDATE ON user_settings
FOR EACH ROW
EXECUTE FUNCTION update_user_settings_updated_at();

-- ==========================================
-- COMMENTS
-- ==========================================

COMMENT ON TABLE user_settings IS 'User preferences and settings';
COMMENT ON COLUMN user_settings.app_language IS 'UI language code (nl, en, de, fr, es, hi, ar)';
COMMENT ON COLUMN user_settings.output_language IS 'Default language for AI-generated content';
COMMENT ON COLUMN user_settings.email_language IS 'Default language for email generation';

