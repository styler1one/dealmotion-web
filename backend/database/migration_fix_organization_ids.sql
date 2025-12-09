-- Migration: Fix Organization ID Mismatches
-- Date: 4 December 2025
-- Issue: company_profiles and sales_profiles were saved under "Personal - {email}" 
--        organizations while research/preps use organization_members org_id
-- Solution: Update profiles to use the organization_id from organization_members

-- ============================================
-- STEP 1: Identify affected users
-- ============================================

-- This query shows users with mismatched organization_ids
-- Run this BEFORE the migration to see who is affected:

/*
SELECT 
    sp.user_id,
    sp.full_name,
    sp.organization_id as sales_profile_org,
    om.organization_id as org_members_org,
    o1.name as profile_org_name,
    o2.name as members_org_name
FROM sales_profiles sp
JOIN organization_members om ON sp.user_id = om.user_id
LEFT JOIN organizations o1 ON sp.organization_id = o1.id
LEFT JOIN organizations o2 ON om.organization_id = o2.id
WHERE sp.organization_id != om.organization_id;
*/

-- ============================================
-- STEP 2: Update sales_profiles
-- ============================================

-- Update sales_profiles to use organization_id from organization_members
UPDATE sales_profiles sp
SET organization_id = om.organization_id
FROM organization_members om
WHERE sp.user_id = om.user_id
  AND sp.organization_id != om.organization_id;

-- ============================================
-- STEP 3: Update company_profiles
-- ============================================

-- First, we need to find which company_profiles need updating
-- Company profiles are linked to organizations, not directly to users
-- So we need to find the user through sales_profile or organization_members

-- Update company_profiles where the organization has a mismatched sales_profile
UPDATE company_profiles cp
SET organization_id = correct_org.org_id
FROM (
    SELECT 
        cp_inner.id as company_profile_id,
        om.organization_id as org_id
    FROM company_profiles cp_inner
    JOIN sales_profiles sp ON cp_inner.organization_id = sp.organization_id
    JOIN organization_members om ON sp.user_id = om.user_id
    WHERE cp_inner.organization_id != om.organization_id
) correct_org
WHERE cp.id = correct_org.company_profile_id;

-- ============================================
-- STEP 4: Verify the fix
-- ============================================

-- Run this AFTER the migration to verify no mismatches remain:

/*
SELECT 
    sp.user_id,
    sp.full_name,
    sp.organization_id as sales_profile_org,
    om.organization_id as org_members_org,
    CASE WHEN sp.organization_id = om.organization_id THEN 'OK' ELSE 'MISMATCH' END as status
FROM sales_profiles sp
JOIN organization_members om ON sp.user_id = om.user_id;
*/

-- ============================================
-- STEP 5: Clean up orphaned "Personal - email" organizations (OPTIONAL)
-- ============================================

-- Only run this if you want to clean up unused organizations
-- First check what would be deleted:

/*
SELECT o.* 
FROM organizations o
WHERE o.name LIKE 'Personal - %'
  AND NOT EXISTS (SELECT 1 FROM organization_members om WHERE om.organization_id = o.id)
  AND NOT EXISTS (SELECT 1 FROM company_profiles cp WHERE cp.organization_id = o.id)
  AND NOT EXISTS (SELECT 1 FROM sales_profiles sp WHERE sp.organization_id = o.id)
  AND NOT EXISTS (SELECT 1 FROM research_briefs rb WHERE rb.organization_id = o.id);
*/

-- Then delete if safe:
/*
DELETE FROM organizations o
WHERE o.name LIKE 'Personal - %'
  AND NOT EXISTS (SELECT 1 FROM organization_members om WHERE om.organization_id = o.id)
  AND NOT EXISTS (SELECT 1 FROM company_profiles cp WHERE cp.organization_id = o.id)
  AND NOT EXISTS (SELECT 1 FROM sales_profiles sp WHERE sp.organization_id = o.id)
  AND NOT EXISTS (SELECT 1 FROM research_briefs rb WHERE rb.organization_id = o.id);
*/

-- ============================================
-- NOTES
-- ============================================
-- 
-- This migration ensures that:
-- 1. All sales_profiles use the organization_id from organization_members
-- 2. All company_profiles are linked to the correct organization
-- 3. Future data will be consistent (code changes ensure this)
--
-- For the specific user mentioned (test2@agentboss.nl):
-- - sales_profile org: 7995a42a-1606-4fe8-8e32-1f88fba5077e (Personal - test2@agentboss.nl)
-- - organization_members org: 05231949-0ca8-4433-8665-7ed75e899112 (My Organization)
-- 
-- After migration, both will use: 05231949-0ca8-4433-8665-7ed75e899112

