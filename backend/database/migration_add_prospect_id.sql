-- ============================================================
-- MIGRATION: Add prospect_id to existing tables
-- Run this FIRST before the complete_schema.sql
-- ============================================================

-- 1. First create the prospects table if it doesn't exist
CREATE TABLE IF NOT EXISTS prospects (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- Core fields
  company_name TEXT NOT NULL,
  company_name_normalized TEXT GENERATED ALWAYS AS (LOWER(TRIM(company_name))) STORED,
  
  -- Optional enrichment
  website TEXT,
  linkedin_url TEXT,
  industry TEXT,
  company_size TEXT,
  country TEXT,
  city TEXT,
  
  -- Contact info (primary contact)
  contact_name TEXT,
  contact_email TEXT,
  contact_role TEXT,
  contact_linkedin TEXT,
  
  -- Status tracking
  status TEXT DEFAULT 'new' CHECK (status IN ('new', 'researching', 'qualified', 'meeting_scheduled', 'proposal_sent', 'won', 'lost', 'inactive')),
  
  -- Metadata
  notes TEXT,
  tags TEXT[],
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_activity_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Prevent duplicate prospects per org (normalized name)
  UNIQUE(organization_id, company_name_normalized)
);

-- 2. Add prospect_id column to research_briefs (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'research_briefs' AND column_name = 'prospect_id'
  ) THEN
    ALTER TABLE research_briefs ADD COLUMN prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL;
    CREATE INDEX IF NOT EXISTS idx_research_briefs_prospect ON research_briefs(prospect_id);
  END IF;
END $$;

-- 3. Add prospect_id column to meeting_preps (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'meeting_preps' AND column_name = 'prospect_id'
  ) THEN
    ALTER TABLE meeting_preps ADD COLUMN prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL;
    CREATE INDEX IF NOT EXISTS idx_meeting_preps_prospect ON meeting_preps(prospect_id);
  END IF;
END $$;

-- 4. Add prospect_id column to followups (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'followups' AND column_name = 'prospect_id'
  ) THEN
    ALTER TABLE followups ADD COLUMN prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL;
    CREATE INDEX IF NOT EXISTS idx_followups_prospect ON followups(prospect_id);
  END IF;
END $$;

-- 5. Create indexes on prospects table
CREATE INDEX IF NOT EXISTS idx_prospects_org ON prospects(organization_id);
CREATE INDEX IF NOT EXISTS idx_prospects_name_normalized ON prospects(company_name_normalized);
CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_prospects_last_activity ON prospects(organization_id, last_activity_at DESC);

-- 6. Enable RLS on prospects
ALTER TABLE prospects ENABLE ROW LEVEL SECURITY;

-- 7. Create RLS policies for prospects (drop first if exists to avoid errors)
DROP POLICY IF EXISTS "Users can view prospects in their org" ON prospects;
DROP POLICY IF EXISTS "Users can insert prospects in their org" ON prospects;
DROP POLICY IF EXISTS "Users can update prospects in their org" ON prospects;
DROP POLICY IF EXISTS "Users can delete prospects in their org" ON prospects;

-- Helper function (create or replace)
CREATE OR REPLACE FUNCTION get_user_org_ids()
RETURNS SETOF UUID AS $$
  SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
$$ LANGUAGE SQL SECURITY DEFINER;

CREATE POLICY "Users can view prospects in their org"
  ON prospects FOR SELECT
  USING (organization_id IN (SELECT get_user_org_ids()));

CREATE POLICY "Users can insert prospects in their org"
  ON prospects FOR INSERT
  WITH CHECK (organization_id IN (SELECT get_user_org_ids()));

CREATE POLICY "Users can update prospects in their org"
  ON prospects FOR UPDATE
  USING (organization_id IN (SELECT get_user_org_ids()));

CREATE POLICY "Users can delete prospects in their org"
  ON prospects FOR DELETE
  USING (organization_id IN (SELECT get_user_org_ids()));

