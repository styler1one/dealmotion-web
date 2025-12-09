-- STEP 1: Find all function signatures
-- Run this query first to see what we're dealing with:

SELECT 
    p.proname as function_name,
    pg_get_function_identity_arguments(p.oid) as arguments,
    p.proconfig as config
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public'
AND p.proname IN (
    'calculate_sales_profile_completeness', 
    'calculate_company_profile_completeness', 
    'get_or_create_prospect', 
    'get_or_create_default_deal', 
    'get_or_create_usage_record'
)
ORDER BY p.proname;

