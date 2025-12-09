-- ============================================================
-- Migration: Add prospect_contacts table
-- Version: 2.1
-- Date: 2024-11-28
-- 
-- Purpose: Support multiple contacts per prospect with 
-- LinkedIn analysis data for personalized sales approach
-- ============================================================

-- ============================================================
-- 1. CREATE PROSPECT_CONTACTS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS prospect_contacts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- ========== Basic Contact Info ==========
  name TEXT NOT NULL,
  role TEXT,                          -- Job title / function
  email TEXT,
  phone TEXT,
  linkedin_url TEXT,
  
  -- ========== LinkedIn Analysis Data ==========
  -- Populated by AI analysis of LinkedIn profile
  linkedin_headline TEXT,             -- Their LinkedIn headline
  linkedin_summary TEXT,              -- Career summary / about section
  linkedin_experience JSONB,          -- Previous roles [{company, title, duration}]
  linkedin_activity_level TEXT,       -- 'active', 'moderate', 'passive'
  linkedin_post_themes TEXT[],        -- Topics they post about
  
  -- ========== AI-Generated Insights ==========
  communication_style TEXT,           -- 'formal', 'informal', 'technical', 'strategic'
  probable_drivers TEXT,              -- What motivates them (progress, fixing, standing out)
  decision_authority TEXT,            -- 'decision_maker', 'influencer', 'gatekeeper', 'user'
  urgency_signals TEXT,               -- Any signals of urgency or frustration
  
  -- ========== Sales-Relevant Analysis ==========
  profile_brief TEXT,                 -- Full markdown analysis
  pain_points_for_role TEXT,          -- Role-specific pain points
  conversation_approach TEXT,         -- How to approach this person
  opening_suggestions TEXT[],         -- Suggested conversation openers
  questions_to_ask TEXT[],            -- Discovery questions for this person
  topics_to_avoid TEXT[],             -- Sensitivities to be aware of
  
  -- ========== Relationship Tracking ==========
  is_primary BOOLEAN DEFAULT false,   -- Primary contact for this prospect
  relationship_strength TEXT,         -- 'new', 'warm', 'strong'
  last_contact_date TIMESTAMPTZ,
  notes TEXT,
  
  -- ========== Meta ==========
  analyzed_at TIMESTAMPTZ,            -- When LinkedIn was last analyzed
  analysis_source TEXT,               -- 'linkedin', 'manual', 'crm_import'
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. INDEXES FOR PERFORMANCE
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_prospect_contacts_prospect 
  ON prospect_contacts(prospect_id);

CREATE INDEX IF NOT EXISTS idx_prospect_contacts_org 
  ON prospect_contacts(organization_id);

CREATE INDEX IF NOT EXISTS idx_prospect_contacts_primary 
  ON prospect_contacts(prospect_id, is_primary) 
  WHERE is_primary = true;

CREATE INDEX IF NOT EXISTS idx_prospect_contacts_name 
  ON prospect_contacts(organization_id, LOWER(name));

-- ============================================================
-- 3. ROW LEVEL SECURITY
-- ============================================================
ALTER TABLE prospect_contacts ENABLE ROW LEVEL SECURITY;

-- Users can view contacts in their organization
CREATE POLICY "Users can view own org contacts"
  ON prospect_contacts FOR SELECT
  USING (
    organization_id IN (
      SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
    )
  );

-- Users can insert contacts in their organization
CREATE POLICY "Users can insert own org contacts"
  ON prospect_contacts FOR INSERT
  WITH CHECK (
    organization_id IN (
      SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
    )
  );

-- Users can update contacts in their organization
CREATE POLICY "Users can update own org contacts"
  ON prospect_contacts FOR UPDATE
  USING (
    organization_id IN (
      SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
    )
  );

-- Users can delete contacts in their organization
CREATE POLICY "Users can delete own org contacts"
  ON prospect_contacts FOR DELETE
  USING (
    organization_id IN (
      SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
    )
  );

-- ============================================================
-- 4. SERVICE ROLE POLICIES (for backend)
-- ============================================================
CREATE POLICY "Service role full access to contacts"
  ON prospect_contacts FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- ============================================================
