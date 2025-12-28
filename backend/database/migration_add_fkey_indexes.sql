-- ============================================================
-- Migration: Add Missing Foreign Key Indexes
-- Date: 23 December 2025
-- 
-- Fixes Supabase Advisor INFO warnings for unindexed foreign keys
-- These indexes improve JOIN performance on foreign key columns
-- ============================================================

-- admin_alerts
CREATE INDEX IF NOT EXISTS idx_admin_alerts_acknowledged_by 
    ON admin_alerts(acknowledged_by);

CREATE INDEX IF NOT EXISTS idx_admin_alerts_resolved_by 
    ON admin_alerts(resolved_by);

-- affiliate_clicks
CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_signup_user 
    ON affiliate_clicks(signup_user_id);

-- affiliate_referrals
CREATE INDEX IF NOT EXISTS idx_affiliate_referrals_click 
    ON affiliate_referrals(click_id);

-- billing_archive
CREATE INDEX IF NOT EXISTS idx_billing_archive_gdpr_request 
    ON billing_archive(gdpr_request_id);

-- calendar_meetings
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_followup 
    ON calendar_meetings(followup_id);

CREATE INDEX IF NOT EXISTS idx_calendar_meetings_legacy_meeting 
    ON calendar_meetings(legacy_meeting_id);

CREATE INDEX IF NOT EXISTS idx_calendar_meetings_preparation 
    ON calendar_meetings(preparation_id);

-- external_recordings
CREATE INDEX IF NOT EXISTS idx_external_recordings_imported_followup 
    ON external_recordings(imported_followup_id);

-- gdpr_data_exports
CREATE INDEX IF NOT EXISTS idx_gdpr_data_exports_organization 
    ON gdpr_data_exports(organization_id);

-- meeting_outcomes
CREATE INDEX IF NOT EXISTS idx_meeting_outcomes_followup 
    ON meeting_outcomes(followup_id);

-- mobile_recordings
CREATE INDEX IF NOT EXISTS idx_mobile_recordings_followup 
    ON mobile_recordings(followup_id);

CREATE INDEX IF NOT EXISTS idx_mobile_recordings_prospect 
    ON mobile_recordings(prospect_id);

-- prospecting_results
CREATE INDEX IF NOT EXISTS idx_prospecting_results_duplicate_of 
    ON prospecting_results(duplicate_of);

-- scheduled_recordings
CREATE INDEX IF NOT EXISTS idx_scheduled_recordings_followup 
    ON scheduled_recordings(followup_id);

-- ============================================================
-- NOTE: Unused indexes are intentionally NOT removed
-- ============================================================
-- The 90+ "unused_index" warnings should be ignored for now:
-- 1. Index usage stats reset after database restarts
-- 2. Many indexes support RLS policies (indirect usage)
-- 3. Some indexes are for future/rare query patterns
-- 4. Removing indexes risks breaking queries later
--
-- Review unused indexes periodically (every 3-6 months)
-- Only remove if consistently unused in production
-- ============================================================
