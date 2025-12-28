-- ============================================================
-- Migration: Fix RLS Performance Issues
-- Date: 23 December 2025
-- 
-- Fixes:
-- 1. auth_rls_initplan: Wrap auth.uid()/auth.role() in (select ...)
-- 2. multiple_permissive_policies: Consolidate overlapping policies
--
-- Tables affected:
-- - affiliates, affiliate_clicks, affiliate_referrals, affiliate_commissions
-- - affiliate_payouts, affiliate_events
-- - magic_onboarding_sessions, profile_chat_sessions
-- - prospecting_searches, prospecting_results
-- - api_usage_logs, credit_transactions, credit_balances
-- ============================================================

-- ============================================================
-- AFFILIATES
-- ============================================================
DROP POLICY IF EXISTS "affiliates_select_own" ON affiliates;
DROP POLICY IF EXISTS "affiliates_update_own" ON affiliates;
DROP POLICY IF EXISTS "affiliates_service_all" ON affiliates;

-- Combined policy: users can see/update their own OR service_role can do all
CREATE POLICY "affiliates_select" ON affiliates
    FOR SELECT USING (
        user_id = (select auth.uid()) 
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliates_update" ON affiliates
    FOR UPDATE USING (
        user_id = (select auth.uid()) 
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliates_insert" ON affiliates
    FOR INSERT WITH CHECK (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliates_delete" ON affiliates
    FOR DELETE USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- AFFILIATE_CLICKS
-- ============================================================
DROP POLICY IF EXISTS "affiliate_clicks_select_own" ON affiliate_clicks;
DROP POLICY IF EXISTS "affiliate_clicks_insert_any" ON affiliate_clicks;
DROP POLICY IF EXISTS "affiliate_clicks_service_all" ON affiliate_clicks;

-- Anyone can insert (public click tracking)
CREATE POLICY "affiliate_clicks_insert" ON affiliate_clicks
    FOR INSERT WITH CHECK (true);

-- Affiliates can see their own clicks, service_role can see all
CREATE POLICY "affiliate_clicks_select" ON affiliate_clicks
    FOR SELECT USING (
        affiliate_id IN (
            SELECT id FROM affiliates WHERE user_id = (select auth.uid())
        )
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliate_clicks_update" ON affiliate_clicks
    FOR UPDATE USING (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliate_clicks_delete" ON affiliate_clicks
    FOR DELETE USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- AFFILIATE_REFERRALS
-- ============================================================
DROP POLICY IF EXISTS "affiliate_referrals_select_own" ON affiliate_referrals;
DROP POLICY IF EXISTS "affiliate_referrals_service_all" ON affiliate_referrals;

CREATE POLICY "affiliate_referrals_select" ON affiliate_referrals
    FOR SELECT USING (
        affiliate_id IN (
            SELECT id FROM affiliates WHERE user_id = (select auth.uid())
        )
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliate_referrals_insert" ON affiliate_referrals
    FOR INSERT WITH CHECK (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliate_referrals_update" ON affiliate_referrals
    FOR UPDATE USING (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliate_referrals_delete" ON affiliate_referrals
    FOR DELETE USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- AFFILIATE_COMMISSIONS
-- ============================================================
DROP POLICY IF EXISTS "affiliate_commissions_select_own" ON affiliate_commissions;
DROP POLICY IF EXISTS "affiliate_commissions_service_all" ON affiliate_commissions;

CREATE POLICY "affiliate_commissions_select" ON affiliate_commissions
    FOR SELECT USING (
        affiliate_id IN (
            SELECT id FROM affiliates WHERE user_id = (select auth.uid())
        )
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliate_commissions_all" ON affiliate_commissions
    FOR ALL USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- AFFILIATE_PAYOUTS
-- ============================================================
DROP POLICY IF EXISTS "affiliate_payouts_select_own" ON affiliate_payouts;
DROP POLICY IF EXISTS "affiliate_payouts_service_all" ON affiliate_payouts;

CREATE POLICY "affiliate_payouts_select" ON affiliate_payouts
    FOR SELECT USING (
        affiliate_id IN (
            SELECT id FROM affiliates WHERE user_id = (select auth.uid())
        )
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliate_payouts_all" ON affiliate_payouts
    FOR ALL USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- AFFILIATE_EVENTS
-- ============================================================
DROP POLICY IF EXISTS "affiliate_events_select_own" ON affiliate_events;
DROP POLICY IF EXISTS "affiliate_events_service_all" ON affiliate_events;

CREATE POLICY "affiliate_events_select" ON affiliate_events
    FOR SELECT USING (
        affiliate_id IN (
            SELECT id FROM affiliates WHERE user_id = (select auth.uid())
        )
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliate_events_all" ON affiliate_events
    FOR ALL USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- MAGIC_ONBOARDING_SESSIONS
-- ============================================================
DROP POLICY IF EXISTS "Users can view own sessions" ON magic_onboarding_sessions;
DROP POLICY IF EXISTS "Users can insert own sessions" ON magic_onboarding_sessions;
DROP POLICY IF EXISTS "Service role can manage all sessions" ON magic_onboarding_sessions;

CREATE POLICY "magic_onboarding_sessions_select" ON magic_onboarding_sessions
    FOR SELECT USING (
        user_id = (select auth.uid())
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "magic_onboarding_sessions_insert" ON magic_onboarding_sessions
    FOR INSERT WITH CHECK (
        user_id = (select auth.uid())
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "magic_onboarding_sessions_update" ON magic_onboarding_sessions
    FOR UPDATE USING (
        user_id = (select auth.uid())
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "magic_onboarding_sessions_delete" ON magic_onboarding_sessions
    FOR DELETE USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- PROFILE_CHAT_SESSIONS
-- ============================================================
DROP POLICY IF EXISTS "Users can view own chat sessions" ON profile_chat_sessions;
DROP POLICY IF EXISTS "Users can insert own chat sessions" ON profile_chat_sessions;
DROP POLICY IF EXISTS "Users can update own chat sessions" ON profile_chat_sessions;
DROP POLICY IF EXISTS "Service role can manage all sessions" ON profile_chat_sessions;

CREATE POLICY "profile_chat_sessions_select" ON profile_chat_sessions
    FOR SELECT USING (
        user_id = (select auth.uid())
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "profile_chat_sessions_insert" ON profile_chat_sessions
    FOR INSERT WITH CHECK (
        user_id = (select auth.uid())
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "profile_chat_sessions_update" ON profile_chat_sessions
    FOR UPDATE USING (
        user_id = (select auth.uid())
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "profile_chat_sessions_delete" ON profile_chat_sessions
    FOR DELETE USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- PROSPECTING_SEARCHES
-- ============================================================
DROP POLICY IF EXISTS "Users can view own org searches" ON prospecting_searches;
DROP POLICY IF EXISTS "Users can insert own searches" ON prospecting_searches;
DROP POLICY IF EXISTS "Users can update own searches" ON prospecting_searches;
DROP POLICY IF EXISTS "Users can delete own searches" ON prospecting_searches;
DROP POLICY IF EXISTS "Service role can manage all searches" ON prospecting_searches;

CREATE POLICY "prospecting_searches_select" ON prospecting_searches
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "prospecting_searches_insert" ON prospecting_searches
    FOR INSERT WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "prospecting_searches_update" ON prospecting_searches
    FOR UPDATE USING (
        user_id = (select auth.uid())
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "prospecting_searches_delete" ON prospecting_searches
    FOR DELETE USING (
        user_id = (select auth.uid())
        OR (select auth.role()) = 'service_role'
    );

-- ============================================================
-- PROSPECTING_RESULTS
-- ============================================================
DROP POLICY IF EXISTS "Users can view own org results" ON prospecting_results;
DROP POLICY IF EXISTS "Users can update own org results" ON prospecting_results;
DROP POLICY IF EXISTS "Service role can manage all results" ON prospecting_results;

CREATE POLICY "prospecting_results_select" ON prospecting_results
    FOR SELECT USING (
        search_id IN (
            SELECT id FROM prospecting_searches 
            WHERE organization_id IN (
                SELECT organization_id FROM organization_members 
                WHERE user_id = (select auth.uid())
            )
        )
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "prospecting_results_update" ON prospecting_results
    FOR UPDATE USING (
        search_id IN (
            SELECT id FROM prospecting_searches 
            WHERE organization_id IN (
                SELECT organization_id FROM organization_members 
                WHERE user_id = (select auth.uid())
            )
        )
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "prospecting_results_insert" ON prospecting_results
    FOR INSERT WITH CHECK (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "prospecting_results_delete" ON prospecting_results
    FOR DELETE USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- API_USAGE_LOGS
-- ============================================================
DROP POLICY IF EXISTS "Users can view own org api usage" ON api_usage_logs;

CREATE POLICY "api_usage_logs_select" ON api_usage_logs
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
        OR (select auth.role()) = 'service_role'
    );

-- ============================================================
-- CREDIT_TRANSACTIONS
-- ============================================================
DROP POLICY IF EXISTS "Users can view own org credit transactions" ON credit_transactions;
DROP POLICY IF EXISTS "Service can manage credit transactions" ON credit_transactions;

CREATE POLICY "credit_transactions_select" ON credit_transactions
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "credit_transactions_all" ON credit_transactions
    FOR ALL USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- CREDIT_BALANCES
-- ============================================================
DROP POLICY IF EXISTS "Users can view own org credit balance" ON credit_balances;
DROP POLICY IF EXISTS "Service can manage credit balances" ON credit_balances;

CREATE POLICY "credit_balances_select" ON credit_balances
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
        OR (select auth.role()) = 'service_role'
    );

CREATE POLICY "credit_balances_all" ON credit_balances
    FOR ALL USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- DONE
-- ============================================================
-- After running:
-- 1. auth_rls_initplan warnings should be gone (using (select auth.uid()))
-- 2. multiple_permissive_policies warnings should be reduced
--
-- Remaining manual steps:
-- - Function search_path: Run migration_fix_function_search_path_v2.sql
-- - Leaked password protection: Enable in Supabase Dashboard
-- ============================================================
