-- ============================================================
-- GDPR Compliance Migration
-- Version: 1.0
-- Date: 23 December 2025
-- 
-- Implements:
-- - Account deletion tracking (Art. 17 Right to Erasure)
-- - Data export tracking (Art. 15/20 Right of Access/Portability)
-- - Deletion audit trail
-- - Billing data anonymization support
-- ============================================================

-- ============================================================
-- 1. ADD DELETION TRACKING TO USERS TABLE
-- ============================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS 
    deletion_status TEXT DEFAULT 'active' 
    CHECK (deletion_status IN ('active', 'pending_deletion', 'deleted', 'anonymized'));

ALTER TABLE users ADD COLUMN IF NOT EXISTS 
    deletion_requested_at TIMESTAMPTZ;

ALTER TABLE users ADD COLUMN IF NOT EXISTS 
    deletion_scheduled_at TIMESTAMPTZ;

ALTER TABLE users ADD COLUMN IF NOT EXISTS 
    deletion_completed_at TIMESTAMPTZ;

ALTER TABLE users ADD COLUMN IF NOT EXISTS 
    deletion_reason TEXT;

-- Index for finding pending deletions
CREATE INDEX IF NOT EXISTS idx_users_deletion_status 
    ON users(deletion_status) 
    WHERE deletion_status != 'active';

CREATE INDEX IF NOT EXISTS idx_users_deletion_scheduled 
    ON users(deletion_scheduled_at) 
    WHERE deletion_status = 'pending_deletion';

-- ============================================================
-- 2. GDPR DELETION REQUESTS (Audit Trail)
-- ============================================================

CREATE TABLE IF NOT EXISTS gdpr_deletion_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,  -- Not FK because user will be deleted
    user_email TEXT NOT NULL,  -- Store for audit (hashed after completion)
    organization_id UUID,  -- Store for reference
    
    -- Request info
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scheduled_for TIMESTAMPTZ NOT NULL,  -- When deletion will occur (48h grace period)
    reason TEXT,
    
    -- Status tracking
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'processing', 'completed', 'cancelled', 'failed')),
    
    -- Processing info
    processing_started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancellation_reason TEXT,
    
    -- Deletion details (what was deleted)
    deletion_summary JSONB,  -- {tables_cleaned: [...], storage_deleted: [...], etc.}
    error_message TEXT,
    
    -- Billing retention
    billing_data_anonymized BOOLEAN DEFAULT false,
    billing_retention_hash TEXT,  -- Hash to link anonymized billing records
    
    -- Audit
    ip_address TEXT,
    user_agent TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gdpr_deletion_user ON gdpr_deletion_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_gdpr_deletion_status ON gdpr_deletion_requests(status);
CREATE INDEX IF NOT EXISTS idx_gdpr_deletion_scheduled ON gdpr_deletion_requests(scheduled_for) 
    WHERE status = 'pending';

-- ============================================================
-- 3. GDPR DATA EXPORTS (Export Tracking)
-- ============================================================

CREATE TABLE IF NOT EXISTS gdpr_data_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Request info
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Status
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'processing', 'ready', 'downloaded', 'expired', 'failed')),
    
    -- Processing
    processing_started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Export file
    storage_path TEXT,  -- Path in storage bucket
    file_size_bytes INTEGER,
    download_url TEXT,  -- Signed URL (temporary)
    download_expires_at TIMESTAMPTZ,
    
    -- Download tracking
    downloaded_at TIMESTAMPTZ,
    download_count INTEGER DEFAULT 0,
    
    -- Auto-expire
    expires_at TIMESTAMPTZ,  -- When export file will be deleted (7 days)
    
    -- Error handling
    error_message TEXT,
    
    -- Audit
    ip_address TEXT,
    user_agent TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gdpr_export_user ON gdpr_data_exports(user_id);
CREATE INDEX IF NOT EXISTS idx_gdpr_export_status ON gdpr_data_exports(status);
CREATE INDEX IF NOT EXISTS idx_gdpr_export_expires ON gdpr_data_exports(expires_at) 
    WHERE status = 'ready';

-- ============================================================
-- 4. BILLING ARCHIVE (For anonymized billing data retention)
-- ============================================================

CREATE TABLE IF NOT EXISTS billing_archive (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Anonymized reference (hash of original user_id)
    user_hash TEXT NOT NULL,
    organization_hash TEXT,
    
    -- Original payment data (from payment_history)
    original_payment_id UUID,
    stripe_invoice_id TEXT,
    stripe_payment_intent_id TEXT,
    stripe_charge_id TEXT,
    
    -- Payment details (kept for tax/accounting)
    amount_cents INTEGER NOT NULL,
    currency TEXT DEFAULT 'eur',
    status TEXT NOT NULL,
    
    -- Invoice info
    invoice_pdf_url TEXT,
    invoice_number TEXT,
    
    -- Dates
    original_paid_at TIMESTAMPTZ,
    original_created_at TIMESTAMPTZ,
    
    -- Archive metadata
    archived_at TIMESTAMPTZ DEFAULT NOW(),
    archive_reason TEXT DEFAULT 'user_deletion',
    gdpr_request_id UUID REFERENCES gdpr_deletion_requests(id),
    
    -- Retention period (7 years for tax)
    retention_expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 years'
);