-- 8. Create helper function for get_or_create_prospect
CREATE OR REPLACE FUNCTION get_or_create_prospect(
  p_organization_id UUID,
  p_company_name TEXT
) RETURNS UUID AS $$
DECLARE
  v_prospect_id UUID;
  v_normalized_name TEXT;
BEGIN
  v_normalized_name := LOWER(TRIM(p_company_name));
  
  -- Try to find existing prospect
  SELECT id INTO v_prospect_id
  FROM prospects
  WHERE organization_id = p_organization_id
    AND company_name_normalized = v_normalized_name;
  
  -- Create if not exists
  IF v_prospect_id IS NULL THEN
    INSERT INTO prospects (organization_id, company_name)
    VALUES (p_organization_id, p_company_name)
    RETURNING id INTO v_prospect_id;
  END IF;
  
  RETURN v_prospect_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 9. Create trigger to update prospect activity
CREATE OR REPLACE FUNCTION update_prospect_activity()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.prospect_id IS NOT NULL THEN
    UPDATE prospects SET last_activity_at = NOW() WHERE id = NEW.prospect_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing triggers first (to avoid duplicates)
DROP TRIGGER IF EXISTS update_prospect_activity_research ON research_briefs;
DROP TRIGGER IF EXISTS update_prospect_activity_prep ON meeting_preps;
DROP TRIGGER IF EXISTS update_prospect_activity_followup ON followups;

-- Create triggers
CREATE TRIGGER update_prospect_activity_research 
  AFTER INSERT OR UPDATE ON research_briefs
  FOR EACH ROW EXECUTE FUNCTION update_prospect_activity();

CREATE TRIGGER update_prospect_activity_prep 
  AFTER INSERT OR UPDATE ON meeting_preps
  FOR EACH ROW EXECUTE FUNCTION update_prospect_activity();

CREATE TRIGGER update_prospect_activity_followup 
  AFTER INSERT OR UPDATE ON followups
  FOR EACH ROW EXECUTE FUNCTION update_prospect_activity();

-- ============================================================
-- DONE! Now you can optionally run the data migration below
-- to link existing records to the new prospects table
-- ============================================================

-- Uncomment and run this to migrate existing data:
/*
DO $$
DECLARE
  r RECORD;
  v_prospect_id UUID;
BEGIN
  -- Migrate from research_briefs
  FOR r IN 
    SELECT DISTINCT organization_id, company_name 
    FROM research_briefs 
    WHERE prospect_id IS NULL AND company_name IS NOT NULL
  LOOP
    v_prospect_id := get_or_create_prospect(r.organization_id, r.company_name);
    UPDATE research_briefs 
    SET prospect_id = v_prospect_id 
    WHERE organization_id = r.organization_id 
      AND LOWER(TRIM(company_name)) = LOWER(TRIM(r.company_name))
      AND prospect_id IS NULL;
  END LOOP;
  
  -- Migrate from meeting_preps
  FOR r IN 
    SELECT DISTINCT organization_id, prospect_company_name 
    FROM meeting_preps 
    WHERE prospect_id IS NULL AND prospect_company_name IS NOT NULL
  LOOP
    v_prospect_id := get_or_create_prospect(r.organization_id, r.prospect_company_name);
    UPDATE meeting_preps 
    SET prospect_id = v_prospect_id 
    WHERE organization_id = r.organization_id 
      AND LOWER(TRIM(prospect_company_name)) = LOWER(TRIM(r.prospect_company_name))
      AND prospect_id IS NULL;
  END LOOP;
  
  -- Migrate from followups
  FOR r IN 
    SELECT DISTINCT organization_id, prospect_company_name 
    FROM followups 
    WHERE prospect_id IS NULL AND prospect_company_name IS NOT NULL
  LOOP
    v_prospect_id := get_or_create_prospect(r.organization_id, r.prospect_company_name);
    UPDATE followups 
    SET prospect_id = v_prospect_id 
    WHERE organization_id = r.organization_id 
      AND LOWER(TRIM(prospect_company_name)) = LOWER(TRIM(r.prospect_company_name))
      AND prospect_id IS NULL;
  END LOOP;
  
  RAISE NOTICE 'Migration completed!';
END $$;
*/
