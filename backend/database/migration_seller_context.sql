-- ============================================
-- MIGRATION: Seller Context & Style Guide
-- SPEC: SPEC-032-Seller-Context-Prompt-Architecture
-- TASK: TASK-036-Seller-Context-Prompt-Improvements
-- Date: December 2024
-- ============================================

-- ============================================
-- STEP 1: Add style_guide JSONB column
-- ============================================

ALTER TABLE sales_profiles
ADD COLUMN IF NOT EXISTS style_guide JSONB DEFAULT NULL;

COMMENT ON COLUMN sales_profiles.style_guide IS 
'AI-derived style guide containing: tone, formality, language_style, persuasion_style, emoji_usage, signoff, writing_length. Generated after interview completion.';

-- ============================================
-- STEP 2: Add new interview fields for style
-- ============================================

ALTER TABLE sales_profiles
ADD COLUMN IF NOT EXISTS email_tone TEXT,
ADD COLUMN IF NOT EXISTS uses_emoji BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS email_signoff TEXT,
ADD COLUMN IF NOT EXISTS writing_length_preference TEXT;

-- Note: persuasion_style is already captured via sales_methodology

COMMENT ON COLUMN sales_profiles.email_tone IS 'User preference for email tone: direct, warm, formal, casual';
COMMENT ON COLUMN sales_profiles.uses_emoji IS 'Whether user uses emojis in professional communication';
COMMENT ON COLUMN sales_profiles.email_signoff IS 'Preferred email sign-off phrase';
COMMENT ON COLUMN sales_profiles.writing_length_preference IS 'Preference for message length: concise, detailed';

-- ============================================
-- STEP 3: Create index for style_guide queries
-- ============================================

CREATE INDEX IF NOT EXISTS idx_sales_profiles_style_guide 
ON sales_profiles USING GIN (style_guide);

-- ============================================
-- STEP 4: Helper function to get style guide with defaults
-- ============================================

CREATE OR REPLACE FUNCTION get_style_guide_with_defaults(profile_row sales_profiles)
RETURNS JSONB AS $$
DECLARE
    result JSONB;
BEGIN
    -- If style_guide exists, return it
    IF profile_row.style_guide IS NOT NULL THEN
        RETURN profile_row.style_guide;
    END IF;
    
    -- Otherwise, derive from existing fields
    result := jsonb_build_object(
        'tone', COALESCE(
            CASE 
                WHEN profile_row.communication_style ILIKE '%direct%' THEN 'direct'
                WHEN profile_row.communication_style ILIKE '%warm%' OR profile_row.communication_style ILIKE '%relationship%' THEN 'warm'
                WHEN profile_row.communication_style ILIKE '%formal%' THEN 'formal'
                WHEN profile_row.communication_style ILIKE '%casual%' OR profile_row.communication_style ILIKE '%informal%' THEN 'casual'
                ELSE 'professional'
            END,
            'professional'
        ),
        'formality', 'professional',
        'language_style', 'business',
        'persuasion_style', COALESCE(
            CASE 
                WHEN profile_row.sales_methodology ILIKE '%challenger%' THEN 'logic'
                WHEN profile_row.sales_methodology ILIKE '%story%' OR profile_row.sales_methodology ILIKE '%narrative%' THEN 'story'
                WHEN profile_row.sales_methodology ILIKE '%reference%' OR profile_row.sales_methodology ILIKE '%social%' THEN 'reference'
                ELSE 'logic'
            END,
            'logic'
        ),
        'emoji_usage', COALESCE(profile_row.uses_emoji, false),
        'signoff', COALESCE(profile_row.email_signoff, 'Best regards'),
        'writing_length', COALESCE(profile_row.writing_length_preference, 'concise'),
        'generated_at', NULL,
        'confidence_score', 0.5
    );
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- VERIFICATION: Check columns exist
-- ============================================

DO $$
BEGIN
    -- Verify columns were added
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'sales_profiles' 
        AND column_name = 'style_guide'
    ) THEN
        RAISE NOTICE 'SUCCESS: style_guide column exists';
    ELSE
        RAISE EXCEPTION 'FAILED: style_guide column not created';
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'sales_profiles' 
        AND column_name = 'email_tone'
    ) THEN
        RAISE NOTICE 'SUCCESS: email_tone column exists';
    ELSE
        RAISE EXCEPTION 'FAILED: email_tone column not created';
    END IF;
END $$;

-- ============================================
-- DONE
-- ============================================
-- Run this migration in Supabase SQL Editor
-- After running, update interview_service.py with new questions

