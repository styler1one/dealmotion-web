-- ============================================================
-- Admin Health Monitoring Migration
-- 
-- Adds tables for:
-- 1. Service health logs (30-day history)
-- 2. Alert configurations
-- 3. Alert history
--
-- Run: Execute in Supabase SQL Editor
-- ============================================================

-- ============================================================
-- 1. SERVICE HEALTH LOGS - Track health checks over time
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_service_health_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Service identification
    service_name TEXT NOT NULL,          -- 'supabase', 'anthropic', 'stripe', etc.
    
    -- Health status
    status TEXT NOT NULL,                -- 'healthy', 'degraded', 'down'
    response_time_ms INTEGER,            -- Response time in milliseconds
    
    -- Error details (if any)
    error_message TEXT,
    error_code TEXT,
    
    -- Timestamp
    checked_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_health_logs_service 
ON admin_service_health_logs(service_name);

CREATE INDEX IF NOT EXISTS idx_health_logs_service_date 
ON admin_service_health_logs(service_name, checked_at DESC);

CREATE INDEX IF NOT EXISTS idx_health_logs_date 
ON admin_service_health_logs(checked_at DESC);

CREATE INDEX IF NOT EXISTS idx_health_logs_status 
ON admin_service_health_logs(status) WHERE status != 'healthy';

-- ============================================================
-- 2. ALERT CONFIGURATIONS - Define alert thresholds
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_alert_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- What to monitor
    service_name TEXT NOT NULL,          -- 'anthropic', 'all_services', etc.
    metric_type TEXT NOT NULL,           -- 'status', 'response_time', 'error_rate', 'cost'
    
    -- Thresholds
    warning_threshold DECIMAL(10,2),     -- e.g., 500ms response time
    critical_threshold DECIMAL(10,2),    -- e.g., 1000ms response time
    
    -- Alert settings
    alert_email TEXT,                    -- Email to notify
    cooldown_minutes INTEGER DEFAULT 60, -- Don't re-alert within X minutes
    is_enabled BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint: one config per service+metric combo
CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_config_unique 
ON admin_alert_configs(service_name, metric_type);

-- ============================================================
-- 3. ALERT HISTORY - Track sent alerts
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_alert_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Alert details
    config_id UUID REFERENCES admin_alert_configs(id) ON DELETE SET NULL,
    service_name TEXT NOT NULL,
    alert_type TEXT NOT NULL,            -- 'warning', 'critical', 'resolved'
    
    -- Context
    title TEXT NOT NULL,
    message TEXT,
    metric_value DECIMAL(10,2),
    threshold_value DECIMAL(10,2),
    
    -- Notification status
    email_sent BOOLEAN DEFAULT FALSE,
    email_sent_at TIMESTAMPTZ,
    email_recipient TEXT,
    
    -- Acknowledgement
    acknowledged_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    acknowledged_at TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_history_service 
ON admin_alert_history(service_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alert_history_unacked 
ON admin_alert_history(acknowledged_at) WHERE acknowledged_at IS NULL;

-- ============================================================
-- 4. AUTO-CLEANUP: Remove health logs older than 30 days
-- ============================================================
CREATE OR REPLACE FUNCTION cleanup_old_health_logs()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    DELETE FROM admin_service_health_logs
    WHERE checked_at < NOW() - INTERVAL '30 days';
    
    -- Also cleanup old alert history (keep 90 days)
    DELETE FROM admin_alert_history
    WHERE created_at < NOW() - INTERVAL '90 days'
      AND acknowledged_at IS NOT NULL;
END;
$$;

-- ============================================================
-- 5. VIEWS: Aggregated health statistics
-- ============================================================

-- View: Service uptime last 24h
CREATE OR REPLACE VIEW admin_service_uptime_24h AS
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

-- View: Service uptime last 7 days
CREATE OR REPLACE VIEW admin_service_uptime_7d AS
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

-- View: Service uptime last 30 days
CREATE OR REPLACE VIEW admin_service_uptime_30d AS
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

-- ============================================================
-- 6. INSERT DEFAULT ALERT CONFIGS
-- ============================================================
INSERT INTO admin_alert_configs (service_name, metric_type, warning_threshold, critical_threshold, alert_email, is_enabled)
VALUES 
    -- Service status alerts
    ('supabase', 'status', 1, 1, NULL, TRUE),      -- 1 = degraded triggers warning
    ('anthropic', 'status', 1, 1, NULL, TRUE),
    ('stripe', 'status', 1, 1, NULL, TRUE),
    ('inngest', 'status', 1, 1, NULL, TRUE),
    ('deepgram', 'status', 1, 1, NULL, TRUE),
    ('recall', 'status', 1, 1, NULL, TRUE),
    ('pinecone', 'status', 1, 1, NULL, TRUE),
    ('voyage', 'status', 1, 1, NULL, TRUE),
    ('exa', 'status', 1, 1, NULL, TRUE),
    ('google', 'status', 1, 1, NULL, TRUE),
    ('sendgrid', 'status', 1, 1, NULL, TRUE),
    
    -- Response time alerts (ms)
    ('anthropic', 'response_time', 5000, 10000, NULL, TRUE),  -- 5s warning, 10s critical
    ('supabase', 'response_time', 1000, 3000, NULL, TRUE),    -- 1s warning, 3s critical
    
    -- Daily cost alert (cents)
    ('all_services', 'cost', 5000, 10000, NULL, TRUE)         -- $50 warning, $100 critical
ON CONFLICT (service_name, metric_type) DO NOTHING;

-- ============================================================
-- 7. FUNCTION: Log health check result
-- ============================================================
CREATE OR REPLACE FUNCTION log_service_health(
    p_service_name TEXT,
    p_status TEXT,
    p_response_time_ms INTEGER DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL,
    p_error_code TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_log_id UUID;
BEGIN
    INSERT INTO admin_service_health_logs (
        service_name,
        status,
        response_time_ms,
        error_message,
        error_code
    ) VALUES (
        p_service_name,
        p_status,
        p_response_time_ms,
        p_error_message,
        p_error_code
    )
    RETURNING id INTO v_log_id;
    
    RETURN v_log_id;
END;
$$;

-- ============================================================
-- 8. Grant permissions
-- ============================================================
-- These tables should only be accessible via service role
-- No RLS needed as this is admin-only

COMMENT ON TABLE admin_service_health_logs IS 'Tracks health status of external services over time (30 day retention)';
COMMENT ON TABLE admin_alert_configs IS 'Configuration for health monitoring alerts';
COMMENT ON TABLE admin_alert_history IS 'History of sent alerts';


