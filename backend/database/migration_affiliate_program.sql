-- ============================================================
-- Migration: Affiliate Program
-- Version: 1.0
-- Date: 23 December 2025
-- 
-- Creates tables for the DealMotion Affiliate Program:
-- - affiliates: Main affiliate accounts with Stripe Connect
-- - affiliate_clicks: Click tracking for attribution
-- - affiliate_referrals: Users referred by affiliates
-- - affiliate_commissions: Per-payment commission records
-- - affiliate_payouts: Batch payout records
-- - affiliate_events: Audit log
--
-- Also adds columns to existing tables:
-- - users.referred_by_affiliate_id
-- - users.referral_click_id
-- - organization_subscriptions.affiliate_id
-- ============================================================

-- ============================================================
-- 1. AFFILIATES (Main affiliate accounts)
-- ============================================================
CREATE TABLE IF NOT EXISTS affiliates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Unique referral identifier (e.g., "JOHNSMITH" or "AFF_X7K2M9")
    affiliate_code TEXT UNIQUE NOT NULL,
    
    -- Status
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'active', 'paused', 'suspended', 'rejected')),
    status_reason TEXT,
    
    -- Stripe Connect Express account
    stripe_connect_account_id TEXT UNIQUE,
    stripe_connect_status TEXT DEFAULT 'not_connected'
        CHECK (stripe_connect_status IN (
            'not_connected', 
            'pending', 
            'restricted', 
            'active', 
            'disabled'
        )),
    stripe_payouts_enabled BOOLEAN DEFAULT FALSE,
    stripe_charges_enabled BOOLEAN DEFAULT FALSE,
    
    -- Commission rates (stored as decimals, e.g., 0.15 = 15%)
    commission_rate_subscription DECIMAL(5,4) NOT NULL DEFAULT 0.15,
    commission_rate_credits DECIMAL(5,4) NOT NULL DEFAULT 0.10,
    
    -- Payout settings
    minimum_payout_cents INTEGER DEFAULT 5000,  -- €50 minimum
    payout_frequency TEXT DEFAULT 'monthly' 
        CHECK (payout_frequency IN ('weekly', 'biweekly', 'monthly')),
    
    -- Denormalized stats for dashboard performance
    total_clicks INTEGER DEFAULT 0,
    total_signups INTEGER DEFAULT 0,
    total_conversions INTEGER DEFAULT 0,
    total_earned_cents INTEGER DEFAULT 0,
    total_paid_cents INTEGER DEFAULT 0,
    current_balance_cents INTEGER DEFAULT 0,
    
    -- Application & admin notes
    application_notes TEXT,
    internal_notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    activated_at TIMESTAMPTZ,
    
    -- Each user can only be one affiliate
    UNIQUE(user_id)
);

-- Indexes for affiliates
CREATE INDEX IF NOT EXISTS idx_affiliates_code ON affiliates(affiliate_code);
CREATE INDEX IF NOT EXISTS idx_affiliates_user ON affiliates(user_id);
CREATE INDEX IF NOT EXISTS idx_affiliates_org ON affiliates(organization_id);
CREATE INDEX IF NOT EXISTS idx_affiliates_status ON affiliates(status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_affiliates_stripe ON affiliates(stripe_connect_account_id) 
    WHERE stripe_connect_account_id IS NOT NULL;

-- ============================================================
-- 2. AFFILIATE_CLICKS (Click tracking for attribution)
-- ============================================================
CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    affiliate_id UUID NOT NULL REFERENCES affiliates(id) ON DELETE CASCADE,
    
    -- Client-generated tracking ID (stored in cookie)
    click_id TEXT UNIQUE NOT NULL,
    
    -- Where they clicked from and landed
    landing_page TEXT,
    referrer_url TEXT,
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,
    
    -- Device/location info (for fraud detection)
    ip_address INET,
    user_agent TEXT,
    country_code TEXT,
    
    -- Conversion tracking
    converted_to_signup BOOLEAN DEFAULT FALSE,
    signup_user_id UUID REFERENCES auth.users(id),
    converted_at TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 days'
);

