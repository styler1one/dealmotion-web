-- STEP 2: Drop only the OLD function versions (without search_path)
-- The new versions with search_path are already correct

-- Drop OLD calculate_company_profile_completeness(uuid)
DROP FUNCTION IF EXISTS calculate_company_profile_completeness(uuid);

-- Drop OLD calculate_sales_profile_completeness(uuid)  
DROP FUNCTION IF EXISTS calculate_sales_profile_completeness(uuid);

-- Drop OLD get_or_create_default_deal(uuid, uuid, uuid)
DROP FUNCTION IF EXISTS get_or_create_default_deal(uuid, uuid, uuid);

-- Drop OLD get_or_create_prospect(uuid, text) - only 2 params
DROP FUNCTION IF EXISTS get_or_create_prospect(uuid, text);

-- Drop OLD get_or_create_usage_record(uuid) - only 1 param
DROP FUNCTION IF EXISTS get_or_create_usage_record(uuid);

-- Verify: Run the step1 query again - should now show only 5 functions, all with search_path set

