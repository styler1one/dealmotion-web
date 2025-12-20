-- ============================================================
-- MIGRATION: Contextual Prospecting Engine
-- Date: December 2025
-- 
-- Adds tables for AI-powered prospect discovery:
-- - prospecting_searches: User search sessions with input parameters
-- - prospecting_results: Discovered prospects with fit scoring
--
-- Concept: Find prospects that match seller context and proposition,
-- not just firmographic filters. Uses Exa AI for semantic discovery.
-- ============================================================

-- ============================================================
-- 1. PROSPECTING SEARCHES TABLE
-- ============================================================
-- Stores each prospecting search session with user input

CREATE TABLE IF NOT EXISTS prospecting_searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- User Input (max 6 fields as per spec)
    region TEXT,                          -- "Netherlands", "DACH", "Benelux"
    sector TEXT,                          -- Free text: "logistics", "manufacturing"
    company_size TEXT,                    -- Human language: "mid-sized", "enterprise", "SMB"
    proposition TEXT,                     -- "What do we sell?" in 1 sentence
    target_role TEXT,                     -- "For whom is this relevant?" (CFO, CTO, etc.)
    pain_point TEXT,                      -- "Where is pain/urgency?" free text
    
    -- Reference Customers (optional context enrichment)
    -- NOT for firmographic matching, but for LLM to understand "what do these have in common"
    reference_customers TEXT[],           -- Array of company names that are 100% fit
    reference_context TEXT,               -- LLM-extracted context from references (situations, signals)
    
    -- Generated Queries (by LLM)
    generated_queries JSONB DEFAULT '[]', -- Array of 3-5 semantic search queries
    
    -- Status & Results
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'generating_queries', 'searching', 'scoring', 'completed', 'failed')),
    results_count INTEGER DEFAULT 0,
    
    -- Metadata
    error_message TEXT,
    execution_time_seconds FLOAT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_prospecting_searches_org ON prospecting_searches(organization_id);
CREATE INDEX IF NOT EXISTS idx_prospecting_searches_user ON prospecting_searches(user_id);
CREATE INDEX IF NOT EXISTS idx_prospecting_searches_status ON prospecting_searches(status);
CREATE INDEX IF NOT EXISTS idx_prospecting_searches_created ON prospecting_searches(created_at DESC);

-- RLS
ALTER TABLE prospecting_searches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own org searches" ON prospecting_searches
    FOR SELECT USING (organization_id IN (
        SELECT organization_id FROM organization_members WHERE user_id = (SELECT auth.uid())
    ));

CREATE POLICY "Users can insert own searches" ON prospecting_searches
    FOR INSERT WITH CHECK (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can update own searches" ON prospecting_searches
    FOR UPDATE USING (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can delete own searches" ON prospecting_searches
    FOR DELETE USING (user_id = (SELECT auth.uid()));

CREATE POLICY "Service role can manage all searches" ON prospecting_searches
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================
-- 2. PROSPECTING RESULTS TABLE
-- ============================================================
-- Individual discovered prospects with fit scoring

CREATE TABLE IF NOT EXISTS prospecting_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_id UUID NOT NULL REFERENCES prospecting_searches(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Company Identity (normalized)
    company_name TEXT NOT NULL,
    company_name_normalized TEXT GENERATED ALWAYS AS (LOWER(TRIM(company_name))) STORED,
    website TEXT,
    linkedin_url TEXT,
    
    -- Derived Information
    inferred_sector TEXT,
    inferred_region TEXT,
    inferred_size TEXT,                   -- "startup", "SMB", "mid-market", "enterprise"
    
    -- Scoring (0-100)
    fit_score INTEGER DEFAULT 0 CHECK (fit_score >= 0 AND fit_score <= 100),
    proposition_fit INTEGER DEFAULT 0 CHECK (proposition_fit >= 0 AND proposition_fit <= 100),
    seller_fit INTEGER DEFAULT 0 CHECK (seller_fit >= 0 AND seller_fit <= 100),
    intent_score INTEGER DEFAULT 0 CHECK (intent_score >= 0 AND intent_score <= 100),
    recency_score INTEGER DEFAULT 0 CHECK (recency_score >= 0 AND recency_score <= 100),
    
    -- Why this prospect (AI-generated)
    fit_reason TEXT,                      -- 1-sentence explanation
    key_signal TEXT,                      -- Most important signal found
    
    -- Source & Evidence
    source_url TEXT NOT NULL,
    source_title TEXT,
    source_snippet TEXT,                  -- Relevant excerpt
    source_published_date DATE,
    
    -- Query that found this result
    matched_query TEXT,
    
    -- Link to prospect (if imported)
    prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
    imported_at TIMESTAMPTZ,
    
    -- Deduplication
    is_duplicate BOOLEAN DEFAULT false,
    duplicate_of UUID REFERENCES prospecting_results(id) ON DELETE SET NULL,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_prospecting_results_search ON prospecting_results(search_id);
CREATE INDEX IF NOT EXISTS idx_prospecting_results_org ON prospecting_results(organization_id);
CREATE INDEX IF NOT EXISTS idx_prospecting_results_score ON prospecting_results(search_id, fit_score DESC);
CREATE INDEX IF NOT EXISTS idx_prospecting_results_company ON prospecting_results(company_name_normalized);
CREATE INDEX IF NOT EXISTS idx_prospecting_results_prospect ON prospecting_results(prospect_id) WHERE prospect_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_prospecting_results_not_duplicate ON prospecting_results(search_id, is_duplicate) WHERE is_duplicate = false;

-- RLS
ALTER TABLE prospecting_results ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own org results" ON prospecting_results
    FOR SELECT USING (organization_id IN (
        SELECT organization_id FROM organization_members WHERE user_id = (SELECT auth.uid())
    ));

CREATE POLICY "Users can update own org results" ON prospecting_results
    FOR UPDATE USING (organization_id IN (
        SELECT organization_id FROM organization_members WHERE user_id = (SELECT auth.uid())
    ));

CREATE POLICY "Service role can manage all results" ON prospecting_results
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================
-- 3. TRIGGER FOR UPDATED_AT (if needed on search updates)
-- ============================================================

-- No updated_at on these tables - they are mostly write-once

-- ============================================================
-- END OF MIGRATION
-- ============================================================

