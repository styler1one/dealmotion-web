-- Migration: Add custom_notes column to research_briefs
-- Date: 2025-12-15
-- Description: Allows users to add their own intel/notes when starting research

-- Add custom_notes column to research_briefs if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'research_briefs' AND column_name = 'custom_notes'
    ) THEN
        ALTER TABLE research_briefs ADD COLUMN custom_notes TEXT;
        COMMENT ON COLUMN research_briefs.custom_notes IS 'User-provided intel about the prospect that supplements the AI research';
    END IF;
END $$;
