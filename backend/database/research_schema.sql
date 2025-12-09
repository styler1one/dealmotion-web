-- Research Agent Database Schema
-- Run this in Supabase SQL Editor

-- 1. Create research_briefs table
CREATE TABLE IF NOT EXISTS research_briefs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  company_name TEXT NOT NULL,
  company_linkedin_url TEXT,
  country TEXT,
  city TEXT,
  status TEXT NOT NULL CHECK (status IN ('pending', 'researching', 'completed', 'failed')),
  research_data JSONB DEFAULT '{}'::jsonb,
  brief_content TEXT,
  pdf_url TEXT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- 2. Create research_sources table
CREATE TABLE IF NOT EXISTS research_sources (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  research_id UUID NOT NULL REFERENCES research_briefs(id) ON DELETE CASCADE,
  source_type TEXT NOT NULL CHECK (source_type IN ('claude', 'gemini', 'kvk', 'premium')),
  source_name TEXT NOT NULL,
  data JSONB NOT NULL,
  fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Create indexes
CREATE INDEX IF NOT EXISTS idx_research_briefs_org ON research_briefs(organization_id);
CREATE INDEX IF NOT EXISTS idx_research_briefs_user ON research_briefs(user_id);
CREATE INDEX IF NOT EXISTS idx_research_briefs_status ON research_briefs(status);
CREATE INDEX IF NOT EXISTS idx_research_briefs_created ON research_briefs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_research_sources_research ON research_sources(research_id);

-- 4. Enable RLS
ALTER TABLE research_briefs ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_sources ENABLE ROW LEVEL SECURITY;

-- 5. Create RLS policies for research_briefs
CREATE POLICY "Users can view own org research"
  ON research_briefs FOR SELECT
  USING (
    organization_id IN (
      SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert own org research"
  ON research_briefs FOR INSERT
  WITH CHECK (
    organization_id IN (
      SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
    )
  );

CREATE POLICY "Users can update own org research"
  ON research_briefs FOR UPDATE
  USING (
    organization_id IN (
      SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
    )
  );

CREATE POLICY "Users can delete own org research"
  ON research_briefs FOR DELETE
  USING (
    organization_id IN (
      SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
    )
  );

-- 6. Create RLS policies for research_sources
CREATE POLICY "Users can view own org research sources"
  ON research_sources FOR SELECT
  USING (
    research_id IN (
      SELECT id FROM research_briefs WHERE organization_id IN (
        SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
      )
    )
  );

CREATE POLICY "Users can insert research sources"
  ON research_sources FOR INSERT
  WITH CHECK (
    research_id IN (
      SELECT id FROM research_briefs WHERE organization_id IN (
        SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
      )
    )
  );

-- 7. Create storage bucket for research PDFs (if not exists)
INSERT INTO storage.buckets (id, name, public)
VALUES ('research-pdfs', 'research-pdfs', false)
ON CONFLICT (id) DO NOTHING;

-- 8. Create storage policies
CREATE POLICY "Users can upload research PDFs"
  ON storage.objects FOR INSERT
  TO authenticated
  WITH CHECK (bucket_id = 'research-pdfs');

CREATE POLICY "Users can read research PDFs"
  ON storage.objects FOR SELECT
  TO authenticated
  USING (bucket_id = 'research-pdfs');

CREATE POLICY "Users can delete research PDFs"
  ON storage.objects FOR DELETE
  TO authenticated
  USING (bucket_id = 'research-pdfs');