-- 5. TRIGGER: Auto-update updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION update_prospect_contacts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_prospect_contacts_updated_at ON prospect_contacts;
CREATE TRIGGER trigger_prospect_contacts_updated_at
  BEFORE UPDATE ON prospect_contacts
  FOR EACH ROW
  EXECUTE FUNCTION update_prospect_contacts_updated_at();

-- ============================================================
-- 6. TRIGGER: Ensure only one primary contact per prospect
-- ============================================================
CREATE OR REPLACE FUNCTION ensure_single_primary_contact()
RETURNS TRIGGER AS $$
BEGIN
  -- If setting this contact as primary, unset others
  IF NEW.is_primary = true THEN
    UPDATE prospect_contacts 
    SET is_primary = false 
    WHERE prospect_id = NEW.prospect_id 
      AND id != NEW.id 
      AND is_primary = true;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_single_primary_contact ON prospect_contacts;
CREATE TRIGGER trigger_single_primary_contact
  BEFORE INSERT OR UPDATE ON prospect_contacts
  FOR EACH ROW
  WHEN (NEW.is_primary = true)
  EXECUTE FUNCTION ensure_single_primary_contact();

-- ============================================================
-- 7. LINK TO RESEARCH_BRIEFS (optional)
-- ============================================================
-- Add column to track which contact was analyzed for a research
ALTER TABLE research_briefs 
ADD COLUMN IF NOT EXISTS contact_id UUID REFERENCES prospect_contacts(id);

-- Index for lookup
CREATE INDEX IF NOT EXISTS idx_research_briefs_contact 
  ON research_briefs(contact_id) 
  WHERE contact_id IS NOT NULL;

-- ============================================================
-- 8. MIGRATE EXISTING CONTACT DATA FROM PROSPECTS
-- ============================================================
-- This creates prospect_contacts records from existing prospects.contact_* fields
INSERT INTO prospect_contacts (
  prospect_id,
  organization_id,
  name,
  role,
  email,
  linkedin_url,
  is_primary,
  analysis_source
)
SELECT 
  p.id as prospect_id,
  p.organization_id,
  p.contact_name as name,
  p.contact_role as role,
  p.contact_email as email,
  p.contact_linkedin as linkedin_url,
  true as is_primary,
  'migrated' as analysis_source
FROM prospects p
WHERE p.contact_name IS NOT NULL
  AND p.contact_name != ''
ON CONFLICT DO NOTHING;

-- ============================================================
-- 9. HELPER FUNCTION: Get or create contact
-- ============================================================
CREATE OR REPLACE FUNCTION get_or_create_prospect_contact(
  p_prospect_id UUID,
  p_organization_id UUID,
  p_name TEXT,
  p_role TEXT DEFAULT NULL,
  p_linkedin_url TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
  v_contact_id UUID;
BEGIN
  -- Try to find existing contact by name (case-insensitive)
  SELECT id INTO v_contact_id
  FROM prospect_contacts
  WHERE prospect_id = p_prospect_id
    AND LOWER(TRIM(name)) = LOWER(TRIM(p_name))
  LIMIT 1;
  
  -- If not found, create new contact
  IF v_contact_id IS NULL THEN
    INSERT INTO prospect_contacts (
      prospect_id, 
      organization_id, 
      name, 
      role, 
      linkedin_url,
      is_primary
    )
    VALUES (
      p_prospect_id, 
      p_organization_id, 
      p_name, 
      p_role, 
      p_linkedin_url,
      -- Make primary if this is the first contact for the prospect
      NOT EXISTS (SELECT 1 FROM prospect_contacts WHERE prospect_id = p_prospect_id)
    )
    RETURNING id INTO v_contact_id;
  END IF;
  
  RETURN v_contact_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- DONE! 
-- 
-- New table: prospect_contacts
-- - Multiple contacts per prospect
-- - LinkedIn analysis storage
-- - AI-generated insights
-- - Conversation tips
-- - RLS policies
-- - Auto-migration of existing contact data
-- ============================================================

