-- =====================================================
-- FIX SECURITY ISSUES
-- =====================================================
-- 1. Security Definer Views - change to SECURITY INVOKER
-- 2. Function Search Path - set explicit search_path
-- =====================================================

-- =====================================================
-- PART 1: FIX SECURITY DEFINER VIEWS
-- Change from SECURITY DEFINER to SECURITY INVOKER
-- This ensures RLS policies are applied to the querying user
-- =====================================================

-- First, let's get the current view definitions and recreate them
-- with SECURITY INVOKER

-- prospect_hub_summary view
DROP VIEW IF EXISTS prospect_hub_summary;
CREATE VIEW prospect_hub_summary 
WITH (security_invoker = true)
AS
SELECT 
    p.id as prospect_id,
    p.company_name,
    p.organization_id,
    p.status,
    p.created_at as prospect_created_at,
    rb.id as latest_research_id,
    rb.status as research_status,
    rb.created_at as research_created_at,
    mp.id as latest_prep_id,
    mp.status as prep_status,
    f.id as latest_followup_id,
    f.status as followup_status,
    f.created_at as followup_created_at,
    f.meeting_date,
    d.id as deal_id,
    d.name as deal_name,
    d.crm_stage as deal_stage,
    d.crm_value_cents as deal_value,
    d.is_active as deal_active
FROM prospects p
LEFT JOIN LATERAL (
    SELECT * FROM research_briefs rb2 
    WHERE rb2.prospect_id = p.id 
    ORDER BY rb2.created_at DESC LIMIT 1
) rb ON true
LEFT JOIN LATERAL (
    SELECT * FROM meeting_preps mp2 
    WHERE mp2.prospect_id = p.id 
    ORDER BY mp2.created_at DESC LIMIT 1
) mp ON true
LEFT JOIN LATERAL (
    SELECT * FROM followups f2 
    WHERE f2.prospect_id = p.id 
    ORDER BY f2.created_at DESC LIMIT 1
) f ON true
LEFT JOIN deals d ON d.prospect_id = p.id;

-- deal_summary view
DROP VIEW IF EXISTS deal_summary;
CREATE VIEW deal_summary 
WITH (security_invoker = true)
AS
SELECT 
    d.id,
    d.name,
    d.description,
    d.prospect_id,
    d.organization_id,
    d.is_active,
    d.crm_stage,
    d.crm_value_cents,
    d.crm_currency,
    d.crm_probability,
    d.crm_expected_close,
    d.created_at,
    d.updated_at,
    p.company_name as prospect_company_name,
    COUNT(DISTINCT mp.id) as prep_count,
    COUNT(DISTINCT f.id) as followup_count,
    MAX(f.meeting_date) as last_meeting_date,
    MAX(f.created_at) as last_followup_date
FROM deals d
LEFT JOIN prospects p ON d.prospect_id = p.id
LEFT JOIN meeting_preps mp ON mp.deal_id = d.id
LEFT JOIN followups f ON f.deal_id = d.id
GROUP BY d.id, d.name, d.description, d.prospect_id, d.organization_id, d.is_active,
         d.crm_stage, d.crm_value_cents, d.crm_currency, d.crm_probability, 
         d.crm_expected_close, d.created_at, d.updated_at, p.company_name;


-- =====================================================
-- PART 2: FIX FUNCTION SEARCH PATH
-- Add SET search_path = '' to all functions
-- =====================================================