CREATE INDEX IF NOT EXISTS idx_billing_archive_hash ON billing_archive(user_hash);
CREATE INDEX IF NOT EXISTS idx_billing_archive_retention ON billing_archive(retention_expires_at);

-- ============================================================
-- 5. STORAGE BUCKET FOR EXPORTS
-- ============================================================

INSERT INTO storage.buckets (id, name, public) 
VALUES ('gdpr-exports', 'gdpr-exports', false)
ON CONFLICT (id) DO NOTHING;

-- Storage policies for GDPR exports
CREATE POLICY "Users can download own exports"
    ON storage.objects FOR SELECT
    TO authenticated
    USING (
        bucket_id = 'gdpr-exports' 
        AND (storage.foldername(name))[1] = (SELECT auth.uid())::text
    );

-- Only backend can upload exports (service role)
CREATE POLICY "Service role can manage exports"
    ON storage.objects FOR ALL
    TO service_role
    USING (bucket_id = 'gdpr-exports');

-- ============================================================
-- 6. RLS POLICIES
-- ============================================================

ALTER TABLE gdpr_deletion_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE gdpr_data_exports ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_archive ENABLE ROW LEVEL SECURITY;

-- Users can view their own deletion requests
CREATE POLICY "Users can view own deletion requests"
    ON gdpr_deletion_requests FOR SELECT
    TO authenticated
    USING (user_id = (SELECT auth.uid()));

-- Users can cancel their own pending deletion
CREATE POLICY "Users can update own pending deletion"
    ON gdpr_deletion_requests FOR UPDATE
    TO authenticated
    USING (user_id = (SELECT auth.uid()) AND status = 'pending');

-- Users can view their own exports
CREATE POLICY "Users can view own exports"
    ON gdpr_data_exports FOR SELECT
    TO authenticated
    USING (user_id = (SELECT auth.uid()));

-- Billing archive is admin-only (no user access after anonymization)
CREATE POLICY "Admin can view billing archive"
    ON billing_archive FOR SELECT
    TO authenticated
    USING (public.is_admin());

-- Service role can manage all GDPR tables
CREATE POLICY "Service role manages deletion requests"
    ON gdpr_deletion_requests FOR ALL
    TO service_role
    USING (true);

CREATE POLICY "Service role manages exports"
    ON gdpr_data_exports FOR ALL
    TO service_role
    USING (true);

CREATE POLICY "Service role manages billing archive"
    ON billing_archive FOR ALL
    TO service_role
    USING (true);

-- ============================================================
-- 7. UPDATED_AT TRIGGERS
-- ============================================================

CREATE TRIGGER update_gdpr_deletion_requests_updated_at
    BEFORE UPDATE ON gdpr_deletion_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_gdpr_data_exports_updated_at
    BEFORE UPDATE ON gdpr_data_exports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 8. HELPER FUNCTIONS
-- ============================================================

-- Function to generate user hash for billing anonymization
CREATE OR REPLACE FUNCTION generate_user_hash(p_user_id UUID)
RETURNS TEXT AS $$
BEGIN
    -- Use SHA-256 hash with a salt
    RETURN encode(
        digest(
            p_user_id::text || '-dealmotion-billing-archive-' || extract(epoch from now())::text,
            'sha256'
        ),
        'hex'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Function to check if user can be deleted (no active subscriptions)
CREATE OR REPLACE FUNCTION can_user_be_deleted(p_user_id UUID)
RETURNS TABLE(can_delete BOOLEAN, reason TEXT) AS $$
DECLARE
    v_active_subscription BOOLEAN;
    v_pending_deletion BOOLEAN;
BEGIN
    -- Check for active paid subscriptions
    SELECT EXISTS (
        SELECT 1 
        FROM public.organization_subscriptions os
        JOIN public.organization_members om ON os.organization_id = om.organization_id
        WHERE om.user_id = p_user_id
        AND os.status = 'active'
        AND os.plan_id != 'free'
        AND os.cancel_at_period_end = false
    ) INTO v_active_subscription;
    
    IF v_active_subscription THEN
        RETURN QUERY SELECT false, 'Active subscription must be cancelled first';
        RETURN;
    END IF;
    
    -- Check for pending deletion
    SELECT EXISTS (
        SELECT 1 
        FROM public.gdpr_deletion_requests
        WHERE user_id = p_user_id
        AND status IN ('pending', 'processing')
    ) INTO v_pending_deletion;
    
    IF v_pending_deletion THEN
        RETURN QUERY SELECT false, 'Deletion already in progress';
        RETURN;
    END IF;
    
    RETURN QUERY SELECT true, NULL::TEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- ============================================================
-- END OF MIGRATION
-- ============================================================

