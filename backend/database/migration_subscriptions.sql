-- Migration: Subscription & Billing System
-- Created: 29 November 2025
-- SPEC: SPEC-022-Subscription-Billing.md
-- 
-- Run this migration in Supabase SQL Editor
-- This creates the subscription, usage tracking, and payment tables

-- ============================================
-- 1. SUBSCRIPTION PLANS (Static Configuration)
-- ============================================

CREATE TABLE IF NOT EXISTS subscription_plans (
  id TEXT PRIMARY KEY,  -- 'free', 'solo_monthly', 'solo_yearly', 'teams'
  name TEXT NOT NULL,
  description TEXT,
  price_cents INTEGER,  -- Price in cents (0, 2900, 1900, NULL for custom)
  billing_interval TEXT,  -- 'month', 'year', NULL for free/custom
  stripe_price_id TEXT,  -- Stripe Price ID (set after creating in Stripe)
  features JSONB NOT NULL DEFAULT '{}',  -- Feature flags & limits
  is_active BOOLEAN DEFAULT true,
  display_order INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default plans
INSERT INTO subscription_plans (id, name, description, price_cents, billing_interval, features, display_order) VALUES
('free', 'Free', 'Perfect om te starten', 0, NULL, '{
  "research_limit": 3,
  "preparation_limit": 3,
  "followup_limit": 1,
  "transcription_seconds_limit": 0,
  "kb_document_limit": 0,
  "contact_analysis": "basic",
  "pdf_watermark": true,
  "user_limit": 1,
  "crm_integration": false,
  "team_sharing": false,
  "priority_support": false
}', 1),
('solo_monthly', 'Solo', 'Voor de individuele sales professional', 2900, 'month', '{
  "research_limit": -1,
  "preparation_limit": -1,
  "followup_limit": -1,
  "transcription_seconds_limit": 36000,
  "kb_document_limit": 50,
  "contact_analysis": "full",
  "pdf_watermark": false,
  "user_limit": 1,
  "crm_integration": false,
  "team_sharing": false,
  "priority_support": false
}', 2),
('solo_yearly', 'Solo (Jaarlijks)', 'Bespaar 34% met jaarlijkse betaling', 22800, 'year', '{
  "research_limit": -1,
  "preparation_limit": -1,
  "followup_limit": -1,
  "transcription_seconds_limit": 36000,
  "kb_document_limit": 50,
  "contact_analysis": "full",
  "pdf_watermark": false,
  "user_limit": 1,
  "crm_integration": false,
  "team_sharing": false,
  "priority_support": false
}', 3),
('teams', 'Teams', 'Voor sales teams', NULL, 'month', '{
  "research_limit": -1,
  "preparation_limit": -1,
  "followup_limit": -1,
  "transcription_seconds_limit": -1,
  "kb_document_limit": -1,
  "contact_analysis": "full",
  "pdf_watermark": false,
  "user_limit": -1,
  "crm_integration": true,
  "team_sharing": true,
  "priority_support": true,
  "sso": true,
  "analytics_dashboard": true,
  "dedicated_support": true,
  "onboarding_call": true
}', 4)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  price_cents = EXCLUDED.price_cents,
  billing_interval = EXCLUDED.billing_interval,
  features = EXCLUDED.features,
  display_order = EXCLUDED.display_order,
  updated_at = NOW();

-- ============================================
-- 2. ORGANIZATION SUBSCRIPTIONS
-- ============================================

CREATE TABLE IF NOT EXISTS organization_subscriptions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  plan_id TEXT NOT NULL REFERENCES subscription_plans(id) DEFAULT 'free',
  status TEXT NOT NULL DEFAULT 'active',  -- 'trialing', 'active', 'past_due', 'canceled', 'suspended', 'unpaid'
  
  -- Stripe references
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT UNIQUE,
  
  -- Billing cycle
  current_period_start TIMESTAMPTZ,
  current_period_end TIMESTAMPTZ,
  cancel_at_period_end BOOLEAN DEFAULT false,
  canceled_at TIMESTAMPTZ,
  
  -- Trial
  trial_start TIMESTAMPTZ,
  trial_end TIMESTAMPTZ,
  
  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(organization_id)
);