-- Indexes for affiliate_clicks
CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_affiliate ON affiliate_clicks(affiliate_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_click_id ON affiliate_clicks(click_id);
-- Note: We use a simple partial index on converted_to_signup instead of expires_at > NOW()
-- because NOW() is not IMMUTABLE. The application handles expiration checks.
CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_pending ON affiliate_clicks(affiliate_id, expires_at) 
    WHERE converted_to_signup = FALSE;
CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_ip ON affiliate_clicks(ip_address, created_at DESC);

-- ============================================================
-- 3. AFFILIATE_REFERRALS (Users referred by affiliates)
-- ============================================================
CREATE TABLE IF NOT EXISTS affiliate_referrals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    affiliate_id UUID NOT NULL REFERENCES affiliates(id) ON DELETE CASCADE,
    click_id UUID REFERENCES affiliate_clicks(id),
    
    -- Referred user (the person who signed up)
    referred_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    referred_organization_id UUID REFERENCES organizations(id),
    referred_email TEXT NOT NULL,
    
    -- Conversion tracking
    signup_at TIMESTAMPTZ DEFAULT NOW(),
    first_payment_at TIMESTAMPTZ,
    converted BOOLEAN DEFAULT FALSE,
    
    -- Lifetime stats for this referral
    lifetime_revenue_cents INTEGER DEFAULT 0,
    lifetime_commission_cents INTEGER DEFAULT 0,
    
    -- Status
    status TEXT DEFAULT 'active' 
        CHECK (status IN ('active', 'churned', 'refunded', 'disputed')),
    churned_at TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Each user can only be referred once
    UNIQUE(referred_user_id)
);

-- Indexes for affiliate_referrals
CREATE INDEX IF NOT EXISTS idx_affiliate_referrals_affiliate ON affiliate_referrals(affiliate_id);
CREATE INDEX IF NOT EXISTS idx_affiliate_referrals_user ON affiliate_referrals(referred_user_id);
CREATE INDEX IF NOT EXISTS idx_affiliate_referrals_converted ON affiliate_referrals(affiliate_id) 
    WHERE converted = TRUE;
CREATE INDEX IF NOT EXISTS idx_affiliate_referrals_org ON affiliate_referrals(referred_organization_id)
    WHERE referred_organization_id IS NOT NULL;

-- ============================================================
-- 4. AFFILIATE_COMMISSIONS (Per-payment commission records)
-- ============================================================
CREATE TABLE IF NOT EXISTS affiliate_commissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    affiliate_id UUID NOT NULL REFERENCES affiliates(id) ON DELETE CASCADE,
    referral_id UUID NOT NULL REFERENCES affiliate_referrals(id) ON DELETE CASCADE,
    
    -- Source payment (Stripe references)
    stripe_invoice_id TEXT,
    stripe_charge_id TEXT,
    stripe_payment_intent_id TEXT,
    
    -- Payment details
    payment_type TEXT NOT NULL 
        CHECK (payment_type IN ('subscription', 'credit_pack', 'one_time')),
    payment_amount_cents INTEGER NOT NULL,
    currency TEXT DEFAULT 'eur',
    
    -- Commission calculation
    commission_rate DECIMAL(5,4) NOT NULL,
    commission_amount_cents INTEGER NOT NULL,
    
    -- Status flow: pending → approved → processing → paid
    -- Or: pending → reversed (if refund)
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending',      -- Waiting for refund window (14 days)
            'approved',     -- Ready for payout
            'processing',   -- Payout in progress
            'paid',         -- Successfully paid
            'reversed',     -- Refund/chargeback occurred
            'disputed'      -- Under dispute
        )),
    
    -- Timing
    payment_at TIMESTAMPTZ NOT NULL,
    approved_at TIMESTAMPTZ,  -- After 14-day refund window
    
    -- Payout tracking
    payout_id UUID,  -- Will reference affiliate_payouts after that table is created
    paid_at TIMESTAMPTZ,
    
    -- Reversal tracking
    reversed_at TIMESTAMPTZ,
    reversal_reason TEXT,
    original_stripe_refund_id TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for affiliate_commissions
CREATE INDEX IF NOT EXISTS idx_affiliate_commissions_affiliate ON affiliate_commissions(affiliate_id);
CREATE INDEX IF NOT EXISTS idx_affiliate_commissions_referral ON affiliate_commissions(referral_id);
CREATE INDEX IF NOT EXISTS idx_affiliate_commissions_status ON affiliate_commissions(status);
CREATE INDEX IF NOT EXISTS idx_affiliate_commissions_pending ON affiliate_commissions(affiliate_id) 
    WHERE status IN ('pending', 'approved');
CREATE INDEX IF NOT EXISTS idx_affiliate_commissions_stripe_invoice ON affiliate_commissions(stripe_invoice_id)
    WHERE stripe_invoice_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_affiliate_commissions_payout ON affiliate_commissions(payout_id)
    WHERE payout_id IS NOT NULL;

