-- ============================================================
-- Migration: Pricing V4 Update (January 2026)
-- 
-- Updates subscription_plans with correct Early Bird pricing:
-- - Pro: €99 regular → €75 early bird (AI Notetaker INCLUDED)
-- - Pro+: €149 regular → €125 early bird (AI Notetaker INCLUDED)
-- - Yearly: 15% discount
--
-- IMPORTANT: AI Notetaker is now included in BOTH Pro and Pro+ plans
-- ============================================================

-- Update Pro Monthly
UPDATE subscription_plans 
SET 
    description = 'Stop wasting hours on research & prep',
    price_cents = 7500,           -- €75 early bird
    original_price_cents = 9900,  -- €99 regular
    features = jsonb_set(
        features,
        '{ai_notetaker}',
        'true'::jsonb
    ),
    updated_at = NOW()
WHERE id = 'pro_monthly';

-- Update Pro Yearly
UPDATE subscription_plans 
SET 
    description = 'Stop wasting hours on research & prep',
    price_cents = 76500,           -- €765/year (€63.75/mo with 15% off)
    original_price_cents = 100800, -- €1008/year regular
    features = jsonb_set(
        features,
        '{ai_notetaker}',
        'true'::jsonb
    ),
    updated_at = NOW()
WHERE id = 'pro_yearly';

-- Update Pro+ Monthly
UPDATE subscription_plans 
SET 
    description = 'Never take notes again — AI does it for you',
    price_cents = 12500,          -- €125 early bird
    original_price_cents = 14900, -- €149 regular
    updated_at = NOW()
WHERE id = 'pro_plus_monthly';

-- Update Pro+ Yearly
UPDATE subscription_plans 
SET 
    description = 'Never take notes again — AI does it for you',
    price_cents = 127500,          -- €1275/year (€106.25/mo with 15% off)
    original_price_cents = 152400, -- €1524/year regular
    updated_at = NOW()
WHERE id = 'pro_plus_yearly';

-- Verify the updates
SELECT id, name, description, price_cents, original_price_cents, billing_interval, 
       features->>'ai_notetaker' as ai_notetaker
FROM subscription_plans 
WHERE is_active = true
ORDER BY display_order;