-- Index for Stripe lookups
CREATE INDEX IF NOT EXISTS idx_org_subs_stripe_customer ON organization_subscriptions(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_org_subs_stripe_subscription ON organization_subscriptions(stripe_subscription_id);
CREATE INDEX IF NOT EXISTS idx_org_subs_status ON organization_subscriptions(status);

-- ============================================
-- 3. USAGE RECORDS (Per Billing Period)
-- ============================================

CREATE TABLE IF NOT EXISTS usage_records (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  period_start TIMESTAMPTZ NOT NULL,
  period_end TIMESTAMPTZ NOT NULL,
  
  -- Usage counters
  research_count INTEGER DEFAULT 0,
  preparation_count INTEGER DEFAULT 0,
  followup_count INTEGER DEFAULT 0,
  transcription_seconds INTEGER DEFAULT 0,
  kb_document_count INTEGER DEFAULT 0,
  
  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(organization_id, period_start)
);

-- Index for period lookups
CREATE INDEX IF NOT EXISTS idx_usage_org_period ON usage_records(organization_id, period_start, period_end);

-- ============================================
-- 4. PAYMENT HISTORY
-- ============================================

CREATE TABLE IF NOT EXISTS payment_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- Stripe references
  stripe_invoice_id TEXT UNIQUE,
  stripe_payment_intent_id TEXT,
  stripe_charge_id TEXT,
  
  -- Payment details
  amount_cents INTEGER NOT NULL,
  currency TEXT DEFAULT 'eur',
  status TEXT NOT NULL,  -- 'paid', 'failed', 'refunded', 'pending'
  
  -- Invoice
  invoice_pdf_url TEXT,
  invoice_number TEXT,
  
  -- Timestamps
  paid_at TIMESTAMPTZ,
  failed_at TIMESTAMPTZ,
  refunded_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for organization payment history
CREATE INDEX IF NOT EXISTS idx_payment_history_org ON payment_history(organization_id, created_at DESC);

-- ============================================
-- 5. STRIPE WEBHOOK EVENTS (Idempotency)
-- ============================================

CREATE TABLE IF NOT EXISTS stripe_webhook_events (
  id TEXT PRIMARY KEY,  -- Stripe event ID (evt_...)
  event_type TEXT NOT NULL,
  processed_at TIMESTAMPTZ DEFAULT NOW(),
  payload JSONB
);

-- Cleanup old events (keep 30 days)
-- Run this periodically: DELETE FROM stripe_webhook_events WHERE processed_at < NOW() - INTERVAL '30 days';

-- ============================================
-- 6. HELPER FUNCTIONS
-- ============================================

-- Function to get or create subscription for organization
CREATE OR REPLACE FUNCTION get_or_create_subscription(p_organization_id UUID)
RETURNS UUID AS $$
DECLARE
  v_subscription_id UUID;
BEGIN
  -- Try to find existing subscription
  SELECT id INTO v_subscription_id
  FROM organization_subscriptions
  WHERE organization_id = p_organization_id;
  
  -- If not found, create FREE subscription
  IF v_subscription_id IS NULL THEN
    INSERT INTO organization_subscriptions (organization_id, plan_id, status)
    VALUES (p_organization_id, 'free', 'active')
    RETURNING id INTO v_subscription_id;
  END IF;
  
  RETURN v_subscription_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get current usage record (or create if not exists)
CREATE OR REPLACE FUNCTION get_or_create_usage_record(p_organization_id UUID)
RETURNS UUID AS $$
DECLARE
  v_usage_id UUID;
  v_period_start TIMESTAMPTZ;
  v_period_end TIMESTAMPTZ;
BEGIN
  -- Calculate current period (start of current month)
  v_period_start := date_trunc('month', NOW());
  v_period_end := v_period_start + INTERVAL '1 month';
  
  -- Try to find existing usage record for this period
  SELECT id INTO v_usage_id
  FROM usage_records
  WHERE organization_id = p_organization_id
    AND period_start = v_period_start;
  
  -- If not found, create new usage record
  IF v_usage_id IS NULL THEN
    INSERT INTO usage_records (organization_id, period_start, period_end)
    VALUES (p_organization_id, v_period_start, v_period_end)
    RETURNING id INTO v_usage_id;
  END IF;
  
  RETURN v_usage_id;
END;
$$ LANGUAGE plpgsql;

-- Function to increment usage counter
CREATE OR REPLACE FUNCTION increment_usage(
  p_organization_id UUID,
  p_metric TEXT,
  p_amount INTEGER DEFAULT 1
)
RETURNS BOOLEAN AS $$
DECLARE
  v_usage_id UUID;
BEGIN
  -- Get or create usage record
  v_usage_id := get_or_create_usage_record(p_organization_id);
  
  -- Increment the appropriate counter
  EXECUTE format(
    'UPDATE usage_records SET %I = %I + $1, updated_at = NOW() WHERE id = $2',
    p_metric, p_metric
  ) USING p_amount, v_usage_id;
  
  RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function to check if action is within limits
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
      WHEN 'transcription_seconds' THEN transcription_seconds
      WHEN 'kb_document' THEN kb_document_count
    END, 0
  ) INTO v_current
  FROM usage_records
  WHERE organization_id = p_organization_id
    AND period_start = date_trunc('month', NOW());
  
  -- Return result
  RETURN jsonb_build_object(
    'allowed', v_current < v_limit,
    'current', COALESCE(v_current, 0),
    'limit', v_limit,
    'unlimited', false,
    'remaining', GREATEST(0, v_limit - COALESCE(v_current, 0))
  );
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 7. ROW LEVEL SECURITY (RLS)
-- ============================================

