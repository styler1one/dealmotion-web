-- ============================================================
-- i18n Language Support Migration
-- Version: 1.0
-- Date: 29 November 2025
-- 
-- Adds language preference columns to support:
-- - UI Language (stored in Supabase auth.users metadata)
-- - Working Language (organization default + user override)
-- - Client Communication Language (per prospect)
--
-- Supported languages: nl, en, de, fr, es, hi, ar
-- ============================================================

-- 1. Add working language default to organizations
ALTER TABLE organizations 
ADD COLUMN IF NOT EXISTS default_working_language TEXT DEFAULT 'nl';

-- Add check constraint for valid language codes
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'organizations_language_check'
    ) THEN
        ALTER TABLE organizations 
        ADD CONSTRAINT organizations_language_check 
        CHECK (default_working_language IN ('nl', 'en', 'de', 'fr', 'es', 'hi', 'ar'));
    END IF;
END $$;

-- 2. Add working language override for users (per organization membership)
ALTER TABLE organization_members
ADD COLUMN IF NOT EXISTS working_language_override TEXT;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'org_members_language_check'
    ) THEN
        ALTER TABLE organization_members 
        ADD CONSTRAINT org_members_language_check 
        CHECK (working_language_override IS NULL OR working_language_override IN ('nl', 'en', 'de', 'fr', 'es', 'hi', 'ar'));
    END IF;
END $$;

-- 3. Add communication language preference to prospects
ALTER TABLE prospects
ADD COLUMN IF NOT EXISTS preferred_language TEXT DEFAULT 'nl';

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'prospects_language_check'
    ) THEN
        ALTER TABLE prospects 
        ADD CONSTRAINT prospects_language_check 
        CHECK (preferred_language IN ('nl', 'en', 'de', 'fr', 'es', 'hi', 'ar'));
    END IF;
END $$;

-- 4. Add language tracking to generated content

-- Research briefs
ALTER TABLE research_briefs
ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'nl';

-- Meeting preps
ALTER TABLE meeting_preps
ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'nl';

-- Follow-ups (both summary and email language)
ALTER TABLE followups
ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'nl';

ALTER TABLE followups
ADD COLUMN IF NOT EXISTS email_language TEXT DEFAULT 'en';

-- 5. Create index for prospect language filtering
CREATE INDEX IF NOT EXISTS idx_prospects_language 
ON prospects(organization_id, preferred_language);

-- 6. Create index for content language filtering
CREATE INDEX IF NOT EXISTS idx_research_briefs_language 
ON research_briefs(organization_id, language);

CREATE INDEX IF NOT EXISTS idx_meeting_preps_language 
ON meeting_preps(organization_id, language);

CREATE INDEX IF NOT EXISTS idx_followups_language 
ON followups(organization_id, language);

-- ============================================================
-- Migration complete!
-- 
-- Next steps:
-- 1. Run this migration in Supabase SQL Editor
-- 2. Verify columns exist with: SELECT * FROM information_schema.columns WHERE table_name = 'prospects';
-- 3. Check existing data has defaults: SELECT preferred_language, COUNT(*) FROM prospects GROUP BY preferred_language;
-- ============================================================

-- Log migration
DO $$
BEGIN
    RAISE NOTICE 'i18n language migration completed successfully';
    RAISE NOTICE 'Supported languages: nl, en, de, fr, es, hi, ar';
END $$;