-- ============================================================
-- 5. AFFILIATE_PAYOUTS (Batch payout records)
-- ============================================================
CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    affiliate_id UUID NOT NULL REFERENCES affiliates(id) ON DELETE CASCADE,
    
    -- Payout details
    amount_cents INTEGER NOT NULL,
    currency TEXT DEFAULT 'eur',
    commission_count INTEGER NOT NULL,  -- Number of commissions in this payout
    
    -- Stripe Connect transfer/payout
    stripe_transfer_id TEXT UNIQUE,
    stripe_payout_id TEXT,
    
    -- Status
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending',      -- Scheduled for payout
            'processing',   -- Sent to Stripe
            'succeeded',    -- Transfer completed
            'failed',       -- Transfer failed
            'canceled'      -- Manually canceled
        )),
    
    -- Timing
    scheduled_for TIMESTAMPTZ,
    initiated_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    
    -- Error handling
    failure_reason TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add foreign key from commissions to payouts (now that payouts table exists)
ALTER TABLE affiliate_commissions 
    ADD CONSTRAINT fk_affiliate_commissions_payout 
    FOREIGN KEY (payout_id) REFERENCES affiliate_payouts(id);

-- Indexes for affiliate_payouts
CREATE INDEX IF NOT EXISTS idx_affiliate_payouts_affiliate ON affiliate_payouts(affiliate_id);
CREATE INDEX IF NOT EXISTS idx_affiliate_payouts_status ON affiliate_payouts(status);
CREATE INDEX IF NOT EXISTS idx_affiliate_payouts_scheduled ON affiliate_payouts(scheduled_for) 
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_affiliate_payouts_stripe ON affiliate_payouts(stripe_transfer_id)
    WHERE stripe_transfer_id IS NOT NULL;

-- ============================================================
-- 6. AFFILIATE_EVENTS (Audit log)
-- ============================================================
CREATE TABLE IF NOT EXISTS affiliate_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    affiliate_id UUID REFERENCES affiliates(id) ON DELETE SET NULL,
    
    -- Event type (e.g., 'signup', 'activated', 'payout_requested', 'commission_earned')
    event_type TEXT NOT NULL,
    event_data JSONB DEFAULT '{}',
    
    -- Who triggered this event
    actor_type TEXT CHECK (actor_type IN ('system', 'affiliate', 'admin', 'stripe', 'user')),
    actor_id UUID,
    
    -- Additional context
    ip_address INET,
    user_agent TEXT,
    
    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for affiliate_events
