-- ============================================================
-- Migration: Prospect Notes
-- Date: 4 December 2025
-- SPEC: SPEC-034-Prospects-UX-Overhaul
-- 
-- Adds notes functionality to prospects for tracking
-- important information and observations.
-- ============================================================

-- 1. Create prospect_notes table
CREATE TABLE IF NOT EXISTS prospect_notes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  
  content TEXT NOT NULL,
  is_pinned BOOLEAN DEFAULT false,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Indexes
CREATE INDEX IF NOT EXISTS idx_prospect_notes_prospect ON prospect_notes(prospect_id);
CREATE INDEX IF NOT EXISTS idx_prospect_notes_org ON prospect_notes(organization_id);
CREATE INDEX IF NOT EXISTS idx_prospect_notes_user ON prospect_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_prospect_notes_pinned ON prospect_notes(prospect_id, is_pinned DESC, created_at DESC);

-- 3. Enable RLS
ALTER TABLE prospect_notes ENABLE ROW LEVEL SECURITY;

-- 4. RLS Policies
CREATE POLICY "Users can view notes in their organization"
  ON prospect_notes FOR SELECT
  USING (organization_id IN (SELECT organization_id FROM organization_members WHERE user_id = auth.uid()));

CREATE POLICY "Users can create notes in their organization"
  ON prospect_notes FOR INSERT
  WITH CHECK (organization_id IN (SELECT organization_id FROM organization_members WHERE user_id = auth.uid()));

CREATE POLICY "Users can update their own notes"
  ON prospect_notes FOR UPDATE
  USING (user_id = auth.uid());

CREATE POLICY "Users can delete their own notes"
  ON prospect_notes FOR DELETE
  USING (user_id = auth.uid());

-- 5. Updated_at trigger
CREATE TRIGGER update_prospect_notes_updated_at 
  BEFORE UPDATE ON prospect_notes
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- Verification
-- ============================================================
-- Run after migration:
-- SELECT COUNT(*) FROM prospect_notes; -- Should be 0
-- \d prospect_notes -- Check table structure

