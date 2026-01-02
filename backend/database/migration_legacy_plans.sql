-- ============================================================
-- MIGRATION: Convert Legacy Plans to New Plans + Fix Credit Balances
-- Date: January 2026
-- ============================================================

-- ============================================================
-- PART 1: Convert legacy plan IDs
-- ============================================================

-- 1. Check current state
SELECT plan_id, COUNT(*) as count 
FROM organization_subscriptions 
GROUP BY plan_id 
ORDER BY count DESC;

-- 2. Update subscriptions with light_solo to free
UPDATE organization_subscriptions 
SET plan_id = 'free', updated_at = NOW()
WHERE plan_id = 'light_solo';

-- 3. Update subscriptions with pro_solo to pro_monthly
UPDATE organization_subscriptions 
SET plan_id = 'pro_monthly', updated_at = NOW()
WHERE plan_id = 'pro_solo';

-- 4. Update subscriptions with unlimited_solo to pro_plus_monthly
UPDATE organization_subscriptions 
SET plan_id = 'pro_plus_monthly', updated_at = NOW()
WHERE plan_id = 'unlimited_solo';

-- 5. Verify the migration
SELECT plan_id, COUNT(*) as count 
FROM organization_subscriptions 
GROUP BY plan_id 
ORDER BY count DESC;

-- 6. Deactivate legacy plans
UPDATE subscription_plans 
SET is_active = false 
WHERE id IN ('light_solo', 'pro_solo', 'unlimited_solo', 'solo_monthly', 'solo_yearly');

-- ============================================================
-- PART 2: Fix credit_balances with correct subscription_credits_total
-- ============================================================

-- Check current credit_balances state
SELECT 
    cb.subscription_credits_total,
    sp.credits_per_month,
    os.plan_id,
    COUNT(*) as count
FROM credit_balances cb
JOIN organization_subscriptions os ON os.organization_id = cb.organization_id
JOIN subscription_plans sp ON sp.id = os.plan_id
GROUP BY cb.subscription_credits_total, sp.credits_per_month, os.plan_id
ORDER BY count DESC;

-- Update credit_balances to use the correct credits_per_month from subscription_plans
UPDATE credit_balances cb
SET 
    subscription_credits_total = sp.credits_per_month,
    is_unlimited = (sp.credits_per_month = -1),
    updated_at = NOW()
FROM organization_subscriptions os
JOIN subscription_plans sp ON sp.id = os.plan_id
WHERE os.organization_id = cb.organization_id
  AND cb.subscription_credits_total != sp.credits_per_month
  AND sp.credits_per_month IS NOT NULL;

-- Verify the fix
SELECT 
    os.plan_id,
    sp.name as plan_name,
    sp.credits_per_month,
    cb.subscription_credits_total,
    cb.is_unlimited,
    COUNT(*) as count
FROM credit_balances cb
JOIN organization_subscriptions os ON os.organization_id = cb.organization_id
JOIN subscription_plans sp ON sp.id = os.plan_id
GROUP BY os.plan_id, sp.name, sp.credits_per_month, cb.subscription_credits_total, cb.is_unlimited
ORDER BY os.plan_id;