-- Drop functions that have return type or parameter name conflicts
-- DO NOT drop is_org_member or get_user_org_ids - they are used by RLS policies
DROP FUNCTION IF EXISTS increment_usage(UUID, TEXT, INTEGER);
DROP FUNCTION IF EXISTS get_knowledge_base_stats(UUID);
DROP FUNCTION IF EXISTS check_usage_limit(UUID, TEXT);
DROP FUNCTION IF EXISTS get_or_create_subscription(UUID);
DROP FUNCTION IF EXISTS get_or_create_usage_record(UUID, TIMESTAMPTZ, TIMESTAMPTZ);
DROP FUNCTION IF EXISTS get_or_create_prospect(UUID, TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS get_or_create_default_deal(UUID, UUID, TEXT);
DROP FUNCTION IF EXISTS get_or_create_prospect_contact(UUID, UUID, TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS calculate_sales_profile_completeness(JSONB);
DROP FUNCTION IF EXISTS calculate_company_profile_completeness(JSONB);

-- update_followup_actions_updated_at
CREATE OR REPLACE FUNCTION update_followup_actions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- calculate_sales_profile_completeness
CREATE OR REPLACE FUNCTION calculate_sales_profile_completeness(profile_data JSONB)
RETURNS INTEGER AS $$
DECLARE
    completeness INTEGER := 0;
    total_fields INTEGER := 10;
    filled_fields INTEGER := 0;
BEGIN
    IF profile_data->>'full_name' IS NOT NULL AND profile_data->>'full_name' != '' THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'email' IS NOT NULL AND profile_data->>'email' != '' THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'phone' IS NOT NULL AND profile_data->>'phone' != '' THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'job_title' IS NOT NULL AND profile_data->>'job_title' != '' THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'linkedin_url' IS NOT NULL AND profile_data->>'linkedin_url' != '' THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'years_experience' IS NOT NULL THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'industries' IS NOT NULL AND jsonb_array_length(profile_data->'industries') > 0 THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'expertise_areas' IS NOT NULL AND jsonb_array_length(profile_data->'expertise_areas') > 0 THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'sales_style' IS NOT NULL AND profile_data->>'sales_style' != '' THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'bio' IS NOT NULL AND profile_data->>'bio' != '' THEN filled_fields := filled_fields + 1; END IF;
    
    completeness := (filled_fields * 100) / total_fields;
    RETURN completeness;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- calculate_company_profile_completeness
CREATE OR REPLACE FUNCTION calculate_company_profile_completeness(profile_data JSONB)
RETURNS INTEGER AS $$
DECLARE
    completeness INTEGER := 0;
    total_fields INTEGER := 8;
    filled_fields INTEGER := 0;
BEGIN
    IF profile_data->>'company_name' IS NOT NULL AND profile_data->>'company_name' != '' THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'website' IS NOT NULL AND profile_data->>'website' != '' THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'industry' IS NOT NULL AND profile_data->>'industry' != '' THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'description' IS NOT NULL AND profile_data->>'description' != '' THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'target_market' IS NOT NULL AND profile_data->>'target_market' != '' THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'value_proposition' IS NOT NULL AND profile_data->>'value_proposition' != '' THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'products_services' IS NOT NULL AND jsonb_array_length(profile_data->'products_services') > 0 THEN filled_fields := filled_fields + 1; END IF;
    IF profile_data->>'unique_selling_points' IS NOT NULL AND jsonb_array_length(profile_data->'unique_selling_points') > 0 THEN filled_fields := filled_fields + 1; END IF;
    
    completeness := (filled_fields * 100) / total_fields;
    RETURN completeness;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- update_updated_at_column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- update_user_settings_updated_at
CREATE OR REPLACE FUNCTION update_user_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- get_user_org_ids
CREATE OR REPLACE FUNCTION get_user_org_ids()
RETURNS SETOF UUID AS $$
    SELECT organization_id FROM public.organization_members WHERE user_id = auth.uid()
$$ LANGUAGE SQL SECURITY DEFINER SET search_path = '';

-- get_or_create_prospect
CREATE OR REPLACE FUNCTION get_or_create_prospect(
    p_organization_id UUID,
    p_company_name TEXT,
    p_website TEXT DEFAULT NULL,
    p_linkedin_url TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_prospect_id UUID;
BEGIN
    -- Try to find existing prospect
    SELECT id INTO v_prospect_id
    FROM public.prospects
    WHERE organization_id = p_organization_id
      AND LOWER(company_name) = LOWER(p_company_name)
    LIMIT 1;
    
    -- Create if not exists
    IF v_prospect_id IS NULL THEN
        INSERT INTO public.prospects (organization_id, company_name, website, linkedin_url)
        VALUES (p_organization_id, p_company_name, p_website, p_linkedin_url)
        RETURNING id INTO v_prospect_id;
    END IF;
    
    RETURN v_prospect_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- update_prospect_activity
CREATE OR REPLACE FUNCTION update_prospect_activity()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.prospects 
    SET last_activity_at = NOW(),
        updated_at = NOW()
    WHERE id = COALESCE(NEW.prospect_id, OLD.prospect_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- log_deal_activity
CREATE OR REPLACE FUNCTION log_deal_activity()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.prospect_activities (
        prospect_id,
        activity_type,
        title,
        description,
        metadata
    )
    SELECT 
        NEW.prospect_id,
        'deal_updated',
        'Deal: ' || NEW.name,
        'Deal stage: ' || NEW.stage,
        jsonb_build_object('deal_id', NEW.id, 'stage', NEW.stage, 'value', NEW.value)
    WHERE NEW.prospect_id IS NOT NULL;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- log_meeting_activity
CREATE OR REPLACE FUNCTION log_meeting_activity()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.prospect_activities (
        prospect_id,
        activity_type,
        title,
        description,
        metadata
    )
    SELECT 
        NEW.prospect_id,
        'meeting_scheduled',
        'Meeting: ' || COALESCE(NEW.meeting_type, 'Scheduled'),
        'Meeting on ' || COALESCE(NEW.meeting_date::TEXT, 'TBD'),
        jsonb_build_object('meeting_id', NEW.id, 'meeting_date', NEW.meeting_date)
    WHERE NEW.prospect_id IS NOT NULL;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- log_prep_activity
CREATE OR REPLACE FUNCTION log_prep_activity()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.prospect_activities (
        prospect_id,
        activity_type,
        title,
        description,
        metadata
    )
    SELECT 
        NEW.prospect_id,
        'prep_created',
        'Preparation Brief',
        'Status: ' || NEW.status,
        jsonb_build_object('prep_id', NEW.id, 'status', NEW.status)
    WHERE NEW.prospect_id IS NOT NULL;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- log_followup_activity
CREATE OR REPLACE FUNCTION log_followup_activity()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.prospect_activities (
        prospect_id,
        activity_type,
        title,
        description,
        metadata
    )
    SELECT 
        NEW.prospect_id,
        'followup_created',
        'Follow-up Brief',
        'Status: ' || NEW.status,
        jsonb_build_object('followup_id', NEW.id, 'status', NEW.status)
    WHERE NEW.prospect_id IS NOT NULL;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- log_research_activity
CREATE OR REPLACE FUNCTION log_research_activity()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.prospect_activities (
        prospect_id,
        activity_type,
        title,
        description,
        metadata
    )
    SELECT 
        NEW.prospect_id,
        'research_completed',
        'Research Brief',
        'Status: ' || NEW.status,
        jsonb_build_object('research_id', NEW.id, 'status', NEW.status)
    WHERE NEW.prospect_id IS NOT NULL;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- get_or_create_default_deal
CREATE OR REPLACE FUNCTION get_or_create_default_deal(
    p_organization_id UUID,
    p_prospect_id UUID,
    p_prospect_name TEXT
)
RETURNS UUID AS $$
DECLARE
    v_deal_id UUID;
BEGIN
    -- Try to find existing deal for this prospect
    SELECT id INTO v_deal_id
    FROM public.deals
    WHERE organization_id = p_organization_id
      AND prospect_id = p_prospect_id
    LIMIT 1;
    
    -- Create if not exists
    IF v_deal_id IS NULL THEN
        INSERT INTO public.deals (organization_id, prospect_id, name, stage)
        VALUES (p_organization_id, p_prospect_id, p_prospect_name || ' - Deal', 'lead')
        RETURNING id INTO v_deal_id;
    END IF;
    
    RETURN v_deal_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- update_coach_updated_at
CREATE OR REPLACE FUNCTION update_coach_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- get_or_create_subscription
CREATE OR REPLACE FUNCTION get_or_create_subscription(p_organization_id UUID)
RETURNS UUID AS $$
DECLARE
    v_subscription_id UUID;
BEGIN
    SELECT id INTO v_subscription_id
    FROM public.organization_subscriptions
    WHERE organization_id = p_organization_id
    LIMIT 1;
    
    IF v_subscription_id IS NULL THEN
        INSERT INTO public.organization_subscriptions (organization_id, plan_id, status)
        VALUES (p_organization_id, 'free', 'active')
        RETURNING id INTO v_subscription_id;
    END IF;
    
    RETURN v_subscription_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- get_or_create_usage_record
CREATE OR REPLACE FUNCTION get_or_create_usage_record(
    p_organization_id UUID,
    p_period_start TIMESTAMPTZ,
    p_period_end TIMESTAMPTZ
)
RETURNS UUID AS $$
DECLARE
    v_record_id UUID;
BEGIN
    SELECT id INTO v_record_id
    FROM public.usage_records
    WHERE organization_id = p_organization_id
      AND period_start = p_period_start
    LIMIT 1;
    
    IF v_record_id IS NULL THEN
        INSERT INTO public.usage_records (organization_id, period_start, period_end)
        VALUES (p_organization_id, p_period_start, p_period_end)
        RETURNING id INTO v_record_id;
    END IF;
    
    RETURN v_record_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- increment_usage
CREATE OR REPLACE FUNCTION increment_usage(
    p_organization_id UUID,
    p_usage_type TEXT,
    p_amount INTEGER DEFAULT 1
)
RETURNS VOID AS $$
DECLARE
    v_period_start TIMESTAMPTZ;
    v_period_end TIMESTAMPTZ;
    v_record_id UUID;
BEGIN
    v_period_start := date_trunc('month', NOW());
    v_period_end := date_trunc('month', NOW()) + INTERVAL '1 month';
    
    v_record_id := get_or_create_usage_record(p_organization_id, v_period_start, v_period_end);
    
    UPDATE public.usage_records
    SET 
        research_count = CASE WHEN p_usage_type = 'research' THEN research_count + p_amount ELSE research_count END,
        prep_count = CASE WHEN p_usage_type = 'prep' THEN prep_count + p_amount ELSE prep_count END,
        followup_count = CASE WHEN p_usage_type = 'followup' THEN followup_count + p_amount ELSE followup_count END,
        updated_at = NOW()
    WHERE id = v_record_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- check_usage_limit
CREATE OR REPLACE FUNCTION check_usage_limit(
    p_organization_id UUID,
    p_usage_type TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    v_current_usage INTEGER;
    v_limit INTEGER;
    v_plan_id TEXT;
BEGIN
    -- Get current plan
    SELECT plan_id INTO v_plan_id
    FROM public.organization_subscriptions
    WHERE organization_id = p_organization_id
    LIMIT 1;
    
    -- Set limits based on plan
    v_limit := CASE 
        WHEN v_plan_id = 'pro' THEN 1000
        WHEN v_plan_id = 'starter' THEN 50
        ELSE 10 -- free
    END;
    
    -- Get current usage
    SELECT 
        CASE p_usage_type
            WHEN 'research' THEN COALESCE(research_count, 0)
            WHEN 'prep' THEN COALESCE(prep_count, 0)
            WHEN 'followup' THEN COALESCE(followup_count, 0)
            ELSE 0
        END INTO v_current_usage
    FROM public.usage_records
    WHERE organization_id = p_organization_id
      AND period_start = date_trunc('month', NOW())
    LIMIT 1;
    
    RETURN COALESCE(v_current_usage, 0) < v_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- update_updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- update_prospect_contacts_updated_at
CREATE OR REPLACE FUNCTION update_prospect_contacts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- ensure_single_primary_contact
CREATE OR REPLACE FUNCTION ensure_single_primary_contact()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_primary = TRUE THEN
        UPDATE public.prospect_contacts
        SET is_primary = FALSE
        WHERE prospect_id = NEW.prospect_id
          AND id != NEW.id
          AND is_primary = TRUE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- get_or_create_prospect_contact
CREATE OR REPLACE FUNCTION get_or_create_prospect_contact(
    p_prospect_id UUID,
    p_organization_id UUID,
    p_name TEXT,
    p_email TEXT DEFAULT NULL,
    p_linkedin_url TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_contact_id UUID;
BEGIN
    -- Try to find existing contact
    SELECT id INTO v_contact_id
    FROM public.prospect_contacts
    WHERE prospect_id = p_prospect_id
      AND (
          (p_email IS NOT NULL AND LOWER(email) = LOWER(p_email))
          OR (p_linkedin_url IS NOT NULL AND LOWER(linkedin_url) = LOWER(p_linkedin_url))
          OR (p_email IS NULL AND p_linkedin_url IS NULL AND LOWER(name) = LOWER(p_name))
      )
    LIMIT 1;
    
    -- Create if not exists
    IF v_contact_id IS NULL THEN
        INSERT INTO public.prospect_contacts (prospect_id, organization_id, name, email, linkedin_url)
        VALUES (p_prospect_id, p_organization_id, p_name, p_email, p_linkedin_url)
        RETURNING id INTO v_contact_id;
    END IF;
    
    RETURN v_contact_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- is_org_member (keep original parameter name to avoid breaking RLS policies)
CREATE OR REPLACE FUNCTION is_org_member(org_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM public.organization_members
        WHERE organization_id = org_id
          AND user_id = auth.uid()
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- get_knowledge_base_stats
CREATE OR REPLACE FUNCTION get_knowledge_base_stats(p_organization_id UUID)
RETURNS TABLE (
    total_files INTEGER,
    total_chunks INTEGER,
    total_size_bytes BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(DISTINCT f.id)::INTEGER as total_files,
        COUNT(c.id)::INTEGER as total_chunks,
        COALESCE(SUM(f.file_size), 0)::BIGINT as total_size_bytes
    FROM public.knowledge_base_files f
    LEFT JOIN public.knowledge_base_chunks c ON c.file_id = f.id
    WHERE f.organization_id = p_organization_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- update_kb_file_processed_at
CREATE OR REPLACE FUNCTION update_kb_file_processed_at()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'processed' AND OLD.status != 'processed' THEN
        NEW.processed_at = NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';


-- =====================================================
-- PART 3: LEAKED PASSWORD PROTECTION
-- This needs to be enabled in the Supabase Dashboard:
-- Go to: Authentication > Providers > Email > Enable "Leaked password protection"
-- =====================================================

-- Note: This cannot be done via SQL, must be done in the dashboard.
-- See: https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection

