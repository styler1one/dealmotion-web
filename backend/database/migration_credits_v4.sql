-- ============================================================
-- Migration: Credits for V4 Pricing Plans
-- 
-- Updates subscription_plans with correct credits_per_month values
-- for the new credit-based pricing system.
--
-- Plans:
-- - Free: 25 credits/month
-- - Pro: 250 credits/month
-- - Pro+: 600 credits/month
-- - Enterprise: Unlimited (-1)
-- ============================================================

-- Add credits_per_month column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'subscription_plans' AND column_name = 'credits_per_month'
    ) THEN
        ALTER TABLE subscription_plans ADD COLUMN credits_per_month INTEGER DEFAULT 0;
    END IF;
END $$;

-- Update Free plan
UPDATE subscription_plans SET credits_per_month = 25 WHERE id = 'free';

-- Update Pro plans (250 credits/month)
UPDATE subscription_plans SET credits_per_month = 250 WHERE id = 'pro_monthly';
UPDATE subscription_plans SET credits_per_month = 250 WHERE id = 'pro_yearly';

-- Update Pro+ plans (600 credits/month)
UPDATE subscription_plans SET credits_per_month = 600 WHERE id = 'pro_plus_monthly';
UPDATE subscription_plans SET credits_per_month = 600 WHERE id = 'pro_plus_yearly';

-- Legacy plans (keep for existing subscribers)
UPDATE subscription_plans SET credits_per_month = 25 WHERE id = 'light_solo' AND credits_per_month IS NULL;
UPDATE subscription_plans SET credits_per_month = -1 WHERE id = 'unlimited_solo' AND credits_per_month IS NULL;

-- Verify the updates
SELECT id, name, credits_per_month, price_cents, billing_interval 
FROM subscription_plans 
ORDER BY display_order;

-- ============================================================
-- Also update Early Bird pricing (€24 discount)
-- Pro: €99 -> €75
-- Pro+: €149 -> €125
-- ============================================================

UPDATE subscription_plans SET 
    price_cents = 7500,           -- €75 (was €99)
    original_price_cents = 9900   -- Show original €99
WHERE id = 'pro_monthly';

UPDATE subscription_plans SET 
    price_cents = 90000,          -- €75/month * 12 = €900/year
    original_price_cents = 118800 -- €99 * 12 = €1188/year
WHERE id = 'pro_yearly';

UPDATE subscription_plans SET 
    price_cents = 12500,          -- €125 (was €149)
    original_price_cents = 14900  -- Show original €149
WHERE id = 'pro_plus_monthly';

UPDATE subscription_plans SET 
    price_cents = 150000,         -- €125/month * 12 = €1500/year
    original_price_cents = 178800 -- €149 * 12 = €1788/year
WHERE id = 'pro_plus_yearly';

-- ============================================================
-- Update existing credit_balances for organizations
-- This ensures existing users get the correct credit allocation
-- ============================================================

UPDATE credit_balances cb
SET 
    subscription_credits_total = COALESCE(
        (SELECT sp.credits_per_month 
         FROM subscription_plans sp
         JOIN organization_subscriptions os ON os.plan_id = sp.id
         WHERE os.organization_id = cb.organization_id
         LIMIT 1),
        25  -- Default to free plan
    ),
    is_unlimited = COALESCE(
        (SELECT sp.credits_per_month = -1
         FROM subscription_plans sp
         JOIN organization_subscriptions os ON os.plan_id = sp.id
         WHERE os.organization_id = cb.organization_id
         LIMIT 1),
        FALSE
    ),
    updated_at = NOW();

-- Log migration
DO $$
BEGIN
    RAISE NOTICE 'Credits V4 migration complete';
END $$;

