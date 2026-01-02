-- ============================================================
-- Migration: Fix Admin Tables Security
-- 
-- Fixes:
-- 1. Enable RLS on admin tables
-- 2. Add admin-only policies
-- 3. Fix views to use SECURITY INVOKER
-- ============================================================

-- ============================================================
-- 1. Enable RLS on admin tables
-- ============================================================

ALTER TABLE admin_service_health_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_alert_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_alert_history ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 2. Create admin-only policies
-- These tables should only be accessible by admins via service key
-- Admin users are tracked in admin_users table
-- ============================================================

-- admin_service_health_logs
DROP POLICY IF EXISTS "Admin only health logs" ON admin_service_health_logs;
CREATE POLICY "Admin only health logs" ON admin_service_health_logs
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM admin_users 
            WHERE user_id = (select auth.uid()) 
            AND is_active = TRUE
        )
    );

-- admin_alert_configs
DROP POLICY IF EXISTS "Admin only alert configs" ON admin_alert_configs;
CREATE POLICY "Admin only alert configs" ON admin_alert_configs
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM admin_users 
            WHERE user_id = (select auth.uid()) 
            AND is_active = TRUE
        )
    );

-- admin_alert_history
DROP POLICY IF EXISTS "Admin only alert history" ON admin_alert_history;
CREATE POLICY "Admin only alert history" ON admin_alert_history
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM admin_users 
            WHERE user_id = (select auth.uid()) 
            AND is_active = TRUE
        )
    );

-- ============================================================
-- 3. Recreate views with SECURITY INVOKER
-- Drop and recreate to change security mode
-- ============================================================

-- Drop existing views
DROP VIEW IF EXISTS admin_service_uptime_24h;
DROP VIEW IF EXISTS admin_service_uptime_7d;
DROP VIEW IF EXISTS admin_service_uptime_30d;

-- Recreate with SECURITY INVOKER
CREATE VIEW admin_service_uptime_24h WITH (security_invoker = true) AS
SELECT 
    service_name,
    COUNT(*) as total_checks,
    COUNT(*) FILTER (WHERE status = 'healthy') as healthy_checks,
    COUNT(*) FILTER (WHERE status = 'degraded') as degraded_checks,
    COUNT(*) FILTER (WHERE status = 'down') as down_checks,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'healthy')::numeric / 
        NULLIF(COUNT(*)::numeric, 0) * 100, 
        2
    ) as uptime_percent,
    ROUND(AVG(response_time_ms), 0) as avg_response_time_ms,
    MAX(response_time_ms) as max_response_time_ms,
    MIN(response_time_ms) as min_response_time_ms
FROM admin_service_health_logs
WHERE checked_at >= NOW() - INTERVAL '24 hours'
GROUP BY service_name;

CREATE VIEW admin_service_uptime_7d WITH (security_invoker = true) AS
SELECT 
    service_name,
    COUNT(*) as total_checks,
    COUNT(*) FILTER (WHERE status = 'healthy') as healthy_checks,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'healthy')::numeric / 
        NULLIF(COUNT(*)::numeric, 0) * 100, 
        2
    ) as uptime_percent,
    ROUND(AVG(response_time_ms), 0) as avg_response_time_ms
FROM admin_service_health_logs
WHERE checked_at >= NOW() - INTERVAL '7 days'
GROUP BY service_name;

CREATE VIEW admin_service_uptime_30d WITH (security_invoker = true) AS
SELECT 
    service_name,
    COUNT(*) as total_checks,
    COUNT(*) FILTER (WHERE status = 'healthy') as healthy_checks,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'healthy')::numeric / 
        NULLIF(COUNT(*)::numeric, 0) * 100, 
        2
    ) as uptime_percent,
    ROUND(AVG(response_time_ms), 0) as avg_response_time_ms
FROM admin_service_health_logs
WHERE checked_at >= NOW() - INTERVAL '30 days'
GROUP BY service_name;

-- Log migration
DO $$
BEGIN
    RAISE NOTICE 'Admin Security fix migration complete';
END $$;

