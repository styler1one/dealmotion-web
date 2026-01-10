-- ============================================================
-- Migration: Fix Credit Balance Initialization
-- Date: 2026-01-10
-- 
-- Problem: New users get only 2 credits instead of 25
-- Cause: The trigger_init_credit_balance was not deployed, 
--        and handle_new_user doesn't initialize credit_balances
-- 
-- Solution: 
-- 1. Create/update the credit initialization trigger on organizations
-- 2. Update handle_new_user to also initialize credit_balances
-- 3. Fix existing users who have wrong credit amounts
-- ============================================================

-- ============================================================
-- STEP 1: Create the credit balance initialization function
-- NOTE: Function must be created BEFORE the trigger that uses it
-- ============================================================

CREATE OR REPLACE FUNCTION public.initialize_credit_balance_for_subscription()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    plan_credits INTEGER;
BEGIN
    -- Get credits from the subscription plan
    SELECT COALESCE(credits_per_month, 25) INTO plan_credits
    FROM subscription_plans
    WHERE id = NEW.plan_id;
    
    -- Default to free plan credits (25)
    IF plan_credits IS NULL THEN
        plan_credits := 25;
    END IF;
    
    -- Insert or update credit balance record
    INSERT INTO credit_balances (
        organization_id,
        subscription_credits_total,
        subscription_credits_used,
        subscription_period_start,
        subscription_period_end,
        pack_credits_remaining,
        is_unlimited
    ) VALUES (
        NEW.organization_id,
        plan_credits,
        0,
        date_trunc('month', NOW()),
        date_trunc('month', NOW()) + INTERVAL '1 month',
        0,
        plan_credits = -1
    )
    ON CONFLICT (organization_id) DO UPDATE SET
        subscription_credits_total = EXCLUDED.subscription_credits_total,
        is_unlimited = EXCLUDED.is_unlimited,
        updated_at = NOW()
    WHERE credit_balances.subscription_credits_total != EXCLUDED.subscription_credits_total;
    
    RETURN NEW;
END;
$$;

-- ============================================================
-- STEP 2: Create trigger on organization_subscriptions
-- This fires when a new subscription is created (after handle_new_user)
-- ============================================================

DROP TRIGGER IF EXISTS trigger_init_credit_balance ON organizations;
DROP TRIGGER IF EXISTS trigger_init_credit_balance_on_subscription ON organization_subscriptions;

CREATE TRIGGER trigger_init_credit_balance_on_subscription
    AFTER INSERT ON organization_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION public.initialize_credit_balance_for_subscription();

-- ============================================================
-- STEP 3: Verify subscription_plans has correct free plan credits
-- ============================================================

-- Ensure free plan has 25 credits
UPDATE subscription_plans 
SET credits_per_month = 25 
WHERE id = 'free' 
AND (credits_per_month IS NULL OR credits_per_month != 25);

-- Verify
SELECT id, name, credits_per_month FROM subscription_plans WHERE id = 'free';

-- ============================================================
-- STEP 4: Fix existing organizations without credit_balances
-- ============================================================

-- Insert credit_balances for organizations that don't have one
INSERT INTO credit_balances (
    organization_id,
    subscription_credits_total,
    subscription_credits_used,
    subscription_period_start,
    subscription_period_end,
    pack_credits_remaining,
    is_unlimited
)
SELECT 
    os.organization_id,
    COALESCE(sp.credits_per_month, 25),
    0,
    date_trunc('month', NOW()),
    date_trunc('month', NOW()) + INTERVAL '1 month',
    0,
    COALESCE(sp.credits_per_month = -1, FALSE)
FROM organization_subscriptions os
JOIN subscription_plans sp ON sp.id = os.plan_id
WHERE NOT EXISTS (
    SELECT 1 FROM credit_balances cb 
    WHERE cb.organization_id = os.organization_id
);

-- ============================================================
-- STEP 5: Fix existing credit_balances with wrong amounts
-- ============================================================

-- Update credit_balances to match subscription_plans
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

-- ============================================================
-- VERIFICATION
-- ============================================================

-- Show all free plan users and their credits
SELECT 
    u.email,
    os.plan_id,
    sp.credits_per_month as expected_credits,
    cb.subscription_credits_total as actual_credits,
    cb.subscription_credits_used,
    (cb.subscription_credits_total - cb.subscription_credits_used) as available
FROM organization_subscriptions os
JOIN organizations o ON o.id = os.organization_id
JOIN organization_members om ON om.organization_id = o.id
JOIN auth.users u ON u.id = om.user_id
JOIN subscription_plans sp ON sp.id = os.plan_id
LEFT JOIN credit_balances cb ON cb.organization_id = os.organization_id
WHERE os.plan_id = 'free'
ORDER BY u.email;

