-- =====================================================
-- AGGRESSIVE FIX: Drop ALL versions of functions
-- =====================================================

-- First, let's see what function signatures exist
-- Run this query to check: 
-- SELECT proname, pg_get_function_identity_arguments(oid) as args 
-- FROM pg_proc WHERE proname IN ('calculate_sales_profile_completeness', 'calculate_company_profile_completeness', 'get_or_create_prospect', 'get_or_create_default_deal', 'get_or_create_usage_record');

-- Drop ALL possible signatures using CASCADE
DROP FUNCTION IF EXISTS calculate_sales_profile_completeness CASCADE;
DROP FUNCTION IF EXISTS calculate_company_profile_completeness CASCADE;
DROP FUNCTION IF EXISTS get_or_create_prospect CASCADE;
DROP FUNCTION IF EXISTS get_or_create_default_deal CASCADE;
DROP FUNCTION IF EXISTS get_or_create_usage_record CASCADE;

-- Now recreate with search_path set

-- calculate_sales_profile_completeness
CREATE FUNCTION calculate_sales_profile_completeness(profile_data JSONB)
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
CREATE FUNCTION calculate_company_profile_completeness(profile_data JSONB)
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

-- get_or_create_prospect
CREATE FUNCTION get_or_create_prospect(
    p_organization_id UUID,
    p_company_name TEXT,
    p_website TEXT DEFAULT NULL,
    p_linkedin_url TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_prospect_id UUID;
BEGIN
    SELECT id INTO v_prospect_id
    FROM public.prospects
    WHERE organization_id = p_organization_id
      AND LOWER(company_name) = LOWER(p_company_name)
    LIMIT 1;
    
    IF v_prospect_id IS NULL THEN
        INSERT INTO public.prospects (organization_id, company_name, website, linkedin_url)
        VALUES (p_organization_id, p_company_name, p_website, p_linkedin_url)
        RETURNING id INTO v_prospect_id;
    END IF;
    
    RETURN v_prospect_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- get_or_create_default_deal
CREATE FUNCTION get_or_create_default_deal(
    p_organization_id UUID,
    p_prospect_id UUID,
    p_prospect_name TEXT
)
RETURNS UUID AS $$
DECLARE
    v_deal_id UUID;
BEGIN
    SELECT id INTO v_deal_id
    FROM public.deals
    WHERE organization_id = p_organization_id
      AND prospect_id = p_prospect_id
    LIMIT 1;
    
    IF v_deal_id IS NULL THEN
        INSERT INTO public.deals (organization_id, prospect_id, name)
        VALUES (p_organization_id, p_prospect_id, p_prospect_name || ' - Deal')
        RETURNING id INTO v_deal_id;
    END IF;
    
    RETURN v_deal_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- get_or_create_usage_record
CREATE FUNCTION get_or_create_usage_record(
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

-- Verify the fix worked:
-- SELECT proname, prosecdef, proconfig 
-- FROM pg_proc 
-- WHERE proname IN ('calculate_sales_profile_completeness', 'calculate_company_profile_completeness', 'get_or_create_prospect', 'get_or_create_default_deal', 'get_or_create_usage_record')
-- AND pronamespace = 'public'::regnamespace;

