-- Migration: RLS Performance Fix
-- Date: 5 December 2025
-- Fixes: auth_rls_initplan and multiple_permissive_policies warnings
-- 
-- Issues:
-- 1. auth.uid() re-evaluated for each row (should use (select auth.uid()))
-- 2. Multiple permissive policies for same role/action (consolidate)
--
-- Tables affected: coach_daily_tips, prospect_notes, flow_packs

-- ============================================
-- 1. FIX: coach_daily_tips
-- Table has: user_id (no organization_id)
-- ============================================

-- Drop existing policies
DROP POLICY IF EXISTS "Users can view own tips" ON coach_daily_tips;
DROP POLICY IF EXISTS "Users can insert own tips" ON coach_daily_tips;
DROP POLICY IF EXISTS "Service role full access" ON coach_daily_tips;

-- Create optimized policies with (select auth.uid())
-- Note: Service role bypasses RLS, so we don't need a separate policy for it

CREATE POLICY "coach_daily_tips_select" ON coach_daily_tips
    FOR SELECT
    TO authenticated
    USING (user_id = (SELECT auth.uid()));

CREATE POLICY "coach_daily_tips_insert" ON coach_daily_tips
    FOR INSERT
    TO authenticated
    WITH CHECK (user_id = (SELECT auth.uid()));

CREATE POLICY "coach_daily_tips_update" ON coach_daily_tips
    FOR UPDATE
    TO authenticated
    USING (user_id = (SELECT auth.uid()));

CREATE POLICY "coach_daily_tips_delete" ON coach_daily_tips
    FOR DELETE
    TO authenticated
    USING (user_id = (SELECT auth.uid()));

-- ============================================
-- 2. FIX: prospect_notes
-- Table has: user_id, organization_id (user_id for ownership)
-- ============================================

-- Drop existing policies
DROP POLICY IF EXISTS "Users can view notes in their organization" ON prospect_notes;
DROP POLICY IF EXISTS "Users can create notes in their organization" ON prospect_notes;
DROP POLICY IF EXISTS "Users can update their own notes" ON prospect_notes;
DROP POLICY IF EXISTS "Users can delete their own notes" ON prospect_notes;

-- Create optimized policies with (select auth.uid())
CREATE POLICY "prospect_notes_select" ON prospect_notes
    FOR SELECT
    TO authenticated
    USING (
        organization_id IN (
            SELECT om.organization_id 
            FROM organization_members om 
            WHERE om.user_id = (SELECT auth.uid())
        )
    );

CREATE POLICY "prospect_notes_insert" ON prospect_notes
    FOR INSERT
    TO authenticated
    WITH CHECK (
        organization_id IN (
            SELECT om.organization_id 
            FROM organization_members om 
            WHERE om.user_id = (SELECT auth.uid())
        )
        AND user_id = (SELECT auth.uid())
    );

CREATE POLICY "prospect_notes_update" ON prospect_notes
    FOR UPDATE
    TO authenticated
    USING (user_id = (SELECT auth.uid()));

CREATE POLICY "prospect_notes_delete" ON prospect_notes
    FOR DELETE
    TO authenticated
    USING (user_id = (SELECT auth.uid()));

-- ============================================
-- 3. FIX: flow_packs
-- Table has: organization_id
-- ============================================

-- Drop existing policies
DROP POLICY IF EXISTS "Users can view own org flow packs" ON flow_packs;
DROP POLICY IF EXISTS "Service role can manage flow packs" ON flow_packs;

-- Create optimized policy with (select auth.uid())
-- Note: Service role bypasses RLS, INSERT/UPDATE/DELETE handled by backend

CREATE POLICY "flow_packs_select" ON flow_packs
    FOR SELECT
    TO authenticated
    USING (
        organization_id IN (
            SELECT om.organization_id 
            FROM organization_members om 
            WHERE om.user_id = (SELECT auth.uid())
        )
    );

-- ============================================
-- VERIFICATION
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'RLS Performance Fix Migration Complete';
    RAISE NOTICE '- coach_daily_tips: 4 policies updated (user-based)';
    RAISE NOTICE '- prospect_notes: 4 policies updated (org + user-based)';
    RAISE NOTICE '- flow_packs: 1 policy updated (org-based)';
    RAISE NOTICE '- All policies now use (SELECT auth.uid()) for caching';
    RAISE NOTICE '- Service role policies removed (service role bypasses RLS)';
END $$;

-- Run this after migration to verify policies:
/*
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd
FROM pg_policies 
WHERE tablename IN ('coach_daily_tips', 'prospect_notes', 'flow_packs')
ORDER BY tablename, policyname;
*/
