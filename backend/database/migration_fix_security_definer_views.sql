-- ============================================================
-- MIGRATION: Fix Security Definer Views
-- ============================================================
-- Date: 2025-12-23
-- Description: Convert SECURITY DEFINER views to SECURITY INVOKER
--              to respect RLS policies of the querying user
-- 
-- Fixes Supabase Advisor warnings:
-- - public.api_usage_monthly
-- - public.api_usage_daily  
-- - public.organization_usage_summary
-- ============================================================

-- ============================================================
-- 1. RECREATE api_usage_monthly WITH SECURITY INVOKER
-- ============================================================
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

-- Grant access
GRANT SELECT ON api_usage_monthly TO authenticated;
GRANT SELECT ON api_usage_monthly TO service_role;

-- ============================================================
-- 2. RECREATE api_usage_daily WITH SECURITY INVOKER
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

-- Grant access
GRANT SELECT ON api_usage_daily TO authenticated;
GRANT SELECT ON api_usage_daily TO service_role;

-- ============================================================
-- 3. RECREATE organization_usage_summary WITH SECURITY INVOKER
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

-- Grant access
GRANT SELECT ON organization_usage_summary TO authenticated;
GRANT SELECT ON organization_usage_summary TO service_role;

-- ============================================================
-- VERIFICATION
-- ============================================================
-- After running this migration, verify with:
-- SELECT schemaname, viewname, definition 
-- FROM pg_views 
-- WHERE viewname IN ('api_usage_monthly', 'api_usage_daily', 'organization_usage_summary');
--
-- And check security_invoker is set:
-- SELECT relname, reloptions 
-- FROM pg_class 
-- WHERE relname IN ('api_usage_monthly', 'api_usage_daily', 'organization_usage_summary');
