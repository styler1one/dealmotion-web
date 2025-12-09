-- ============================================================
-- Migration: Deal Management & Prospect Hub
-- Version: 1.0
-- Date: 30 November 2025
-- 
-- IMPORTANT: This is NOT a CRM replacement!
-- - Deals are for GROUPING preps/followups, not pipeline management
-- - CRM fields (stage, value, probability) are for future sync only
-- - No manual entry of CRM-like data
-- ============================================================

-- ============================================================
-- 1. DEALS TABLE (Lightweight - for grouping only)
-- ============================================================
CREATE TABLE IF NOT EXISTS deals (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- User-entered fields (minimal!)
  name TEXT NOT NULL,                    -- e.g., "Enterprise License 2025"
  description TEXT,                       -- Optional context/notes
  is_active BOOLEAN DEFAULT true,         -- Simple: active or archived
  
  -- CRM Sync fields (read-only, populated by future CRM integration)
  -- These are EMPTY now, will be filled by Phase 13: CRM Integration
  crm_deal_id TEXT,                       -- External CRM ID (HubSpot, Salesforce, etc.)
  crm_source TEXT,                        -- 'hubspot', 'salesforce', 'pipedrive'
  crm_stage TEXT,                         -- Stage from CRM (display only)
  crm_value_cents BIGINT,                 -- Value from CRM (display only)
  crm_currency TEXT,                      -- Currency from CRM
  crm_probability INTEGER,                -- Probability from CRM (0-100)
  crm_expected_close DATE,                -- Expected close from CRM
  crm_owner TEXT,                         -- Owner name from CRM
  crm_synced_at TIMESTAMPTZ,              -- Last CRM sync timestamp
  
  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

-- Indexes for deals
CREATE INDEX IF NOT EXISTS idx_deals_prospect ON deals(prospect_id);
CREATE INDEX IF NOT EXISTS idx_deals_organization ON deals(organization_id);
CREATE INDEX IF NOT EXISTS idx_deals_active ON deals(organization_id, is_active);
CREATE INDEX IF NOT EXISTS idx_deals_crm ON deals(crm_deal_id) WHERE crm_deal_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_deals_created ON deals(organization_id, created_at DESC);

-- ============================================================
-- 2. MEETINGS TABLE (Links activities to a specific meeting)
-- ============================================================
CREATE TABLE IF NOT EXISTS meetings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  deal_id UUID REFERENCES deals(id) ON DELETE SET NULL,        -- Optional deal link
  prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- Meeting Info
  title TEXT NOT NULL,                   -- e.g., "Discovery Call with Jan"
  meeting_type TEXT,                     -- 'discovery', 'demo', 'negotiation', 'closing', 'review', 'other'
  
  -- Scheduling (optional)
  scheduled_date TIMESTAMPTZ,            -- When the meeting was/is scheduled
  actual_date TIMESTAMPTZ,               -- When it actually happened
  duration_minutes INTEGER,              -- Meeting duration
  location TEXT,                         -- "Zoom", "Teams", "On-site", URL
  
  -- Attendees (contact references)
  contact_ids UUID[] DEFAULT '{}',       -- Which contacts attended
  
  -- Linked DealMotion Items (reverse links - actual FKs are on the other tables)
  -- These are populated by triggers or views
  
  -- Notes
  notes TEXT,                            -- Pre or post meeting notes
  
  -- Status
  status TEXT DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no_show')),
  outcome TEXT CHECK (outcome IS NULL OR outcome IN ('positive', 'neutral', 'negative')),
  
  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

-- Indexes for meetings
CREATE INDEX IF NOT EXISTS idx_meetings_deal ON meetings(deal_id);
CREATE INDEX IF NOT EXISTS idx_meetings_prospect ON meetings(prospect_id);
CREATE INDEX IF NOT EXISTS idx_meetings_organization ON meetings(organization_id);
CREATE INDEX IF NOT EXISTS idx_meetings_scheduled ON meetings(scheduled_date);
CREATE INDEX IF NOT EXISTS idx_meetings_status ON meetings(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_meetings_created ON meetings(organization_id, created_at DESC);

-- ============================================================
-- 3. PROSPECT_ACTIVITIES TABLE (Timeline logging)
-- ============================================================
CREATE TABLE IF NOT EXISTS prospect_activities (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
  deal_id UUID REFERENCES deals(id) ON DELETE SET NULL,
  meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- Activity Info
  activity_type TEXT NOT NULL,           -- 'research', 'contact_added', 'prep', 'meeting', 'followup', 'deal_created', 'note'
  activity_id UUID,                       -- Reference to the actual item (research_id, prep_id, etc.)
  
  -- Display
  title TEXT NOT NULL,                   -- "Research completed"
  description TEXT,                      -- "Brief generated for Acme Corp"
  icon TEXT,                             -- Emoji or icon name for display
  
  -- Extra data (flexible)
  metadata JSONB DEFAULT '{}',           -- Additional context as needed
  
  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

-- Indexes for activities
CREATE INDEX IF NOT EXISTS idx_activities_prospect ON prospect_activities(prospect_id);
CREATE INDEX IF NOT EXISTS idx_activities_deal ON prospect_activities(deal_id);
CREATE INDEX IF NOT EXISTS idx_activities_meeting ON prospect_activities(meeting_id);
CREATE INDEX IF NOT EXISTS idx_activities_organization ON prospect_activities(organization_id);
CREATE INDEX IF NOT EXISTS idx_activities_created ON prospect_activities(prospect_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activities_type ON prospect_activities(activity_type);

-- ============================================================
-- 4. ADD COLUMNS TO EXISTING TABLES
-- ============================================================

-- Add deal_id and meeting_id to meeting_preps
ALTER TABLE meeting_preps 
  ADD COLUMN IF NOT EXISTS deal_id UUID REFERENCES deals(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_meeting_preps_deal ON meeting_preps(deal_id);
CREATE INDEX IF NOT EXISTS idx_meeting_preps_meeting ON meeting_preps(meeting_id);

-- Add deal_id and meeting_id to followups
ALTER TABLE followups 
  ADD COLUMN IF NOT EXISTS deal_id UUID REFERENCES deals(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_followups_deal ON followups(deal_id);
CREATE INDEX IF NOT EXISTS idx_followups_meeting ON followups(meeting_id);

-- ============================================================
-- 5. ROW LEVEL SECURITY POLICIES
-- ============================================================

-- Enable RLS
ALTER TABLE deals ENABLE ROW LEVEL SECURITY;
ALTER TABLE meetings ENABLE ROW LEVEL SECURITY;
ALTER TABLE prospect_activities ENABLE ROW LEVEL SECURITY;

-- DEALS policies
CREATE POLICY "Users can view deals in their org"
  ON deals FOR SELECT
  USING (organization_id IN (SELECT get_user_org_ids()));

CREATE POLICY "Users can insert deals in their org"
  ON deals FOR INSERT
  WITH CHECK (organization_id IN (SELECT get_user_org_ids()));

CREATE POLICY "Users can update deals in their org"
  ON deals FOR UPDATE
  USING (organization_id IN (SELECT get_user_org_ids()));

CREATE POLICY "Users can delete deals in their org"
  ON deals FOR DELETE
  USING (organization_id IN (SELECT get_user_org_ids()));

-- MEETINGS policies
CREATE POLICY "Users can view meetings in their org"
  ON meetings FOR SELECT
  USING (organization_id IN (SELECT get_user_org_ids()));

CREATE POLICY "Users can insert meetings in their org"
  ON meetings FOR INSERT
  WITH CHECK (organization_id IN (SELECT get_user_org_ids()));

CREATE POLICY "Users can update meetings in their org"
  ON meetings FOR UPDATE
  USING (organization_id IN (SELECT get_user_org_ids()));

CREATE POLICY "Users can delete meetings in their org"
  ON meetings FOR DELETE
  USING (organization_id IN (SELECT get_user_org_ids()));

-- PROSPECT_ACTIVITIES policies
CREATE POLICY "Users can view activities in their org"
  ON prospect_activities FOR SELECT
  USING (organization_id IN (SELECT get_user_org_ids()));

CREATE POLICY "Users can insert activities in their org"
  ON prospect_activities FOR INSERT
  WITH CHECK (organization_id IN (SELECT get_user_org_ids()));

-- Activities are generally not updated/deleted directly

-- ============================================================
-- 6. TRIGGERS
-- ============================================================

-- Update timestamps trigger for deals
CREATE TRIGGER set_updated_at_deals BEFORE UPDATE ON deals
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Update timestamps trigger for meetings
CREATE TRIGGER set_updated_at_meetings BEFORE UPDATE ON meetings
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Auto-log activity when deal is created
CREATE OR REPLACE FUNCTION log_deal_activity()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO prospect_activities (
    prospect_id, 
    deal_id, 
    organization_id, 
    activity_type, 
    activity_id,
    title, 
    description,
    icon,
    created_by
  ) VALUES (
    NEW.prospect_id,
    NEW.id,
    NEW.organization_id,
    'deal_created',
    NEW.id,
    'Deal created: ' || NEW.name,
    COALESCE(NEW.description, 'New deal started'),
    '🎯',
    NEW.created_by
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_deal_created
  AFTER INSERT ON deals
  FOR EACH ROW EXECUTE FUNCTION log_deal_activity();

-- Auto-log activity when meeting is created
CREATE OR REPLACE FUNCTION log_meeting_activity()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO prospect_activities (
    prospect_id, 
    deal_id,
    meeting_id,
    organization_id, 
    activity_type, 
    activity_id,
    title, 
    description,
    icon,
    created_by
  ) VALUES (
    NEW.prospect_id,
    NEW.deal_id,
    NEW.id,
    NEW.organization_id,
    'meeting',
    NEW.id,
    'Meeting: ' || NEW.title,
    COALESCE(NEW.meeting_type, 'Meeting') || CASE 
      WHEN NEW.scheduled_date IS NOT NULL THEN ' scheduled for ' || TO_CHAR(NEW.scheduled_date, 'DD Mon YYYY HH24:MI')
      ELSE ''
    END,
    '📅',
    NEW.created_by
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_meeting_created
  AFTER INSERT ON meetings
  FOR EACH ROW EXECUTE FUNCTION log_meeting_activity();

-- Auto-log activity when prep is completed
CREATE OR REPLACE FUNCTION log_prep_activity()
RETURNS TRIGGER AS $$
BEGIN
  -- Only log when status changes to 'completed'
  IF NEW.status = 'completed' AND (OLD.status IS NULL OR OLD.status != 'completed') THEN
    INSERT INTO prospect_activities (
      prospect_id, 
      deal_id,
      meeting_id,
      organization_id, 
      activity_type, 
      activity_id,
      title, 
      description,
      icon,
      created_by
    ) VALUES (
      NEW.prospect_id,
      NEW.deal_id,
      NEW.meeting_id,
      NEW.organization_id,
      'prep',
      NEW.id,
      'Meeting prep completed',
      COALESCE(NEW.meeting_type, 'Meeting') || ' preparation ready',
      '📋',
      NEW.user_id
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_prep_completed
  AFTER INSERT OR UPDATE ON meeting_preps
  FOR EACH ROW EXECUTE FUNCTION log_prep_activity();

-- Auto-log activity when followup is completed
CREATE OR REPLACE FUNCTION log_followup_activity()
RETURNS TRIGGER AS $$
BEGIN
  -- Only log when status changes to 'completed'
  IF NEW.status = 'completed' AND (OLD.status IS NULL OR OLD.status != 'completed') THEN
    INSERT INTO prospect_activities (
      prospect_id, 
      deal_id,
      meeting_id,
      organization_id, 
      activity_type, 
      activity_id,
      title, 
      description,
      icon,
      created_by
    ) VALUES (
      NEW.prospect_id,
      NEW.deal_id,
      NEW.meeting_id,
      NEW.organization_id,
      'followup',
      NEW.id,
      'Follow-up completed',
      COALESCE(NEW.meeting_subject, 'Meeting') || ' follow-up processed',
      '📝',
      NEW.user_id
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_followup_completed
  AFTER INSERT OR UPDATE ON followups
  FOR EACH ROW EXECUTE FUNCTION log_followup_activity();

-- Auto-log activity when research is completed
CREATE OR REPLACE FUNCTION log_research_activity()
RETURNS TRIGGER AS $$
BEGIN
  -- Only log when status changes to 'completed'
  IF NEW.status = 'completed' AND (OLD.status IS NULL OR OLD.status != 'completed') THEN
    INSERT INTO prospect_activities (
      prospect_id, 
      organization_id, 
      activity_type, 
      activity_id,
      title, 
      description,
      icon,
      created_by
    ) VALUES (
      NEW.prospect_id,
      NEW.organization_id,
      'research',
      NEW.id,
      'Research completed',
      'Research brief generated for ' || NEW.company_name,
      '🔍',
      NEW.user_id
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_research_completed
  AFTER INSERT OR UPDATE ON research_briefs
  FOR EACH ROW EXECUTE FUNCTION log_research_activity();

-- ============================================================
-- 7. HELPER FUNCTIONS
-- ============================================================

-- Get or create a default deal for a prospect (for migration)
CREATE OR REPLACE FUNCTION get_or_create_default_deal(
  p_prospect_id UUID,
  p_organization_id UUID,
  p_user_id UUID
) RETURNS UUID AS $$
DECLARE
  v_deal_id UUID;
  v_prospect_name TEXT;
BEGIN
  -- Check if any deal exists for this prospect
  SELECT id INTO v_deal_id
  FROM deals
  WHERE prospect_id = p_prospect_id
  ORDER BY created_at ASC
  LIMIT 1;
  
  -- Create default deal if none exists
  IF v_deal_id IS NULL THEN
    SELECT company_name INTO v_prospect_name FROM prospects WHERE id = p_prospect_id;
    
    INSERT INTO deals (prospect_id, organization_id, name, description, created_by)
    VALUES (
      p_prospect_id, 
      p_organization_id, 
      'Initial Opportunity',
      'Auto-created deal for ' || COALESCE(v_prospect_name, 'prospect'),
      p_user_id
    )
    RETURNING id INTO v_deal_id;
  END IF;
  
  RETURN v_deal_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- 8. VIEWS FOR EASY QUERYING
-- ============================================================

-- Prospect Hub summary view
CREATE OR REPLACE VIEW prospect_hub_summary AS
SELECT 
  p.id AS prospect_id,
  p.organization_id,
  p.company_name,
  p.status,
  p.created_at,
  p.last_activity_at,
  
  -- Counts
  (SELECT COUNT(*) FROM research_briefs rb WHERE rb.prospect_id = p.id AND rb.status = 'completed') AS research_count,
  (SELECT COUNT(*) FROM prospect_contacts pc WHERE pc.prospect_id = p.id) AS contact_count,
  (SELECT COUNT(*) FROM deals d WHERE d.prospect_id = p.id AND d.is_active = true) AS active_deal_count,
  (SELECT COUNT(*) FROM meetings m WHERE m.prospect_id = p.id) AS meeting_count,
  (SELECT COUNT(*) FROM meeting_preps mp WHERE mp.prospect_id = p.id AND mp.status = 'completed') AS prep_count,
  (SELECT COUNT(*) FROM followups f WHERE f.prospect_id = p.id AND f.status = 'completed') AS followup_count,
  
  -- Latest activity
  (
    SELECT jsonb_build_object(
      'type', pa.activity_type,
      'title', pa.title,
      'created_at', pa.created_at
    )
    FROM prospect_activities pa 
    WHERE pa.prospect_id = p.id 
    ORDER BY pa.created_at DESC 
    LIMIT 1
  ) AS latest_activity
  
FROM prospects p;

-- Deal summary view
CREATE OR REPLACE VIEW deal_summary AS
SELECT 
  d.id AS deal_id,
  d.prospect_id,
  d.organization_id,
  d.name,
  d.description,
  d.is_active,
  d.created_at,
  
  -- Prospect info
  p.company_name,
  
  -- Counts
  (SELECT COUNT(*) FROM meetings m WHERE m.deal_id = d.id) AS meeting_count,
  (SELECT COUNT(*) FROM meeting_preps mp WHERE mp.deal_id = d.id AND mp.status = 'completed') AS prep_count,
  (SELECT COUNT(*) FROM followups f WHERE f.deal_id = d.id AND f.status = 'completed') AS followup_count,
  
  -- Latest meeting
  (
    SELECT jsonb_build_object(
      'id', m.id,
      'title', m.title,
      'scheduled_date', m.scheduled_date,
      'status', m.status
    )
    FROM meetings m 
    WHERE m.deal_id = d.id 
    ORDER BY COALESCE(m.scheduled_date, m.created_at) DESC 
    LIMIT 1
  ) AS latest_meeting,
  
  -- CRM info (if synced)
  d.crm_deal_id IS NOT NULL AS is_crm_synced,
  d.crm_stage,
  d.crm_value_cents,
  d.crm_currency,
  d.crm_synced_at
  
FROM deals d
JOIN prospects p ON p.id = d.prospect_id;

-- ============================================================
-- DONE! Run this in Supabase SQL Editor
-- ============================================================
-- After running, the following is available:
-- 
-- Tables:
-- - deals (grouping for sales activities)
-- - meetings (individual meetings)
-- - prospect_activities (timeline)
--
-- New columns on existing tables:
-- - meeting_preps.deal_id, meeting_preps.meeting_id
-- - followups.deal_id, followups.meeting_id
--
-- Views:
-- - prospect_hub_summary (quick stats per prospect)
-- - deal_summary (quick stats per deal)
--
-- Activity logging is automatic via triggers.
-- ============================================================

