-- Migration: Billing System v2 - Simplified Flow-Based Pricing
-- Created: 3 December 2025
-- SPEC: SPEC-022-Subscription-Billing.md (v2)
-- 
-- Run this migration in Supabase SQL Editor AFTER migration_subscriptions.sql
-- This updates the pricing model to flow-based limits

-- ============================================
-- 1. ADD NEW COLUMNS
-- ============================================

-- Add flow_count to usage_records
ALTER TABLE usage_records 
ADD COLUMN IF NOT EXISTS flow_count INTEGER DEFAULT 0;

-- Add original_price_cents to subscription_plans (for strikethrough pricing)
ALTER TABLE subscription_plans 
ADD COLUMN IF NOT EXISTS original_price_cents INTEGER;

-- ============================================
-- 2. UPDATE SUBSCRIPTION PLANS TO v2
-- ============================================

-- First, deactivate old plans
UPDATE subscription_plans 
SET is_active = false 
WHERE id IN ('solo_monthly', 'solo_yearly', 'teams');

-- Update FREE plan
UPDATE subscription_plans SET
  name = 'Free',
  description = 'Start gratis met 2 flows',
  price_cents = 0,
  original_price_cents = NULL,
  billing_interval = NULL,
  features = '{
    "flow_limit": 2,
    "user_limit": 1,
    "crm_integration": false,
    "team_sharing": false,
    "priority_support": false
  }'::jsonb,
  display_order = 1,
  is_active = true,
  updated_at = NOW()
WHERE id = 'free';

-- Insert new plans (using UPSERT)
INSERT INTO subscription_plans (id, name, description, price_cents, original_price_cents, billing_interval, features, display_order, is_active) VALUES
('light_solo', 'Light Solo', 'Voor de startende sales pro', 995, NULL, 'month', '{
  "flow_limit": 5,
  "user_limit": 1,
  "crm_integration": false,
  "team_sharing": false,
  "priority_support": false
}'::jsonb, 2, true),
('unlimited_solo', 'Unlimited Solo', 'Onbeperkt voor early adopters', 2995, 7995, 'month', '{
  "flow_limit": -1,
  "user_limit": 1,
  "crm_integration": false,
  "team_sharing": false,
  "priority_support": true
}'::jsonb, 3, true),
('enterprise', 'Enterprise', 'Voor teams met CRM integraties', NULL, NULL, NULL, '{
  "flow_limit": -1,
  "user_limit": -1,
  "crm_integration": true,
  "team_sharing": true,
  "priority_support": true,
  "crm_providers": ["dynamics", "salesforce", "hubspot", "pipedrive", "zoho"],
  "sso": true,
  "dedicated_support": true
}'::jsonb, 4, true)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  price_cents = EXCLUDED.price_cents,
  original_price_cents = EXCLUDED.original_price_cents,
  billing_interval = EXCLUDED.billing_interval,
  features = EXCLUDED.features,
  display_order = EXCLUDED.display_order,
  is_active = EXCLUDED.is_active,
  updated_at = NOW();

-- ============================================
-- 3. UPDATE HELPER FUNCTIONS FOR FLOW-BASED LIMITS
-- ============================================

-- Drop existing functions first (required when changing return type)
DROP FUNCTION IF EXISTS check_usage_limit(UUID, TEXT);
DROP FUNCTION IF EXISTS check_flow_limit(UUID);
DROP FUNCTION IF EXISTS increment_flow(UUID);

