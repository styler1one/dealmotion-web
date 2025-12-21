-- ============================================================
-- Migration: Credit Transactions V5 - Detailed Logging
-- 
-- Adds user_id and metadata to credit_transactions for
-- full audit trail and transparency.
-- ============================================================

-- Add user_id column
ALTER TABLE credit_transactions 
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL;

-- Add metadata JSONB column for context
ALTER TABLE credit_transactions 
ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Add index for user queries
CREATE INDEX IF NOT EXISTS idx_credit_tx_user 
ON credit_transactions(user_id) WHERE user_id IS NOT NULL;

-- Add index for reference_type queries (for filtering by action type)
CREATE INDEX IF NOT EXISTS idx_credit_tx_reference_type 
ON credit_transactions(organization_id, reference_type, created_at DESC);

-- Update descriptions for existing transactions to be more user-friendly
UPDATE credit_transactions 
SET description = CASE 
    WHEN reference_type = 'research_flow' THEN 'Research: ' || COALESCE(metadata->>'company_name', 'Unknown')
    WHEN reference_type = 'preparation' THEN 'Preparation: ' || COALESCE(metadata->>'prospect_company', 'Unknown')
    WHEN reference_type = 'prospect_discovery' THEN 'Prospect Discovery'
    WHEN reference_type = 'followup' THEN 'Meeting Follow-up'
    WHEN reference_type = 'followup_action' THEN 'Follow-up Action'
    WHEN reference_type = 'transcription_minute' THEN 'Transcription'
    WHEN reference_type = 'contact_search' THEN 'Contact: ' || COALESCE(metadata->>'contact_name', 'Unknown')
    WHEN reference_type = 'subscription' THEN description
    WHEN reference_type = 'pack_purchase' THEN description
    ELSE description
END
WHERE description LIKE 'Consumed%';

-- Log migration
DO $$
BEGIN
    RAISE NOTICE 'Credit Transactions V5 migration complete - added user_id and metadata columns';
END $$;

