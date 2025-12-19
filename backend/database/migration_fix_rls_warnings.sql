-- ============================================================
-- Migration: Fix RLS Performance Warnings
-- Date: 19 December 2025
-- 
-- Fixes 76 Supabase SQL Linter warnings:
-- 1. auth_rls_initplan: Replace auth.uid() with (select auth.uid())
-- 2. multiple_permissive_policies: Remove redundant service role policies
--    (service_role already bypasses RLS, so these policies are unnecessary)
-- 
-- Tables affected:
-- - mobile_recordings (4 policies)
-- - auto_record_settings (4 policies)
-- - autopilot_proposals (4 policies)
-- - autopilot_settings (2 policies)
-- - meeting_outcomes (4 policies)
-- - user_prep_preferences (2 policies)
-- ============================================================

-- ============================================================
-- 1. MOBILE_RECORDINGS - Fix auth.uid() and subqueries
-- ============================================================

-- Drop existing policies
DROP POLICY IF EXISTS "Users can view own org recordings" ON mobile_recordings;
DROP POLICY IF EXISTS "Users can insert recordings" ON mobile_recordings;
DROP POLICY IF EXISTS "Users can update own recordings" ON mobile_recordings;
DROP POLICY IF EXISTS "Users can delete own recordings" ON mobile_recordings;

-- Recreate with (select auth.uid()) pattern
CREATE POLICY "Users can view own org recordings" ON mobile_recordings
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can insert recordings" ON mobile_recordings
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can update own recordings" ON mobile_recordings
    FOR UPDATE
    USING (user_id = (select auth.uid()))
    WITH CHECK (user_id = (select auth.uid()));

CREATE POLICY "Users can delete own recordings" ON mobile_recordings
    FOR DELETE
    USING (user_id = (select auth.uid()));

-- ============================================================
-- 2. AUTO_RECORD_SETTINGS - Fix auth.uid()
-- ============================================================

DROP POLICY IF EXISTS "Users can view own auto_record_settings" ON auto_record_settings;
DROP POLICY IF EXISTS "Users can insert own auto_record_settings" ON auto_record_settings;
DROP POLICY IF EXISTS "Users can update own auto_record_settings" ON auto_record_settings;
DROP POLICY IF EXISTS "Users can delete own auto_record_settings" ON auto_record_settings;

CREATE POLICY "Users can view own auto_record_settings" ON auto_record_settings
    FOR SELECT
    USING (user_id = (select auth.uid()));

CREATE POLICY "Users can insert own auto_record_settings" ON auto_record_settings
    FOR INSERT
    WITH CHECK (user_id = (select auth.uid()));

CREATE POLICY "Users can update own auto_record_settings" ON auto_record_settings
    FOR UPDATE
    USING (user_id = (select auth.uid()));

CREATE POLICY "Users can delete own auto_record_settings" ON auto_record_settings
    FOR DELETE
    USING (user_id = (select auth.uid()));

-- ============================================================
-- 3. AUTOPILOT_PROPOSALS - Fix auth.uid() and remove service role policy
-- ============================================================

-- Remove redundant service role policy (service_role bypasses RLS anyway)
DROP POLICY IF EXISTS "Service role can manage all proposals" ON autopilot_proposals;

-- Drop and recreate user policies with (select auth.uid())
DROP POLICY IF EXISTS "Users can view own proposals" ON autopilot_proposals;
DROP POLICY IF EXISTS "Users can update own proposals" ON autopilot_proposals;
DROP POLICY IF EXISTS "Users can insert own proposals" ON autopilot_proposals;

CREATE POLICY "Users can view own proposals" ON autopilot_proposals
    FOR SELECT
    USING (user_id = (select auth.uid()));

CREATE POLICY "Users can update own proposals" ON autopilot_proposals
    FOR UPDATE
    USING (user_id = (select auth.uid()));

CREATE POLICY "Users can insert own proposals" ON autopilot_proposals
    FOR INSERT
    WITH CHECK (user_id = (select auth.uid()));

-- ============================================================
-- 4. AUTOPILOT_SETTINGS - Fix auth.uid() and remove service role policy
-- ============================================================

DROP POLICY IF EXISTS "Service role can manage all settings" ON autopilot_settings;
DROP POLICY IF EXISTS "Users can manage own settings" ON autopilot_settings;

CREATE POLICY "Users can manage own settings" ON autopilot_settings
    FOR ALL
    USING (user_id = (select auth.uid()));

-- ============================================================
-- 5. MEETING_OUTCOMES - Fix auth.uid() and remove service role policy
-- ============================================================

DROP POLICY IF EXISTS "Service role can manage all outcomes" ON meeting_outcomes;
DROP POLICY IF EXISTS "Users can view own outcomes" ON meeting_outcomes;
DROP POLICY IF EXISTS "Users can insert own outcomes" ON meeting_outcomes;
DROP POLICY IF EXISTS "Users can update own outcomes" ON meeting_outcomes;

CREATE POLICY "Users can view own outcomes" ON meeting_outcomes
    FOR SELECT
    USING (user_id = (select auth.uid()));

CREATE POLICY "Users can insert own outcomes" ON meeting_outcomes
    FOR INSERT
    WITH CHECK (user_id = (select auth.uid()));

CREATE POLICY "Users can update own outcomes" ON meeting_outcomes
    FOR UPDATE
    USING (user_id = (select auth.uid()));

-- ============================================================
-- 6. USER_PREP_PREFERENCES - Fix auth.uid() and remove service role policy
-- ============================================================

DROP POLICY IF EXISTS "Service role can manage all preferences" ON user_prep_preferences;
DROP POLICY IF EXISTS "Users can manage own preferences" ON user_prep_preferences;

CREATE POLICY "Users can manage own preferences" ON user_prep_preferences
    FOR ALL
    USING (user_id = (select auth.uid()));

-- ============================================================
-- VERIFICATION
-- ============================================================
-- After running this migration, verify in Supabase SQL Linter:
-- 1. auth_rls_initplan warnings should be reduced
-- 2. multiple_permissive_policies warnings should be eliminated
--
-- Note: Service role (used by backend) automatically bypasses RLS,
-- so explicit service role policies are unnecessary and cause
-- the "multiple permissive policies" warning.
-- ============================================================