-- Enable RLS on all tables
ALTER TABLE subscription_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE stripe_webhook_events ENABLE ROW LEVEL SECURITY;

-- Subscription plans: readable by all authenticated users
CREATE POLICY "Plans are viewable by authenticated users"
  ON subscription_plans FOR SELECT
  TO authenticated
  USING (is_active = true);

-- Organization subscriptions: only viewable by org members
CREATE POLICY "Subscriptions viewable by org members"
  ON organization_subscriptions FOR SELECT
  TO authenticated
  USING (
    organization_id IN (
      SELECT organization_id FROM organization_members
      WHERE user_id = auth.uid()
    )
  );

-- Usage records: only viewable by org members
CREATE POLICY "Usage viewable by org members"
  ON usage_records FOR SELECT
  TO authenticated
  USING (
    organization_id IN (
      SELECT organization_id FROM organization_members
      WHERE user_id = auth.uid()
    )
  );

-- Payment history: only viewable by org admins
CREATE POLICY "Payments viewable by org admins"
  ON payment_history FOR SELECT
  TO authenticated
  USING (
    organization_id IN (
      SELECT organization_id FROM organization_members
      WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
    )
  );

-- Webhook events: service role only (no user access)
CREATE POLICY "Webhook events service role only"
  ON stripe_webhook_events FOR ALL
  TO service_role
  USING (true);

-- ============================================
-- 8. TRIGGERS
-- ============================================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to subscription tables
DROP TRIGGER IF EXISTS update_subscription_plans_updated_at ON subscription_plans;
CREATE TRIGGER update_subscription_plans_updated_at
  BEFORE UPDATE ON subscription_plans
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_organization_subscriptions_updated_at ON organization_subscriptions;
CREATE TRIGGER update_organization_subscriptions_updated_at
  BEFORE UPDATE ON organization_subscriptions
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_usage_records_updated_at ON usage_records;
CREATE TRIGGER update_usage_records_updated_at
  BEFORE UPDATE ON usage_records
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- 9. CREATE DEFAULT SUBSCRIPTIONS FOR EXISTING ORGS
-- ============================================

-- Insert FREE subscription for all existing organizations that don't have one
INSERT INTO organization_subscriptions (organization_id, plan_id, status)
SELECT id, 'free', 'active'
FROM organizations
WHERE id NOT IN (SELECT organization_id FROM organization_subscriptions)
ON CONFLICT (organization_id) DO NOTHING;

-- ============================================
-- DONE! 
-- ============================================
-- After running this migration:
-- 1. Create Stripe products/prices in Stripe Dashboard
-- 2. Update subscription_plans.stripe_price_id with the Stripe Price IDs
-- 3. Set up Stripe webhook endpoint

