-- ============================================================
-- MIGRATION: Pricing V4 - High-End Pricing Model
-- Date: December 2025
-- 
-- New Pricing Structure:
-- 1. Free - Test & experience (no limits change)
-- 2. Pro - Everything EXCEPT AI Notetaker (€79,95/month, launch €49,95)
-- 3. Pro+ - Everything INCLUDING AI Notetaker (€99,95/month, launch €69,95)
-- 4. Enterprise - Teams with CRM integrations
--
-- Yearly pricing: 15% discount
-- - Pro yearly: €815/year (launch €509)
-- - Pro+ yearly: €1019/year (launch €713)
-- ============================================================

-- ============================================================
-- 1. DEACTIVATE OLD PLANS
-- ============================================================

-- Deactivate old plans (keep for existing subscriptions)
UPDATE subscription_plans SET is_active = false 
WHERE id IN ('light_solo', 'pro_solo', 'unlimited_solo', 'solo_monthly', 'solo_yearly');

-- ============================================================
-- 2. INSERT NEW PLANS
-- ============================================================

-- Free Plan (update existing)
UPDATE subscription_plans SET
  name = 'Free',
  description = 'Test & experience DealMotion',
  price_cents = 0,
  original_price_cents = NULL,
  billing_interval = NULL,
  features = '{
    "flow_limit": 2,
    "user_limit": 1,
    "ai_notetaker": false,
    "knowledge_base": true,
    "transcription": true,
    "contacts_analysis": true,
    "pdf_export": true,
    "crm_integration": false,
    "team_sharing": false,
    "priority_support": false
  }'::jsonb,
  display_order = 1,
  is_active = true
WHERE id = 'free';

-- Pro Monthly
INSERT INTO subscription_plans (id, name, description, price_cents, original_price_cents, billing_interval, features, display_order, is_active) VALUES
('pro_monthly', 'Pro', 'Everything for the modern sales professional', 4995, 7995, 'month', '{
  "flow_limit": -1,
  "user_limit": 1,
  "ai_notetaker": false,
  "knowledge_base": true,
  "transcription": true,
  "contacts_analysis": true,
  "pdf_export": true,
  "crm_integration": false,
  "team_sharing": false,
  "priority_support": true
}'::jsonb, 2, true)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  price_cents = EXCLUDED.price_cents,
  original_price_cents = EXCLUDED.original_price_cents,
  billing_interval = EXCLUDED.billing_interval,
  features = EXCLUDED.features,
  display_order = EXCLUDED.display_order,
  is_active = EXCLUDED.is_active;

-- Pro Yearly (15% discount: €79.95 * 12 * 0.85 = €815.49 ≈ €815)
INSERT INTO subscription_plans (id, name, description, price_cents, original_price_cents, billing_interval, features, display_order, is_active) VALUES
('pro_yearly', 'Pro', 'Everything for the modern sales professional', 50900, 81500, 'year', '{
  "flow_limit": -1,
  "user_limit": 1,
  "ai_notetaker": false,
  "knowledge_base": true,
  "transcription": true,
  "contacts_analysis": true,
  "pdf_export": true,
  "crm_integration": false,
  "team_sharing": false,
  "priority_support": true
}'::jsonb, 3, true)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  price_cents = EXCLUDED.price_cents,
  original_price_cents = EXCLUDED.original_price_cents,
  billing_interval = EXCLUDED.billing_interval,
  features = EXCLUDED.features,
  display_order = EXCLUDED.display_order,
  is_active = EXCLUDED.is_active;

-- Pro+ Monthly (includes AI Notetaker)
INSERT INTO subscription_plans (id, name, description, price_cents, original_price_cents, billing_interval, features, display_order, is_active) VALUES
('pro_plus_monthly', 'Pro+', 'Complete package with AI Notetaker', 6995, 9995, 'month', '{
  "flow_limit": -1,
  "user_limit": 1,
  "ai_notetaker": true,
  "knowledge_base": true,
  "transcription": true,
  "contacts_analysis": true,
  "pdf_export": true,
  "crm_integration": false,
  "team_sharing": false,
  "priority_support": true
}'::jsonb, 4, true)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  price_cents = EXCLUDED.price_cents,
  original_price_cents = EXCLUDED.original_price_cents,
  billing_interval = EXCLUDED.billing_interval,
  features = EXCLUDED.features,
  display_order = EXCLUDED.display_order,
  is_active = EXCLUDED.is_active;

-- Pro+ Yearly (15% discount: €99.95 * 12 * 0.85 = €1019.49 ≈ €1019)
INSERT INTO subscription_plans (id, name, description, price_cents, original_price_cents, billing_interval, features, display_order, is_active) VALUES
('pro_plus_yearly', 'Pro+', 'Complete package with AI Notetaker', 71300, 101900, 'year', '{
  "flow_limit": -1,
  "user_limit": 1,
  "ai_notetaker": true,
  "knowledge_base": true,
  "transcription": true,
  "contacts_analysis": true,
  "pdf_export": true,
  "crm_integration": false,
  "team_sharing": false,
  "priority_support": true
}'::jsonb, 5, true)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  price_cents = EXCLUDED.price_cents,
  original_price_cents = EXCLUDED.original_price_cents,
  billing_interval = EXCLUDED.billing_interval,
  features = EXCLUDED.features,
  display_order = EXCLUDED.display_order,
  is_active = EXCLUDED.is_active;

-- Enterprise (update existing)
UPDATE subscription_plans SET
  name = 'Enterprise',
  description = 'For teams with CRM integrations',
  price_cents = NULL,
  original_price_cents = NULL,
  billing_interval = NULL,
  features = '{
    "flow_limit": -1,
    "user_limit": -1,
    "ai_notetaker": true,
    "knowledge_base": true,
    "transcription": true,
    "contacts_analysis": true,
    "pdf_export": true,
    "crm_integration": true,
    "crm_providers": ["dynamics", "salesforce", "hubspot", "pipedrive", "zoho"],
    "team_sharing": true,
    "priority_support": true,
    "sso": true,
    "dedicated_support": true
  }'::jsonb,
  display_order = 6,
  is_active = true
WHERE id = 'enterprise';

-- ============================================================
-- 3. VERIFICATION
-- ============================================================

DO $$
DECLARE
  v_plan RECORD;
BEGIN
  RAISE NOTICE '=== Pricing V4 Migration Complete ===';
  RAISE NOTICE '';
  RAISE NOTICE 'New Pricing Structure:';
  
  FOR v_plan IN 
    SELECT id, name, price_cents, original_price_cents, billing_interval 
    FROM subscription_plans 
    WHERE is_active = true 
    ORDER BY display_order
  LOOP
    IF v_plan.price_cents IS NOT NULL THEN
      RAISE NOTICE '- % (%): €%.2f (launch) / €%.2f (regular) per %',
        v_plan.name,
        v_plan.id,
        v_plan.price_cents::numeric / 100,
        COALESCE(v_plan.original_price_cents, v_plan.price_cents)::numeric / 100,
        COALESCE(v_plan.billing_interval, 'n/a');
    ELSE
      RAISE NOTICE '- % (%): Contact Sales', v_plan.name, v_plan.id;
    END IF;
  END LOOP;
  
  RAISE NOTICE '';
  RAISE NOTICE 'Key Differentiator: AI Notetaker';
  RAISE NOTICE '- Pro: Everything EXCEPT AI Notetaker';
  RAISE NOTICE '- Pro+: Everything INCLUDING AI Notetaker';
END $$;
