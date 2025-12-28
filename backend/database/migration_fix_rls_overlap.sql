-- ============================================================
-- Migration: Fix RLS Policy Overlap
-- Date: 23 December 2025
-- 
-- Problem: Using FOR ALL creates implicit SELECT policy that overlaps
-- with explicit *_select policies.
--
-- Solution: Remove *_all policies and use specific action policies instead
-- ============================================================

-- ============================================================
-- AFFILIATE_COMMISSIONS
-- ============================================================
-- Remove the overlapping _all policy (which covers SELECT too)
DROP POLICY IF EXISTS "affiliate_commissions_all" ON affiliate_commissions;

-- Add specific policies for non-SELECT actions
CREATE POLICY "affiliate_commissions_insert" ON affiliate_commissions
    FOR INSERT WITH CHECK (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliate_commissions_update" ON affiliate_commissions
    FOR UPDATE USING (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliate_commissions_delete" ON affiliate_commissions
    FOR DELETE USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- AFFILIATE_EVENTS
-- ============================================================
DROP POLICY IF EXISTS "affiliate_events_all" ON affiliate_events;

CREATE POLICY "affiliate_events_insert" ON affiliate_events
    FOR INSERT WITH CHECK (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliate_events_update" ON affiliate_events
    FOR UPDATE USING (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliate_events_delete" ON affiliate_events
    FOR DELETE USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- AFFILIATE_PAYOUTS
-- ============================================================
DROP POLICY IF EXISTS "affiliate_payouts_all" ON affiliate_payouts;

CREATE POLICY "affiliate_payouts_insert" ON affiliate_payouts
    FOR INSERT WITH CHECK (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliate_payouts_update" ON affiliate_payouts
    FOR UPDATE USING (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "affiliate_payouts_delete" ON affiliate_payouts
    FOR DELETE USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- CREDIT_TRANSACTIONS
-- ============================================================
DROP POLICY IF EXISTS "credit_transactions_all" ON credit_transactions;

CREATE POLICY "credit_transactions_insert" ON credit_transactions
    FOR INSERT WITH CHECK (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "credit_transactions_update" ON credit_transactions
    FOR UPDATE USING (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "credit_transactions_delete" ON credit_transactions
    FOR DELETE USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- CREDIT_BALANCES
-- ============================================================
DROP POLICY IF EXISTS "credit_balances_all" ON credit_balances;

CREATE POLICY "credit_balances_insert" ON credit_balances
    FOR INSERT WITH CHECK (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "credit_balances_update" ON credit_balances
    FOR UPDATE USING (
        (select auth.role()) = 'service_role'
    );

CREATE POLICY "credit_balances_delete" ON credit_balances
    FOR DELETE USING (
        (select auth.role()) = 'service_role'
    );

-- ============================================================
-- DONE
-- ============================================================
-- This removes the FOR ALL policies that were causing overlap
-- with the specific FOR SELECT policies.
-- ============================================================
