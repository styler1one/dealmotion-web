-- ============================================================
-- Migration: Add contact_ids to meeting_preps and followups
-- Version: 2.2
-- Date: 2024-11-30
-- 
-- Purpose: Link selected contacts to meeting preps and followups
-- so they can be displayed in the UI and used for AI context
-- ============================================================

-- ============================================================
-- 1. ADD contact_ids TO meeting_preps
-- ============================================================
ALTER TABLE meeting_preps 
ADD COLUMN IF NOT EXISTS contact_ids UUID[] DEFAULT '{}';

-- Index for looking up preps by contacts
CREATE INDEX IF NOT EXISTS idx_meeting_preps_contact_ids 
  ON meeting_preps USING GIN(contact_ids);

-- ============================================================
-- 2. ADD contact_ids TO followups
-- ============================================================
ALTER TABLE followups 
ADD COLUMN IF NOT EXISTS contact_ids UUID[] DEFAULT '{}';

-- Index for looking up followups by contacts
CREATE INDEX IF NOT EXISTS idx_followups_contact_ids 
  ON followups USING GIN(contact_ids);

-- ============================================================
-- DONE!
-- 
-- New columns:
-- - meeting_preps.contact_ids: UUID array of linked contacts
-- - followups.contact_ids: UUID array of linked contacts
-- ============================================================

