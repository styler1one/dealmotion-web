-- ============================================================
-- Credit System & API Usage Tracking Migration
-- 
-- This migration adds:
-- 1. api_usage_logs - Track all external API calls with costs
-- 2. credit_transactions - Log all credit consumption/additions
-- 3. Extends subscription_plans with credit limits
-- 4. Views for usage aggregation
--
-- Credit Model:
-- - 1 Credit = 1 Research Flow (Gemini + Claude + Exa)
-- - 1 Credit = 5 Prospect Discovery searches
-- - 1 Credit = 10 minutes Transcription
-- - Subscription includes X credits/month
-- - Credit packs can be purchased for additional credits
-- ============================================================

-- ============================================================
-- 1. API USAGE LOGS - Track every external API call
-- ============================================================
CREATE TABLE IF NOT EXISTS api_usage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    
    -- API Identification
    api_provider TEXT NOT NULL,           -- 'anthropic', 'gemini', 'exa', 'deepgram', 'voyage', 'pinecone', 'recall', 'brave'
    api_service TEXT,                     -- 'research', 'discovery', 'transcription', 'embedding', etc.
    model TEXT,                           -- 'claude-sonnet-4', 'gemini-2.0-flash', 'nova-2', etc.
    
    -- Token Usage (for LLM APIs)
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    
    -- Request Count (for search APIs like Exa, Brave)
    request_count INTEGER DEFAULT 1,
    
    -- Duration (for audio APIs like Deepgram)
    duration_seconds INTEGER DEFAULT 0,
    
    -- Calculated cost in cents (USD)
    estimated_cost_cents INTEGER DEFAULT 0,
    
    -- Credit consumption (how many credits this consumed)
    credits_consumed DECIMAL(10,4) DEFAULT 0,
    
    -- Context
    request_metadata JSONB DEFAULT '{}',  -- Extra context like prospect_id, company_name, etc.
    
    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_api_usage_org ON api_usage_logs(organization_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_org_created ON api_usage_logs(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_usage_provider ON api_usage_logs(api_provider);
CREATE INDEX IF NOT EXISTS idx_api_usage_user ON api_usage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_created ON api_usage_logs(created_at DESC);

-- ============================================================
-- 2. CREDIT TRANSACTIONS - Track all credit movements
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Transaction type
    transaction_type TEXT NOT NULL,       -- 'subscription_reset', 'pack_purchase', 'consumption', 'admin_grant', 'refund'
    
    -- Amount (positive = added, negative = consumed)
    credits_amount DECIMAL(10,4) NOT NULL,
    
    -- Balance after transaction
    balance_after DECIMAL(10,4) NOT NULL,
    
    -- Reference
    reference_type TEXT,                  -- 'flow_pack', 'subscription', 'api_usage', 'admin'
    reference_id UUID,                    -- ID of related record
    
    -- Description
    description TEXT,
    
    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_tx_org ON credit_transactions(organization_id);
CREATE INDEX IF NOT EXISTS idx_credit_tx_org_created ON credit_transactions(organization_id, created_at DESC);

-- ============================================================
-- 3. CREDIT BALANCES - Current credit balance per org
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_balances (
    organization_id UUID PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Subscription credits (reset monthly)
    subscription_credits_total INTEGER DEFAULT 0,      -- Credits included in plan
    subscription_credits_used DECIMAL(10,4) DEFAULT 0, -- Used this period
    subscription_period_start TIMESTAMPTZ,
    subscription_period_end TIMESTAMPTZ,
    
    -- Pack credits (don't reset, consumed FIFO)
    pack_credits_remaining DECIMAL(10,4) DEFAULT 0,    -- From purchased packs
    
    -- Totals (computed for convenience)
    total_credits_available DECIMAL(10,4) GENERATED ALWAYS AS (
        GREATEST(0, subscription_credits_total - subscription_credits_used) + pack_credits_remaining
    ) STORED,
    
    -- Flags
    is_unlimited BOOLEAN DEFAULT FALSE,                -- Unlimited plan
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 4. UPDATE SUBSCRIPTION_PLANS - Add credit limits
-- ============================================================
-- Add credit_limit column if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'subscription_plans' AND column_name = 'credits_per_month'
    ) THEN
        ALTER TABLE subscription_plans ADD COLUMN credits_per_month INTEGER DEFAULT 0;
    END IF;
END $$;

-- Update existing plans with credit limits
UPDATE subscription_plans SET credits_per_month = 2 WHERE id = 'free';
UPDATE subscription_plans SET credits_per_month = 10 WHERE id = 'light_solo';
UPDATE subscription_plans SET credits_per_month = -1 WHERE id = 'unlimited_solo';  -- -1 = unlimited

-- ============================================================
-- 5. UPDATE FLOW_PACKS - Add credit equivalent
-- ============================================================
-- flow_packs already exist, flows = credits (1:1 mapping)
-- No changes needed, we'll treat flows as credits

-- ============================================================
-- 6. MONTHLY USAGE AGGREGATION VIEW
-- ============================================================
-- Using security_invoker = true to respect RLS policies of the querying user
DROP VIEW IF EXISTS api_usage_monthly;
CREATE VIEW api_usage_monthly
WITH (security_invoker = true)
AS
SELECT 
    organization_id,
    date_trunc('month', created_at) as month,
    api_provider,
    api_service,
    model,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(input_tokens + output_tokens) as total_tokens,
    SUM(request_count) as total_requests,
    SUM(duration_seconds) as total_duration_seconds,
    SUM(estimated_cost_cents) as total_cost_cents,
    SUM(credits_consumed) as total_credits_consumed,
    COUNT(*) as total_api_calls
FROM api_usage_logs
GROUP BY organization_id, date_trunc('month', created_at), api_provider, api_service, model;

GRANT SELECT ON api_usage_monthly TO authenticated;
GRANT SELECT ON api_usage_monthly TO service_role;

-- ============================================================
-- 7. DAILY USAGE AGGREGATION VIEW
-- ============================================================
DROP VIEW IF EXISTS api_usage_daily;
CREATE VIEW api_usage_daily
WITH (security_invoker = true)
AS
SELECT 
    organization_id,
    date_trunc('day', created_at) as day,
    api_provider,
    SUM(input_tokens + output_tokens) as total_tokens,
    SUM(request_count) as total_requests,
    SUM(duration_seconds) as total_duration_seconds,
    SUM(estimated_cost_cents) as total_cost_cents,
    SUM(credits_consumed) as total_credits_consumed,
    COUNT(*) as total_api_calls
FROM api_usage_logs
GROUP BY organization_id, date_trunc('day', created_at), api_provider;

GRANT SELECT ON api_usage_daily TO authenticated;
GRANT SELECT ON api_usage_daily TO service_role;

-- ============================================================
-- 8. ORGANIZATION USAGE SUMMARY VIEW
-- ============================================================
DROP VIEW IF EXISTS organization_usage_summary;
CREATE VIEW organization_usage_summary
WITH (security_invoker = true)
AS
SELECT 
    cb.organization_id,
    cb.subscription_credits_total,
    cb.subscription_credits_used,
    cb.pack_credits_remaining,
    cb.total_credits_available,
    cb.is_unlimited,
    cb.subscription_period_start,
    cb.subscription_period_end,
    COALESCE(usage.total_cost_cents, 0) as current_month_cost_cents,
    COALESCE(usage.total_api_calls, 0) as current_month_api_calls
FROM credit_balances cb
LEFT JOIN (
    SELECT 
        organization_id,
        SUM(estimated_cost_cents) as total_cost_cents,
        COUNT(*) as total_api_calls
    FROM api_usage_logs
    WHERE created_at >= date_trunc('month', NOW())
    GROUP BY organization_id
) usage ON cb.organization_id = usage.organization_id;

GRANT SELECT ON organization_usage_summary TO authenticated;
GRANT SELECT ON organization_usage_summary TO service_role;

-- ============================================================
-- 9. RLS POLICIES
-- ============================================================

-- API Usage Logs - Users can only see their org's usage
ALTER TABLE api_usage_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own org api usage" ON api_usage_logs;
CREATE POLICY "Users can view own org api usage" ON api_usage_logs
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
        )
    );

-- Service role can insert (backend only)
DROP POLICY IF EXISTS "Service can insert api usage" ON api_usage_logs;
CREATE POLICY "Service can insert api usage" ON api_usage_logs
    FOR INSERT
    WITH CHECK (true);

-- Credit Transactions - Users can view their org's transactions
ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own org credit transactions" ON credit_transactions;
CREATE POLICY "Users can view own org credit transactions" ON credit_transactions
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Service can manage credit transactions" ON credit_transactions;
CREATE POLICY "Service can manage credit transactions" ON credit_transactions
    FOR ALL
    WITH CHECK (true);

-- Credit Balances - Users can view their org's balance
ALTER TABLE credit_balances ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own org credit balance" ON credit_balances;
CREATE POLICY "Users can view own org credit balance" ON credit_balances
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Service can manage credit balances" ON credit_balances;
CREATE POLICY "Service can manage credit balances" ON credit_balances
    FOR ALL
    WITH CHECK (true);

-- ============================================================
-- 10. FUNCTION: Initialize credit balance for new orgs
-- ============================================================
CREATE OR REPLACE FUNCTION initialize_credit_balance()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    plan_credits INTEGER;
BEGIN
    -- Get credits from subscription plan
    SELECT COALESCE(credits_per_month, 2) INTO plan_credits
    FROM subscription_plans sp
    JOIN organization_subscriptions os ON os.plan_id = sp.id
    WHERE os.organization_id = NEW.id
    LIMIT 1;
    
    -- Default to free plan credits if no subscription
    IF plan_credits IS NULL THEN
        plan_credits := 2;
    END IF;
    
    -- Insert credit balance record
    INSERT INTO credit_balances (
        organization_id,
        subscription_credits_total,
        subscription_credits_used,
        subscription_period_start,
        subscription_period_end,
        pack_credits_remaining,
        is_unlimited
    ) VALUES (
        NEW.id,
        plan_credits,
        0,
        date_trunc('month', NOW()),
        date_trunc('month', NOW()) + INTERVAL '1 month',
        0,
        plan_credits = -1
    )
    ON CONFLICT (organization_id) DO NOTHING;
    
    RETURN NEW;
END;
$$;

-- Create trigger for new organizations
DROP TRIGGER IF EXISTS trigger_init_credit_balance ON organizations;
CREATE TRIGGER trigger_init_credit_balance
    AFTER INSERT ON organizations
    FOR EACH ROW
    EXECUTE FUNCTION initialize_credit_balance();

-- ============================================================
-- 11. FUNCTION: Reset monthly subscription credits
-- ============================================================
CREATE OR REPLACE FUNCTION reset_monthly_subscription_credits()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Reset subscription credits for all orgs where period has ended
    UPDATE credit_balances cb
    SET 
        subscription_credits_used = 0,
        subscription_period_start = date_trunc('month', NOW()),
        subscription_period_end = date_trunc('month', NOW()) + INTERVAL '1 month',
        subscription_credits_total = COALESCE(
            (SELECT sp.credits_per_month 
             FROM subscription_plans sp
             JOIN organization_subscriptions os ON os.plan_id = sp.id
             WHERE os.organization_id = cb.organization_id
             LIMIT 1),
            2  -- Default to free plan
        ),
        is_unlimited = (
            SELECT sp.credits_per_month = -1
            FROM subscription_plans sp
            JOIN organization_subscriptions os ON os.plan_id = sp.id
            WHERE os.organization_id = cb.organization_id
            LIMIT 1
        ),
        updated_at = NOW()
    WHERE subscription_period_end <= NOW();
    
    -- Log the reset
    INSERT INTO credit_transactions (
        organization_id,
        transaction_type,
        credits_amount,
        balance_after,
        reference_type,
        description
    )
    SELECT 
        organization_id,
        'subscription_reset',
        subscription_credits_total,
        total_credits_available,
        'subscription',
        'Monthly credit reset'
    FROM credit_balances
    WHERE subscription_period_start = date_trunc('month', NOW());
END;
$$;

-- ============================================================
-- 12. Initialize credit balances for existing organizations
-- ============================================================
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
    o.id,
    COALESCE(sp.credits_per_month, 2),
    0,
    date_trunc('month', NOW()),
    date_trunc('month', NOW()) + INTERVAL '1 month',
    COALESCE((
        SELECT SUM(flows_remaining) 
        FROM flow_packs fp 
        WHERE fp.organization_id = o.id AND fp.status = 'active'
    ), 0),
    COALESCE(sp.credits_per_month = -1, FALSE)
FROM organizations o
LEFT JOIN organization_subscriptions os ON os.organization_id = o.id
LEFT JOIN subscription_plans sp ON sp.id = os.plan_id
ON CONFLICT (organization_id) DO UPDATE SET
    subscription_credits_total = EXCLUDED.subscription_credits_total,
    is_unlimited = EXCLUDED.is_unlimited,
    updated_at = NOW();

-- ============================================================
-- DONE
-- ============================================================