CREATE INDEX IF NOT EXISTS idx_affiliate_events_affiliate ON affiliate_events(affiliate_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_affiliate_events_type ON affiliate_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_affiliate_events_created ON affiliate_events(created_at DESC);

-- ============================================================
-- 7. MODIFICATIONS TO EXISTING TABLES
-- ============================================================

-- Add affiliate tracking to users table
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS referred_by_affiliate_id UUID REFERENCES affiliates(id);

ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS referral_click_id TEXT;

CREATE INDEX IF NOT EXISTS idx_users_affiliate ON users(referred_by_affiliate_id) 
    WHERE referred_by_affiliate_id IS NOT NULL;

-- Add affiliate tracking to organization_subscriptions
ALTER TABLE organization_subscriptions 
    ADD COLUMN IF NOT EXISTS affiliate_id UUID REFERENCES affiliates(id);

CREATE INDEX IF NOT EXISTS idx_org_subs_affiliate ON organization_subscriptions(affiliate_id) 
    WHERE affiliate_id IS NOT NULL;

-- ============================================================
-- 8. TRIGGER FUNCTIONS
-- ============================================================

-- Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_affiliate_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
DROP TRIGGER IF EXISTS trigger_affiliates_updated_at ON affiliates;
CREATE TRIGGER trigger_affiliates_updated_at
    BEFORE UPDATE ON affiliates
    FOR EACH ROW EXECUTE FUNCTION update_affiliate_updated_at();

DROP TRIGGER IF EXISTS trigger_affiliate_referrals_updated_at ON affiliate_referrals;
CREATE TRIGGER trigger_affiliate_referrals_updated_at
    BEFORE UPDATE ON affiliate_referrals
    FOR EACH ROW EXECUTE FUNCTION update_affiliate_updated_at();

DROP TRIGGER IF EXISTS trigger_affiliate_commissions_updated_at ON affiliate_commissions;
CREATE TRIGGER trigger_affiliate_commissions_updated_at
    BEFORE UPDATE ON affiliate_commissions
    FOR EACH ROW EXECUTE FUNCTION update_affiliate_updated_at();

DROP TRIGGER IF EXISTS trigger_affiliate_payouts_updated_at ON affiliate_payouts;
CREATE TRIGGER trigger_affiliate_payouts_updated_at
    BEFORE UPDATE ON affiliate_payouts
    FOR EACH ROW EXECUTE FUNCTION update_affiliate_updated_at();

-- ============================================================
-- 9. HELPER FUNCTIONS
-- ============================================================

-- Generate unique affiliate code
CREATE OR REPLACE FUNCTION generate_affiliate_code(p_user_id UUID)
RETURNS TEXT AS $$
DECLARE
    v_code TEXT;
    v_exists BOOLEAN;
    v_attempts INTEGER := 0;
BEGIN
    -- Try to generate a unique code
    LOOP
        -- Generate a random alphanumeric code
        v_code := 'AFF_' || UPPER(SUBSTRING(MD5(RANDOM()::TEXT || p_user_id::TEXT) FROM 1 FOR 6));
        
        -- Check if it exists
        SELECT EXISTS(SELECT 1 FROM affiliates WHERE affiliate_code = v_code) INTO v_exists;
        
        -- Exit if unique or too many attempts
        v_attempts := v_attempts + 1;
        EXIT WHEN NOT v_exists OR v_attempts > 10;
    END LOOP;
    
    IF v_exists THEN
        -- Fallback: use user_id suffix
        v_code := 'AFF_' || UPPER(SUBSTRING(p_user_id::TEXT FROM 1 FOR 8));
    END IF;
    
    RETURN v_code;
END;
$$ LANGUAGE plpgsql;

-- Check if user can be an affiliate (anti-fraud)
CREATE OR REPLACE FUNCTION can_user_become_affiliate(p_user_id UUID)
RETURNS TABLE(allowed BOOLEAN, reason TEXT) AS $$
DECLARE
    v_user_created_at TIMESTAMPTZ;
    v_has_paid BOOLEAN;
BEGIN
    -- Get user creation date
    SELECT created_at INTO v_user_created_at
    FROM auth.users
    WHERE id = p_user_id;
    
    IF v_user_created_at IS NULL THEN
        RETURN QUERY SELECT false, 'User not found';
        RETURN;
    END IF;
    
    -- Check if already an affiliate
    IF EXISTS(SELECT 1 FROM affiliates WHERE user_id = p_user_id) THEN
        RETURN QUERY SELECT false, 'User is already an affiliate';
        RETURN;
    END IF;
    
    -- Check if user was referred (can't be affiliate if referred)
    IF EXISTS(SELECT 1 FROM affiliate_referrals WHERE referred_user_id = p_user_id) THEN
        RETURN QUERY SELECT false, 'Referred users cannot become affiliates';
        RETURN;
    END IF;
    
    -- All checks passed
    RETURN QUERY SELECT true, NULL::TEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Get affiliate stats (for dashboard)
CREATE OR REPLACE FUNCTION get_affiliate_stats(p_affiliate_id UUID)
RETURNS TABLE(
    total_clicks BIGINT,
    total_signups BIGINT,
    total_conversions BIGINT,
    conversion_rate DECIMAL,
    total_earned_cents BIGINT,
    total_paid_cents BIGINT,
    current_balance_cents BIGINT,
    pending_commissions_cents BIGINT,
    this_month_earned_cents BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.total_clicks::BIGINT,
        a.total_signups::BIGINT,
        a.total_conversions::BIGINT,
        CASE WHEN a.total_signups > 0 
            THEN ROUND((a.total_conversions::DECIMAL / a.total_signups) * 100, 2)
            ELSE 0 
        END as conversion_rate,
        a.total_earned_cents::BIGINT,
        a.total_paid_cents::BIGINT,
        a.current_balance_cents::BIGINT,
        COALESCE((
            SELECT SUM(commission_amount_cents)::BIGINT 
            FROM affiliate_commissions 
            WHERE affiliate_id = p_affiliate_id AND status = 'pending'
        ), 0) as pending_commissions_cents,
        COALESCE((
            SELECT SUM(commission_amount_cents)::BIGINT 
            FROM affiliate_commissions 
            WHERE affiliate_id = p_affiliate_id 
            AND created_at >= DATE_TRUNC('month', NOW())
        ), 0) as this_month_earned_cents
    FROM affiliates a
    WHERE a.id = p_affiliate_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 10. ROW LEVEL SECURITY (RLS)
-- ============================================================

-- Enable RLS on all affiliate tables
ALTER TABLE affiliates ENABLE ROW LEVEL SECURITY;
ALTER TABLE affiliate_clicks ENABLE ROW LEVEL SECURITY;
ALTER TABLE affiliate_referrals ENABLE ROW LEVEL SECURITY;
ALTER TABLE affiliate_commissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE affiliate_payouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE affiliate_events ENABLE ROW LEVEL SECURITY;

-- Affiliates: users can only see their own affiliate record
CREATE POLICY affiliates_select_own ON affiliates
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY affiliates_update_own ON affiliates
    FOR UPDATE USING (user_id = auth.uid());

-- Affiliate clicks: affiliates can see their own clicks
CREATE POLICY affiliate_clicks_select_own ON affiliate_clicks
    FOR SELECT USING (
        affiliate_id IN (SELECT id FROM affiliates WHERE user_id = auth.uid())
    );

-- Anyone can insert clicks (for tracking)
CREATE POLICY affiliate_clicks_insert_any ON affiliate_clicks
    FOR INSERT WITH CHECK (true);

-- Affiliate referrals: affiliates can see their referrals
CREATE POLICY affiliate_referrals_select_own ON affiliate_referrals
    FOR SELECT USING (
        affiliate_id IN (SELECT id FROM affiliates WHERE user_id = auth.uid())
    );

-- Affiliate commissions: affiliates can see their commissions
CREATE POLICY affiliate_commissions_select_own ON affiliate_commissions
    FOR SELECT USING (
        affiliate_id IN (SELECT id FROM affiliates WHERE user_id = auth.uid())
    );

-- Affiliate payouts: affiliates can see their payouts
CREATE POLICY affiliate_payouts_select_own ON affiliate_payouts
    FOR SELECT USING (
        affiliate_id IN (SELECT id FROM affiliates WHERE user_id = auth.uid())
    );

-- Affiliate events: affiliates can see their events
CREATE POLICY affiliate_events_select_own ON affiliate_events
    FOR SELECT USING (
        affiliate_id IN (SELECT id FROM affiliates WHERE user_id = auth.uid())
    );

-- Service role bypass (for backend operations)
CREATE POLICY affiliates_service_all ON affiliates
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY affiliate_clicks_service_all ON affiliate_clicks
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY affiliate_referrals_service_all ON affiliate_referrals
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY affiliate_commissions_service_all ON affiliate_commissions
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY affiliate_payouts_service_all ON affiliate_payouts
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY affiliate_events_service_all ON affiliate_events
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================
-- 11. COMMENTS
-- ============================================================

COMMENT ON TABLE affiliates IS 'Affiliate accounts with Stripe Connect for automated payouts';
COMMENT ON TABLE affiliate_clicks IS 'Click tracking for affiliate attribution (30-day cookie window)';
COMMENT ON TABLE affiliate_referrals IS 'Users referred by affiliates - tracks lifetime value';
COMMENT ON TABLE affiliate_commissions IS 'Per-payment commission records with 14-day refund window';
COMMENT ON TABLE affiliate_payouts IS 'Batch payouts via Stripe Connect transfers';
COMMENT ON TABLE affiliate_events IS 'Audit log for all affiliate-related events';

COMMENT ON COLUMN affiliates.affiliate_code IS 'Unique referral code used in URLs (e.g., ?ref=AFF_X7K2M9)';
COMMENT ON COLUMN affiliates.commission_rate_subscription IS 'Commission rate for subscriptions (0.15 = 15%)';
COMMENT ON COLUMN affiliates.commission_rate_credits IS 'Commission rate for credit packs (0.10 = 10%)';
COMMENT ON COLUMN affiliates.current_balance_cents IS 'Approved but unpaid commissions in cents';
COMMENT ON COLUMN affiliate_commissions.status IS 'pending=waiting refund window, approved=ready for payout, paid=transferred';
COMMENT ON COLUMN affiliate_clicks.expires_at IS 'Attribution window expires after 30 days';

-- ============================================================
-- VERIFICATION
-- ============================================================
-- Run these queries after migration to verify:
-- 
-- SELECT COUNT(*) FROM affiliates;
-- SELECT COUNT(*) FROM affiliate_clicks;
-- SELECT COUNT(*) FROM affiliate_referrals;
-- SELECT COUNT(*) FROM affiliate_commissions;
-- SELECT COUNT(*) FROM affiliate_payouts;
-- SELECT COUNT(*) FROM affiliate_events;
--
-- -- Check columns were added
-- SELECT column_name FROM information_schema.columns 
-- WHERE table_name = 'users' AND column_name LIKE '%affiliate%';
--
-- SELECT column_name FROM information_schema.columns 
-- WHERE table_name = 'organization_subscriptions' AND column_name = 'affiliate_id';
-- ============================================================

