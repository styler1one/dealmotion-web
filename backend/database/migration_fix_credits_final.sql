-- ============================================================
-- Migration: Final Credits Fix
-- 
-- Ensures subscription_plans.credits_per_month is the single
-- source of truth, and syncs credit_balances.subscription_credits_total
--
-- Run this ONCE after deploying the updated backend code.
-- ============================================================

-- ============================================================
-- STEP 1: Verify subscription_plans has correct credits_per_month
-- ============================================================

-- First, let's see what we have
SELECT id, name, credits_per_month, is_active 
FROM subscription_plans 
ORDER BY display_order;

-- ============================================================
-- STEP 2: Update ALL plans with correct credits_per_month
-- ============================================================

-- Free plan
UPDATE subscription_plans 
SET credits_per_month = 25 
WHERE id = 'free';

-- Pro plans
UPDATE subscription_plans 
SET credits_per_month = 250 
WHERE id IN ('pro_monthly', 'pro_yearly', 'pro_solo');

-- Pro+ plans  
UPDATE subscription_plans 
SET credits_per_month = 600 
WHERE id IN ('pro_plus_monthly', 'pro_plus_yearly');

-- Enterprise (unlimited)
UPDATE subscription_plans 
SET credits_per_month = -1 
WHERE id = 'enterprise';

-- Legacy plans
UPDATE subscription_plans 
SET credits_per_month = 25 
WHERE id = 'light_solo';

UPDATE subscription_plans 
SET credits_per_month = -1 
WHERE id = 'unlimited_solo';

-- Verify
SELECT id, name, credits_per_month, is_active 
FROM subscription_plans 
ORDER BY display_order;

-- ============================================================
-- STEP 3: Sync credit_balances with subscription_plans
-- ============================================================

-- Check current state
SELECT 
    os.plan_id,
    sp.name as plan_name,
    sp.credits_per_month as plan_credits,
    cb.subscription_credits_total as balance_total,
    cb.is_unlimited as balance_unlimited,
    COUNT(*) as count
FROM credit_balances cb
JOIN organization_subscriptions os ON os.organization_id = cb.organization_id
JOIN subscription_plans sp ON sp.id = os.plan_id
GROUP BY os.plan_id, sp.name, sp.credits_per_month, cb.subscription_credits_total, cb.is_unlimited
ORDER BY os.plan_id;

-- Update credit_balances to match subscription_plans
UPDATE credit_balances cb
SET 
    subscription_credits_total = sp.credits_per_month,
    is_unlimited = (sp.credits_per_month = -1),
    updated_at = NOW()
FROM organization_subscriptions os
JOIN subscription_plans sp ON sp.id = os.plan_id
WHERE os.organization_id = cb.organization_id
  AND (
      cb.subscription_credits_total IS NULL 
      OR cb.subscription_credits_total != sp.credits_per_month
      OR cb.is_unlimited != (sp.credits_per_month = -1)
  );

-- ============================================================
-- STEP 4: Final verification
-- ============================================================

SELECT 
    os.plan_id,
    sp.name as plan_name,
    sp.credits_per_month as plan_credits,
    cb.subscription_credits_total as balance_total,
    cb.subscription_credits_used as balance_used,
    cb.is_unlimited as is_unlimited,
    COUNT(*) as count
FROM credit_balances cb
JOIN organization_subscriptions os ON os.organization_id = cb.organization_id
JOIN subscription_plans sp ON sp.id = os.plan_id
GROUP BY os.plan_id, sp.name, sp.credits_per_month, cb.subscription_credits_total, cb.subscription_credits_used, cb.is_unlimited
ORDER BY os.plan_id;

-- Should show:
-- free         | 25 credits
-- pro_monthly  | 250 credits
-- pro_yearly   | 250 credits
-- pro_plus_*   | 600 credits
-- enterprise   | -1 (unlimited)


