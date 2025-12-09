-- ============================================================
-- Migration: Link Existing Data to Prospects
-- Version: 1.0
-- Date: 30 November 2025
-- 
-- This script:
-- 1. Creates prospects from existing research_briefs
-- 2. Links research_briefs to prospects
-- 3. Links meeting_preps to prospects  
-- 4. Links followups to prospects
-- 5. Creates timeline entries for existing activities
-- ============================================================

-- ============================================================
-- STEP 1: Create prospects from research_briefs
-- ============================================================
-- For each unique company_name in research_briefs, create a prospect

INSERT INTO prospects (organization_id, company_name, status, created_at, last_activity_at)
SELECT DISTINCT 
  rb.organization_id,
  rb.company_name,
  CASE 
    WHEN EXISTS (SELECT 1 FROM followups f WHERE f.prospect_company_name = rb.company_name AND f.organization_id = rb.organization_id AND f.status = 'completed') THEN 'qualified'
    WHEN EXISTS (SELECT 1 FROM meeting_preps mp WHERE mp.prospect_company_name = rb.company_name AND mp.organization_id = rb.organization_id) THEN 'meeting_scheduled'
    ELSE 'researching'
  END as status,
  MIN(rb.created_at) as created_at,
  GREATEST(
    MAX(rb.completed_at),
    (SELECT MAX(mp.completed_at) FROM meeting_preps mp WHERE mp.prospect_company_name = rb.company_name AND mp.organization_id = rb.organization_id),
    (SELECT MAX(f.completed_at) FROM followups f WHERE f.prospect_company_name = rb.company_name AND f.organization_id = rb.organization_id)
  ) as last_activity_at
FROM research_briefs rb
WHERE rb.prospect_id IS NULL
  AND rb.company_name IS NOT NULL
  AND rb.company_name != ''
GROUP BY rb.organization_id, rb.company_name
ON CONFLICT (organization_id, company_name_normalized) DO NOTHING;

-- ============================================================
-- STEP 2: Link research_briefs to prospects
-- ============================================================

UPDATE research_briefs rb
SET prospect_id = p.id
FROM prospects p
WHERE rb.prospect_id IS NULL
  AND rb.organization_id = p.organization_id
  AND LOWER(TRIM(rb.company_name)) = p.company_name_normalized;

-- ============================================================
-- STEP 3: Link meeting_preps to prospects
-- ============================================================

-- First, create prospects for any meeting_preps that don't have a matching research
INSERT INTO prospects (organization_id, company_name, status, created_at)
SELECT DISTINCT 
  mp.organization_id,
  mp.prospect_company_name,
  'meeting_scheduled',
  MIN(mp.created_at)
FROM meeting_preps mp
WHERE mp.prospect_id IS NULL
  AND mp.prospect_company_name IS NOT NULL
  AND mp.prospect_company_name != ''
  AND NOT EXISTS (
    SELECT 1 FROM prospects p 
    WHERE p.organization_id = mp.organization_id 
    AND p.company_name_normalized = LOWER(TRIM(mp.prospect_company_name))
  )
GROUP BY mp.organization_id, mp.prospect_company_name
ON CONFLICT (organization_id, company_name_normalized) DO NOTHING;

-- Now link meeting_preps to prospects
UPDATE meeting_preps mp
SET prospect_id = p.id
FROM prospects p
WHERE mp.prospect_id IS NULL
  AND mp.organization_id = p.organization_id
  AND LOWER(TRIM(mp.prospect_company_name)) = p.company_name_normalized;

-- ============================================================
-- STEP 4: Link followups to prospects
-- ============================================================

-- First, create prospects for any followups that don't have a matching research/prep
INSERT INTO prospects (organization_id, company_name, status, created_at)
SELECT DISTINCT 
  f.organization_id,
  f.prospect_company_name,
  'qualified',
  MIN(f.created_at)
FROM followups f
WHERE f.prospect_id IS NULL
  AND f.prospect_company_name IS NOT NULL
  AND f.prospect_company_name != ''
  AND NOT EXISTS (
    SELECT 1 FROM prospects p 
    WHERE p.organization_id = f.organization_id 
    AND p.company_name_normalized = LOWER(TRIM(f.prospect_company_name))
  )
GROUP BY f.organization_id, f.prospect_company_name
ON CONFLICT (organization_id, company_name_normalized) DO NOTHING;

-- Now link followups to prospects
UPDATE followups f
SET prospect_id = p.id
FROM prospects p
WHERE f.prospect_id IS NULL
  AND f.organization_id = p.organization_id
  AND LOWER(TRIM(f.prospect_company_name)) = p.company_name_normalized;

-- ============================================================
-- STEP 5: Link prospect_contacts to prospects
-- ============================================================
-- Contacts should already be linked via prospect_id from research
-- But let's make sure any orphaned contacts get linked

