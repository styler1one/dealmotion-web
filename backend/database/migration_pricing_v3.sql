-- ============================================================
-- MIGRATION: Pricing V3
-- Date: December 2025
-- 
-- Changes:
-- 1. Rename Light Solo → Pro Solo
-- 2. Update Unlimited Solo pricing (€29,95 → €49,95, strikethrough €79,95 → €99,95)
-- 3. Add flow_packs table for extra flow purchases
-- ============================================================

-- ============================================================
-- 1. UPDATE SUBSCRIPTION PLANS
-- ============================================================

-- Rename Light Solo to Pro Solo and update description
UPDATE subscription_plans SET
  name = 'Pro Solo',
  description = 'Voor de actieve sales pro'
WHERE id = 'light_solo';

-- Update Unlimited Solo pricing
UPDATE subscription_plans SET
  price_cents = 4995,           -- Was 2995 (€29,95 → €49,95)
  original_price_cents = 9995   -- Was 7995 (€79,95 → €99,95)
WHERE id = 'unlimited_solo';

-- ============================================================
-- 2. CREATE FLOW PACKS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS flow_packs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- Pack details
  flows_purchased INTEGER NOT NULL,
  flows_remaining INTEGER NOT NULL,
  price_cents INTEGER NOT NULL,
  
  -- Stripe reference
  stripe_payment_intent_id TEXT,
  stripe_checkout_session_id TEXT,
  
  -- Status
  status TEXT NOT NULL DEFAULT 'active',  -- 'active', 'depleted', 'expired', 'refunded'
  
  -- Timestamps
  purchased_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ,  -- NULL = never expires
  depleted_at TIMESTAMPTZ,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for flow_packs
CREATE INDEX IF NOT EXISTS idx_flow_packs_org ON flow_packs(organization_id);
CREATE INDEX IF NOT EXISTS idx_flow_packs_status ON flow_packs(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_flow_packs_stripe ON flow_packs(stripe_checkout_session_id);

-- ============================================================
-- 3. FLOW PACK PRODUCT CONFIGURATION
-- ============================================================

-- Create flow_pack_products table for different pack sizes
CREATE TABLE IF NOT EXISTS flow_pack_products (
  id TEXT PRIMARY KEY,  -- 'pack_5', 'pack_10', 'pack_20'
  name TEXT NOT NULL,
  flows INTEGER NOT NULL,
  price_cents INTEGER NOT NULL,
  stripe_price_id TEXT,  -- Set after creating in Stripe
  is_active BOOLEAN DEFAULT true,
  display_order INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default flow pack products
INSERT INTO flow_pack_products (id, name, flows, price_cents, display_order, is_active) VALUES
  ('pack_5', '5 Flow Pack', 5, 995, 1, true)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  flows = EXCLUDED.flows,
  price_cents = EXCLUDED.price_cents;

-- ============================================================
-- 4. HELPER FUNCTIONS
-- ============================================================

-- Function to get available flow pack balance for an organization
CREATE OR REPLACE FUNCTION get_flow_pack_balance(p_organization_id UUID)
RETURNS INTEGER AS $$
DECLARE
  v_balance INTEGER;
BEGIN
  SELECT COALESCE(SUM(flows_remaining), 0) INTO v_balance
  FROM flow_packs
  WHERE organization_id = p_organization_id
    AND status = 'active'
    AND (expires_at IS NULL OR expires_at > NOW());
  
  RETURN v_balance;
END;
$$ LANGUAGE plpgsql;

-- Function to consume flows from packs (FIFO - oldest first)
CREATE OR REPLACE FUNCTION consume_flow_pack(p_organization_id UUID, p_amount INTEGER DEFAULT 1)
RETURNS BOOLEAN AS $$
DECLARE
  v_pack RECORD;
  v_remaining INTEGER;
BEGIN
  v_remaining := p_amount;
  
  -- Get active packs ordered by purchase date (FIFO)
  FOR v_pack IN 
    SELECT id, flows_remaining
    FROM flow_packs
    WHERE organization_id = p_organization_id
      AND status = 'active'
      AND flows_remaining > 0
      AND (expires_at IS NULL OR expires_at > NOW())
    ORDER BY purchased_at ASC
  LOOP
    IF v_remaining <= 0 THEN
      EXIT;
    END IF;
    
    IF v_pack.flows_remaining >= v_remaining THEN
      -- This pack can cover the remaining amount
      UPDATE flow_packs SET
        flows_remaining = flows_remaining - v_remaining,
        updated_at = NOW(),
        status = CASE WHEN flows_remaining - v_remaining = 0 THEN 'depleted' ELSE 'active' END,
        depleted_at = CASE WHEN flows_remaining - v_remaining = 0 THEN NOW() ELSE NULL END
      WHERE id = v_pack.id;
      
      v_remaining := 0;
    ELSE
      -- Use all flows from this pack
      v_remaining := v_remaining - v_pack.flows_remaining;
      
      UPDATE flow_packs SET
        flows_remaining = 0,
        status = 'depleted',
        depleted_at = NOW(),
        updated_at = NOW()
      WHERE id = v_pack.id;
    END IF;
  END LOOP;
  
  RETURN v_remaining = 0;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 5. RLS POLICIES FOR FLOW_PACKS
-- ============================================================

ALTER TABLE flow_packs ENABLE ROW LEVEL SECURITY;

-- Users can view their organization's flow packs
CREATE POLICY "Users can view own org flow packs" ON flow_packs
  FOR SELECT
  USING (
    organization_id IN (
      SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
    )
  );

-- Only service role can insert/update (via webhooks)
CREATE POLICY "Service role can manage flow packs" ON flow_packs
  FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================================
-- 6. VERIFICATION
-- ============================================================

-- Verify the updates
DO $$
BEGIN
  RAISE NOTICE 'Pricing V3 Migration Complete';
  RAISE NOTICE '- Light Solo renamed to Pro Solo';
  RAISE NOTICE '- Unlimited Solo: €49,95 (was €29,95), strikethrough €99,95 (was €79,95)';
  RAISE NOTICE '- Flow packs table created';
  RAISE NOTICE '- Flow pack products configured (5 flows = €9,95)';
END $$;

