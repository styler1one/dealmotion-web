-- ============================================================
-- MIGRATION: Convert Legacy Plans to New Plans
-- Date: January 2026
-- 
-- Converts old plan IDs to new plan structure:
-- - light_solo -> free
-- - pro_solo -> pro_monthly  
-- - unlimited_solo -> pro_plus_monthly
-- ============================================================

-- Run these one at a time and verify:

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

-- 6. Deactivate legacy plans (they should already be inactive but ensure it)
UPDATE subscription_plans 
SET is_active = false 
WHERE id IN ('light_solo', 'pro_solo', 'unlimited_solo', 'solo_monthly', 'solo_yearly');