UPDATE prospect_contacts pc
SET prospect_id = p.id
FROM prospects p, research_briefs rb
WHERE pc.prospect_id IS NULL
  AND rb.id = (
    SELECT rb2.id FROM research_briefs rb2 
    WHERE rb2.organization_id = pc.organization_id 
    ORDER BY rb2.created_at DESC 
    LIMIT 1
  )
  AND p.organization_id = pc.organization_id
  AND p.id = rb.prospect_id;

-- ============================================================
-- STEP 6: Update prospect metadata
-- ============================================================

-- Update last_activity_at for all prospects
UPDATE prospects p
SET last_activity_at = GREATEST(
  COALESCE(p.last_activity_at, p.created_at),
  COALESCE((SELECT MAX(rb.completed_at) FROM research_briefs rb WHERE rb.prospect_id = p.id), p.created_at),
  COALESCE((SELECT MAX(mp.completed_at) FROM meeting_preps mp WHERE mp.prospect_id = p.id), p.created_at),
  COALESCE((SELECT MAX(f.completed_at) FROM followups f WHERE f.prospect_id = p.id), p.created_at)
);

-- Update status based on activity
UPDATE prospects p
SET status = CASE 
  WHEN EXISTS (SELECT 1 FROM followups f WHERE f.prospect_id = p.id AND f.status = 'completed') THEN 'qualified'
  WHEN EXISTS (SELECT 1 FROM meeting_preps mp WHERE mp.prospect_id = p.id AND mp.status = 'completed') THEN 'meeting_scheduled'
  WHEN EXISTS (SELECT 1 FROM research_briefs rb WHERE rb.prospect_id = p.id AND rb.status = 'completed') THEN 'researching'
  ELSE 'new'
END;

-- ============================================================
-- STEP 7: Create timeline entries for existing activities
-- ============================================================

-- Add research activities to timeline
INSERT INTO prospect_activities (prospect_id, organization_id, activity_type, activity_id, title, description, icon, created_at, created_by)
SELECT 
  rb.prospect_id,
  rb.organization_id,
  'research',
  rb.id,
  'Research completed',
  'Research brief generated for ' || rb.company_name,
  '🔍',
  COALESCE(rb.completed_at, rb.created_at),
  rb.user_id
FROM research_briefs rb
WHERE rb.prospect_id IS NOT NULL
  AND rb.status = 'completed'
  AND NOT EXISTS (
    SELECT 1 FROM prospect_activities pa 
    WHERE pa.activity_id = rb.id 
    AND pa.activity_type = 'research'
  );

-- Add prep activities to timeline
INSERT INTO prospect_activities (prospect_id, organization_id, activity_type, activity_id, title, description, icon, created_at, created_by)
SELECT 
  mp.prospect_id,
  mp.organization_id,
  'prep',
  mp.id,
  'Meeting prep completed',
  COALESCE(mp.meeting_type, 'Meeting') || ' preparation ready',
  '📋',
  COALESCE(mp.completed_at, mp.created_at),
  mp.user_id
FROM meeting_preps mp
WHERE mp.prospect_id IS NOT NULL
  AND mp.status = 'completed'
  AND NOT EXISTS (
    SELECT 1 FROM prospect_activities pa 
    WHERE pa.activity_id = mp.id 
    AND pa.activity_type = 'prep'
  );

-- Add followup activities to timeline
INSERT INTO prospect_activities (prospect_id, organization_id, activity_type, activity_id, title, description, icon, created_at, created_by)
SELECT 
  f.prospect_id,
  f.organization_id,
  'followup',
  f.id,
  'Follow-up completed',
  COALESCE(f.meeting_subject, 'Meeting') || ' follow-up processed',
  '📝',
  COALESCE(f.completed_at, f.created_at),
  f.user_id
FROM followups f
WHERE f.prospect_id IS NOT NULL
  AND f.status = 'completed'
  AND NOT EXISTS (
    SELECT 1 FROM prospect_activities pa 
    WHERE pa.activity_id = f.id 
    AND pa.activity_type = 'followup'
  );

-- ============================================================
-- VERIFICATION QUERIES (run these to check the migration)
-- ============================================================

-- Check prospects created
-- SELECT COUNT(*) as total_prospects FROM prospects;

-- Check linked research briefs
-- SELECT COUNT(*) as linked_research FROM research_briefs WHERE prospect_id IS NOT NULL;

-- Check linked meeting preps
-- SELECT COUNT(*) as linked_preps FROM meeting_preps WHERE prospect_id IS NOT NULL;

-- Check linked followups
-- SELECT COUNT(*) as linked_followups FROM followups WHERE prospect_id IS NOT NULL;

-- Check timeline entries
-- SELECT COUNT(*) as timeline_entries FROM prospect_activities;

-- View prospect hub summary
-- SELECT * FROM prospect_hub_summary ORDER BY last_activity_at DESC;

-- ============================================================
-- DONE! Run this in Supabase SQL Editor
-- ============================================================
