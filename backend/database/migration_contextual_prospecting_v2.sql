-- ============================================================
-- MIGRATION: Contextual Prospecting V2 - Add Reference Customers
-- Date: December 2025
-- 
-- Adds reference customer fields to existing prospecting_searches table
-- for context enrichment (NOT firmographic lookalike)
-- ============================================================

-- Add reference_customers column (array of company names)
ALTER TABLE prospecting_searches 
ADD COLUMN IF NOT EXISTS reference_customers TEXT[];

-- Add reference_context column (LLM-extracted context from references)
ALTER TABLE prospecting_searches 
ADD COLUMN IF NOT EXISTS reference_context TEXT;

-- Add comment for documentation
COMMENT ON COLUMN prospecting_searches.reference_customers IS 
'Array of company names that are 100% fit - used for context enrichment, NOT firmographic matching';

COMMENT ON COLUMN prospecting_searches.reference_context IS 
'LLM-extracted context from reference customers (situations, signals, challenges they share)';

-- ============================================================
-- END OF MIGRATION
-- ============================================================

