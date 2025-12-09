-- ============================================================
-- Admin Panel Migration
-- Version: 1.0
-- Date: 5 December 2025
-- SPEC: SPEC-037-Admin-Panel
-- 
-- This migration adds:
-- - admin_users table (admin roles)
-- - admin_audit_log table (action logging)
-- - admin_alerts table (proactive alerts)
-- - admin_notes table (internal notes)
-- - Helper functions for dashboard metrics
-- 
-- RUN THIS MIGRATION VIA SUPABASE SQL EDITOR
-- ============================================================

-- ============================================================
-- 1. ADMIN_USERS (Admin role management)
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Role: super_admin > admin > support > viewer
    role TEXT NOT NULL DEFAULT 'support' 
        CHECK (role IN ('super_admin', 'admin', 'support', 'viewer')),
    
    is_active BOOLEAN DEFAULT true,
    last_admin_login_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,  -- No FK to avoid circular dependency for first admin
    
    UNIQUE(user_id)
);

-- Indexes for admin_users
CREATE INDEX IF NOT EXISTS idx_admin_users_user_id ON admin_users(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_admin_users_active ON admin_users(is_active) WHERE is_active = true;

-- ============================================================
-- 2. ADMIN_AUDIT_LOG (Action logging for compliance)
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_user_id UUID NOT NULL REFERENCES admin_users(id),
    
    -- Action details
    action TEXT NOT NULL,           -- 'user.view', 'user.reset_flows', 'alert.acknowledge'
    target_type TEXT,               -- 'user', 'organization', 'alert'
    target_id UUID,
    target_identifier TEXT,         -- email or name for easy searching
    
    -- Context
    details JSONB,                  -- { "flows_reset": 5, "reason": "support request" }
    ip_address INET,
    user_agent TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_audit_log_admin ON admin_audit_log(admin_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_target ON admin_audit_log(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON admin_audit_log(action, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON admin_audit_log(created_at DESC);

-- ============================================================
-- 3. ADMIN_ALERTS (Proactive system alerts)
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Type & Severity
    alert_type TEXT NOT NULL,       -- 'error_spike', 'churn_risk', 'payment_failed', 'usage_limit'
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    
    -- Target
    target_type TEXT,               -- 'user', 'organization', 'system'
    target_id UUID,
    target_name TEXT,               -- Denormalized for display
    
    -- Content
    title TEXT NOT NULL,
    description TEXT,
    context JSONB,                  -- Additional data for investigation
    
    -- Status
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'acknowledged', 'resolved')),
    acknowledged_by UUID REFERENCES admin_users(id),
    acknowledged_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES admin_users(id),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_alerts_status ON admin_alerts(status, severity DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON admin_alerts(alert_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_target ON admin_alerts(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON admin_alerts(created_at DESC);

-- ============================================================
-- 4. ADMIN_NOTES (Internal notes on users/organizations)
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Target
    target_type TEXT NOT NULL CHECK (target_type IN ('user', 'organization')),
    target_id UUID NOT NULL,
    target_identifier TEXT,          -- email/org name for easy reference
    
    -- Content
    content TEXT NOT NULL,
    is_pinned BOOLEAN DEFAULT false,
    
    -- Author
    admin_user_id UUID NOT NULL REFERENCES admin_users(id),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_admin_notes_target ON admin_notes(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_admin_notes_admin ON admin_notes(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_notes_pinned ON admin_notes(target_type, target_id, is_pinned DESC, created_at DESC);

-- ============================================================
-- 5. RLS POLICIES
-- ============================================================

-- Enable RLS on all admin tables
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_notes ENABLE ROW LEVEL SECURITY;

-- Helper function to check if user is admin (cached for performance)
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_is_admin BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM public.admin_users
        WHERE user_id = (SELECT auth.uid())
        AND is_active = true
    ) INTO v_is_admin;
    
    RETURN COALESCE(v_is_admin, false);
END;
$$;

-- Helper function to check if user is super_admin
CREATE OR REPLACE FUNCTION public.is_super_admin()
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_is_super BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM public.admin_users
        WHERE user_id = (SELECT auth.uid())
        AND role = 'super_admin'
        AND is_active = true
    ) INTO v_is_super;
    
    RETURN COALESCE(v_is_super, false);
END;
$$;

-- Helper function to get admin role
CREATE OR REPLACE FUNCTION public.get_admin_role()
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_role TEXT;
BEGIN
    SELECT role INTO v_role
    FROM public.admin_users
    WHERE user_id = (SELECT auth.uid())
    AND is_active = true;
    
    RETURN v_role;
END;
$$;

-- ============================================================
-- RLS Policies for admin_users
-- ============================================================

-- Select: Any active admin can view admin users
CREATE POLICY admin_users_select ON admin_users
    FOR SELECT TO authenticated
    USING (public.is_admin());

-- Insert: Only super_admin can add new admins
CREATE POLICY admin_users_insert ON admin_users
    FOR INSERT TO authenticated
    WITH CHECK (public.is_super_admin());

-- Update: Only super_admin can modify admin users
CREATE POLICY admin_users_update ON admin_users
    FOR UPDATE TO authenticated
    USING (public.is_super_admin())
    WITH CHECK (public.is_super_admin());

-- Delete: Only super_admin can remove admins
CREATE POLICY admin_users_delete ON admin_users
    FOR DELETE TO authenticated
    USING (public.is_super_admin());

-- ============================================================
-- RLS Policies for admin_audit_log
-- ============================================================

-- Select: Any active admin can view audit log
CREATE POLICY audit_log_select ON admin_audit_log
    FOR SELECT TO authenticated
    USING (public.is_admin());

-- Insert: Only service role can insert (via backend)
-- No policy needed - service role bypasses RLS

-- ============================================================
-- RLS Policies for admin_alerts
-- ============================================================

-- Select: Any active admin can view alerts
CREATE POLICY alerts_select ON admin_alerts
    FOR SELECT TO authenticated
    USING (public.is_admin());

-- Update: Support and above can acknowledge/resolve alerts
CREATE POLICY alerts_update ON admin_alerts
    FOR UPDATE TO authenticated
    USING (
        public.get_admin_role() IN ('super_admin', 'admin', 'support')
    )
    WITH CHECK (
        public.get_admin_role() IN ('super_admin', 'admin', 'support')
    );

-- Insert: Only service role can insert (system-generated)
-- No policy needed - service role bypasses RLS

-- ============================================================
-- RLS Policies for admin_notes
-- ============================================================

-- Select: Any active admin can view notes
CREATE POLICY admin_notes_select ON admin_notes
    FOR SELECT TO authenticated
    USING (public.is_admin());

-- Insert: Support and above can create notes
CREATE POLICY admin_notes_insert ON admin_notes
    FOR INSERT TO authenticated
    WITH CHECK (
        public.get_admin_role() IN ('super_admin', 'admin', 'support')
    );

-- Update: Only the author can update their own notes
CREATE POLICY admin_notes_update ON admin_notes
    FOR UPDATE TO authenticated
    USING (
        admin_user_id = (
            SELECT id FROM public.admin_users 
            WHERE user_id = (SELECT auth.uid())
        )
    )
    WITH CHECK (
        admin_user_id = (
            SELECT id FROM public.admin_users 
            WHERE user_id = (SELECT auth.uid())
        )
    );

-- Delete: Only the author can delete their own notes
CREATE POLICY admin_notes_delete ON admin_notes
    FOR DELETE TO authenticated
    USING (
        admin_user_id = (
            SELECT id FROM public.admin_users 
            WHERE user_id = (SELECT auth.uid())
        )
    );

-- ============================================================
-- 6. HELPER FUNCTIONS FOR DASHBOARD METRICS
-- ============================================================

-- Calculate MRR (Monthly Recurring Revenue)
CREATE OR REPLACE FUNCTION public.calculate_mrr()
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_result JSON;
BEGIN
    SELECT json_build_object(
        'mrr_cents', COALESCE((
            SELECT SUM(sp.price_cents)
            FROM public.organization_subscriptions os
            JOIN public.subscription_plans sp ON os.plan_id = sp.id
            WHERE os.status = 'active'
            AND sp.price_cents > 0
        ), 0),
        'paid_users', COALESCE((
            SELECT COUNT(*)
            FROM public.organization_subscriptions os
            JOIN public.subscription_plans sp ON os.plan_id = sp.id
            WHERE os.status = 'active'
            AND sp.price_cents > 0
        ), 0)
    ) INTO v_result;
    
    RETURN v_result;
END;
$$;

-- Get job success rates for last 24 hours
CREATE OR REPLACE FUNCTION public.get_job_stats_24h(p_table_name TEXT)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_result JSON;
BEGIN
    -- Validate table name to prevent SQL injection
    IF p_table_name NOT IN ('research_briefs', 'meeting_preps', 'followups', 'knowledge_base_files') THEN
        RETURN json_build_object(
            'total', 0,
            'completed', 0,
            'failed', 0,
            'success_rate', 0
        );
    END IF;
    
    EXECUTE format('
        SELECT json_build_object(
            ''total'', COALESCE(COUNT(*), 0),
            ''completed'', COALESCE(COUNT(*) FILTER (WHERE status = ''completed''), 0),
            ''failed'', COALESCE(COUNT(*) FILTER (WHERE status = ''failed''), 0),
            ''success_rate'', COALESCE(
                ROUND(
                    COUNT(*) FILTER (WHERE status = ''completed'')::numeric / 
                    NULLIF(COUNT(*), 0) * 100, 1
                ), 0
            )
        )
        FROM public.%I
        WHERE created_at > NOW() - INTERVAL ''24 hours''
    ', p_table_name) INTO v_result;
    
    RETURN COALESCE(v_result, json_build_object('total', 0, 'completed', 0, 'failed', 0, 'success_rate', 0));
END;
$$;

-- Get dashboard metrics summary
CREATE OR REPLACE FUNCTION public.get_admin_dashboard_metrics()
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_result JSON;
    v_total_users INTEGER;
    v_users_growth_week INTEGER;
    v_active_users_7d INTEGER;
    v_mrr JSON;
    v_active_alerts INTEGER;
BEGIN
    -- Total users
    SELECT COUNT(*) INTO v_total_users
    FROM public.users;
    
    -- Users growth this week
    SELECT COUNT(*) INTO v_users_growth_week
    FROM public.users
    WHERE created_at > NOW() - INTERVAL '7 days';
    
    -- Active users in last 7 days (users with activity)
    SELECT COUNT(DISTINCT organization_id) INTO v_active_users_7d
    FROM public.prospect_activities
    WHERE created_at > NOW() - INTERVAL '7 days';
    
    -- MRR
    SELECT public.calculate_mrr() INTO v_mrr;
    
    -- Active alerts
    SELECT COUNT(*) INTO v_active_alerts
    FROM public.admin_alerts
    WHERE status = 'active';
    
    SELECT json_build_object(
        'total_users', COALESCE(v_total_users, 0),
        'users_growth_week', COALESCE(v_users_growth_week, 0),
        'active_users_7d', COALESCE(v_active_users_7d, 0),
        'mrr_cents', COALESCE((v_mrr->>'mrr_cents')::integer, 0),
        'paid_users', COALESCE((v_mrr->>'paid_users')::integer, 0),
        'active_alerts', COALESCE(v_active_alerts, 0)
    ) INTO v_result;
    
    RETURN v_result;
END;
$$;

-- Get usage trends for last 7 days
CREATE OR REPLACE FUNCTION public.get_admin_usage_trends(p_days INTEGER DEFAULT 7)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_result JSON;
BEGIN
    SELECT json_agg(day_data ORDER BY day_date) INTO v_result
    FROM (
        SELECT 
            day_date::date,
            json_build_object(
                'date', day_date::date,
                'researches', COALESCE((
                    SELECT COUNT(*) 
                    FROM public.research_briefs 
                    WHERE created_at::date = day_date::date
                ), 0),
                'preps', COALESCE((
                    SELECT COUNT(*) 
                    FROM public.meeting_preps 
                    WHERE created_at::date = day_date::date
                ), 0),
                'followups', COALESCE((
                    SELECT COUNT(*) 
                    FROM public.followups 
                    WHERE created_at::date = day_date::date
                ), 0),
                'new_users', COALESCE((
                    SELECT COUNT(*) 
                    FROM public.users 
                    WHERE created_at::date = day_date::date
                ), 0)
            ) as day_data
        FROM generate_series(
            NOW() - (p_days || ' days')::interval,
            NOW(),
            '1 day'::interval
        ) AS day_date
    ) trends;
    
    RETURN COALESCE(v_result, '[]'::json);
END;
$$;

-- Get user health score data
CREATE OR REPLACE FUNCTION public.get_user_health_data(p_user_id UUID)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_result JSON;
    v_org_id UUID;
    v_plan TEXT;
    v_days_inactive INTEGER;
    v_error_count INTEGER;
    v_flow_count INTEGER;
    v_flow_limit INTEGER;
    v_profile_completeness INTEGER;
    v_has_failed_payment BOOLEAN;
BEGIN
    -- Get organization
    SELECT om.organization_id INTO v_org_id
    FROM public.organization_members om
    WHERE om.user_id = p_user_id
    LIMIT 1;
    
    IF v_org_id IS NULL THEN
        RETURN json_build_object('error', 'User not found in organization');
    END IF;
    
    -- Get plan
    SELECT COALESCE(os.plan_id, 'free') INTO v_plan
    FROM public.organization_subscriptions os
    WHERE os.organization_id = v_org_id;
    
    -- Days since last activity
    SELECT COALESCE(
        EXTRACT(DAY FROM NOW() - MAX(created_at))::integer,
        999
    ) INTO v_days_inactive
    FROM public.prospect_activities
    WHERE organization_id = v_org_id;
    
    -- Error count in last 30 days
    SELECT COUNT(*) INTO v_error_count
    FROM public.research_briefs
    WHERE organization_id = v_org_id
    AND status = 'failed'
    AND created_at > NOW() - INTERVAL '30 days';
    
    -- Current flow usage
    SELECT COALESCE(ur.flow_count, 0), COALESCE((sp.features->>'flow_limit')::integer, 2)
    INTO v_flow_count, v_flow_limit
    FROM public.organization_subscriptions os
    JOIN public.subscription_plans sp ON os.plan_id = sp.id
    LEFT JOIN public.usage_records ur ON ur.organization_id = v_org_id 
        AND ur.period_start = date_trunc('month', NOW())
    WHERE os.organization_id = v_org_id;
    
    -- Profile completeness (simplified)
    SELECT COALESCE(
        (SELECT CASE 
            WHEN sp.job_title IS NOT NULL AND sp.experience_years IS NOT NULL THEN 80
            WHEN sp.job_title IS NOT NULL THEN 50
            ELSE 20
        END
        FROM public.sales_profiles sp
        WHERE sp.organization_id = v_org_id), 0
    ) INTO v_profile_completeness;
    
    -- Check for failed payments
    SELECT EXISTS (
        SELECT 1 FROM public.organization_subscriptions os
        WHERE os.organization_id = v_org_id
        AND os.status = 'past_due'
    ) INTO v_has_failed_payment;
    
    SELECT json_build_object(
        'plan', COALESCE(v_plan, 'free'),
        'days_since_last_activity', COALESCE(v_days_inactive, 0),
        'error_count_30d', COALESCE(v_error_count, 0),
        'flow_count', COALESCE(v_flow_count, 0),
        'flow_limit', COALESCE(v_flow_limit, 2),
        'flow_usage_percent', CASE 
            WHEN v_flow_limit <= 0 THEN 0
            ELSE ROUND(v_flow_count::numeric / v_flow_limit, 2)
        END,
        'profile_completeness', COALESCE(v_profile_completeness, 0),
        'has_failed_payment', COALESCE(v_has_failed_payment, false)
    ) INTO v_result;
    
    RETURN v_result;
END;
$$;

-- ============================================================
-- 7. TRIGGER FOR UPDATED_AT ON ADMIN_NOTES
-- ============================================================

CREATE OR REPLACE FUNCTION public.update_admin_notes_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS admin_notes_updated_at_trigger ON admin_notes;
CREATE TRIGGER admin_notes_updated_at_trigger
    BEFORE UPDATE ON admin_notes
    FOR EACH ROW
    EXECUTE FUNCTION public.update_admin_notes_updated_at();

-- ============================================================
-- 8. GRANTS FOR SERVICE ROLE
-- ============================================================

-- Grant execute on helper functions
GRANT EXECUTE ON FUNCTION public.is_admin() TO authenticated;
GRANT EXECUTE ON FUNCTION public.is_super_admin() TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_admin_role() TO authenticated;
GRANT EXECUTE ON FUNCTION public.calculate_mrr() TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_job_stats_24h(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_admin_dashboard_metrics() TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_admin_usage_trends(INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_user_health_data(UUID) TO authenticated;

-- ============================================================
-- MIGRATION COMPLETE
-- ============================================================
-- 
-- Next steps:
-- 1. Run this migration in Supabase SQL Editor
-- 2. Bootstrap first admin using:
--    INSERT INTO admin_users (user_id, role, is_active)
--    VALUES ('YOUR-USER-UUID-HERE', 'super_admin', true);
-- 
-- Get your user UUID with:
--    SELECT id FROM auth.users WHERE email = 'your@email.com';
-- ============================================================