-- Function to increment flow count
CREATE OR REPLACE FUNCTION increment_flow(p_organization_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
  v_usage_id UUID;
BEGIN
  -- Get or create usage record
  v_usage_id := get_or_create_usage_record(p_organization_id);
  
  -- Increment flow_count and research_count (research starts a flow)
  UPDATE usage_records 
  SET flow_count = flow_count + 1,
      research_count = research_count + 1,
      updated_at = NOW() 
  WHERE id = v_usage_id;
  
  RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function to check flow limit
CREATE OR REPLACE FUNCTION check_flow_limit(p_organization_id UUID)
RETURNS JSONB AS $$
DECLARE
  v_plan_id TEXT;
  v_features JSONB;
  v_limit INTEGER;
  v_current INTEGER;
BEGIN
  -- Get organization's plan
  SELECT plan_id INTO v_plan_id
  FROM organization_subscriptions
  WHERE organization_id = p_organization_id;
  
  -- Default to free if no subscription
  IF v_plan_id IS NULL THEN
    v_plan_id := 'free';
  END IF;
  
  -- Get plan features
  SELECT features INTO v_features
  FROM subscription_plans
  WHERE id = v_plan_id;
  
  -- Get flow limit (-1 means unlimited)
  v_limit := COALESCE((v_features->>'flow_limit')::INTEGER, 2);
  
  -- If unlimited, always allowed
  IF v_limit = -1 THEN
    RETURN jsonb_build_object(
      'allowed', true,
      'current', 0,
      'limit', -1,
      'unlimited', true,
      'remaining', -1
    );
  END IF;
  
  -- Get current flow count
  SELECT COALESCE(flow_count, 0) INTO v_current
  FROM usage_records
  WHERE organization_id = p_organization_id
    AND period_start = date_trunc('month', NOW());
  
  -- Return result
  RETURN jsonb_build_object(
    'allowed', COALESCE(v_current, 0) < v_limit,
    'current', COALESCE(v_current, 0),
    'limit', v_limit,
    'unlimited', false,
    'remaining', GREATEST(0, v_limit - COALESCE(v_current, 0))
  );
END;
$$ LANGUAGE plpgsql;

-- Update the generic check_usage_limit to support 'flow' metric
CREATE OR REPLACE FUNCTION check_usage_limit(
  p_organization_id UUID,
  p_metric TEXT
)
RETURNS JSONB AS $$
DECLARE
  v_plan_id TEXT;
  v_features JSONB;
  v_limit INTEGER;
  v_current INTEGER;
  v_limit_key TEXT;
BEGIN
  -- For 'flow' metric, use dedicated function
  IF p_metric = 'flow' THEN
    RETURN check_flow_limit(p_organization_id);
  END IF;

  -- Get organization's plan
  SELECT plan_id INTO v_plan_id
  FROM organization_subscriptions
  WHERE organization_id = p_organization_id;
  
  -- Default to free if no subscription
  IF v_plan_id IS NULL THEN
    v_plan_id := 'free';
  END IF;
  
  -- Get plan features
  SELECT features INTO v_features
  FROM subscription_plans
  WHERE id = v_plan_id;
  
  -- Build limit key (e.g., 'research' -> 'research_limit')
  v_limit_key := p_metric || '_limit';
  
  -- Get limit (-1 means unlimited)
  v_limit := (v_features->>v_limit_key)::INTEGER;
  
  -- If limit not found or is NULL, check flow_limit for backwards compatibility
  IF v_limit IS NULL THEN
    -- For research/preparation/followup, use flow_limit
    IF p_metric IN ('research', 'preparation', 'followup') THEN
      RETURN check_flow_limit(p_organization_id);
    END IF;
    -- Otherwise unlimited
    RETURN jsonb_build_object(
      'allowed', true,
      'current', 0,
      'limit', -1,
      'unlimited', true
    );
  END IF;
  
  -- If unlimited, always allowed
  IF v_limit = -1 THEN
    RETURN jsonb_build_object(
      'allowed', true,
      'current', 0,
      'limit', -1,
      'unlimited', true
    );
  END IF;
  
  -- Get current usage
  SELECT COALESCE(
    CASE p_metric
      WHEN 'research' THEN research_count
      WHEN 'preparation' THEN preparation_count
      WHEN 'followup' THEN followup_count
      WHEN 'flow' THEN flow_count
      WHEN 'transcription_seconds' THEN transcription_seconds
      WHEN 'kb_document' THEN kb_document_count
    END, 0
  ) INTO v_current
  FROM usage_records
  WHERE organization_id = p_organization_id
    AND period_start = date_trunc('month', NOW());
  
  -- Return result
  RETURN jsonb_build_object(
    'allowed', COALESCE(v_current, 0) < v_limit,
    'current', COALESCE(v_current, 0),
    'limit', v_limit,
    'unlimited', false,
    'remaining', GREATEST(0, v_limit - COALESCE(v_current, 0))
  );
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 4. MIGRATE EXISTING SUBSCRIPTIONS
-- ============================================

-- Users with solo_monthly -> light_solo (temporary, can be upgraded)
-- Note: This is a soft migration. Existing paid users keep their access.
-- UPDATE organization_subscriptions SET plan_id = 'light_solo' WHERE plan_id = 'solo_monthly';
-- UPDATE organization_subscriptions SET plan_id = 'light_solo' WHERE plan_id = 'solo_yearly';

-- For now, just ensure everyone has a valid plan
-- Existing solo users will need manual migration or will be handled via Stripe webhooks

-- ============================================
-- 5. CALCULATE INITIAL FLOW COUNTS FROM EXISTING DATA
-- ============================================

-- Set flow_count = research_count for existing records
-- (Each research represents the start of a flow)
UPDATE usage_records 
SET flow_count = research_count 
WHERE flow_count = 0 AND research_count > 0;

-- ============================================
-- DONE!
-- ============================================
-- After running this migration:
-- 1. Update Stripe with new products/prices
-- 2. Set STRIPE_PRICE_LIGHT_SOLO and STRIPE_PRICE_UNLIMITED_SOLO env vars
-- 3. Create Stripe Donation Payment Link and set STRIPE_DONATION_LINK env var
-- 4. Update subscription_plans.stripe_price_id:
--    UPDATE subscription_plans SET stripe_price_id = 'price_xxx' WHERE id = 'light_solo';
--    UPDATE subscription_plans SET stripe_price_id = 'price_yyy' WHERE id = 'unlimited_solo';


