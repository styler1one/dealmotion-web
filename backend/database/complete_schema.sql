-- ============================================================
-- DealMotion Complete Database Schema
-- Version: 4.0
-- Last Updated: 15 December 2025
-- 
-- This file consolidates ALL migrations into a single schema.
-- Use this as reference documentation - DO NOT run on existing DB!
-- 
-- COUNTS:
-- - Tables: 50 (+4 autopilot tables)
-- - Functions: 43 (+1 autopilot trigger function)
-- - Triggers: 41 (+3 autopilot triggers)
-- - Indexes: 215 (+13 autopilot indexes)
-- 
-- Changes in 4.0:
-- - Added autopilot_proposals table (SPEC-045: DealMotion Autopilot)
-- - Added autopilot_settings table (user configuration)
-- - Added meeting_outcomes table (learning data)
-- - Added user_prep_preferences table (learned preferences)
-- - Added RLS policies for all autopilot tables
-- - Added unique constraint for duplicate proposal prevention
-- 
-- Changes in 3.9:
-- - Added scheduled_recordings table (AI Notetaker via Recall.ai)
-- - SPEC-043: AI Notetaker / Recall.ai Integration
-- 
-- Changes in 3.8:
-- - Added mobile_recordings table (for PWA/mobile app recordings)
-- - Added recordings storage bucket
-- - Added RLS policies for mobile_recordings
-- 
-- Changes in 3.7:
-- - Added calendar_connections table (OAuth tokens for Google/Microsoft)
-- - Added calendar_meetings table (synced meetings from external calendars)
-- - Added recording_integrations table (Fireflies/Zoom/Teams config)
-- - Added external_recordings table (imported recordings before processing)
-- - Added calendar_meeting_id and external_recording_id to followups table
-- - Added RLS policies for all new tables
-- - Added updated_at triggers for all new tables
-- - SPEC-038: Meetings & Calendar Integration
-- 
-- Changes in 3.6:
-- - Added admin_users table (role-based admin access)
-- - Added admin_audit_log table (action tracking)
-- - Added admin_alerts table (system alerts)
-- - Added admin_notes table (user notes)
-- - Added admin helper functions: is_admin, is_super_admin, get_admin_role
-- - Added dashboard functions: calculate_mrr, get_job_stats_24h, 
--   get_admin_dashboard_metrics, get_admin_usage_trends, get_user_health_data
-- - Added RLS policies for all admin tables
-- 
-- Changes in 3.5:
-- - Added flow_pack_products table (Pricing v3)
-- - Added flow_packs table (Pricing v3)
-- - Added get_flow_pack_balance function
-- - Added consume_flow_pack function
-- - Updated check_flow_limit return type to BOOLEAN
-- - Updated check_usage_limit return type to BOOLEAN
-- - Updated users table with full_name and updated_at columns
-- - Added RLS policies for flow_pack_products and flow_packs
-- - Added SET search_path = '' to all security definer functions
-- 
-- Changes in 3.4:
-- - Added missing functions: get_knowledge_base_stats, update_coach_updated_at,
--   update_followup_actions_updated_at, update_kb_file_processed_at,
--   update_updated_at_column, update_user_settings_updated_at
-- - Fixed function signatures to match database exactly
-- - Added all missing triggers (30 total)
-- 
-- Changes in 3.3:
-- - Updated get_style_guide_with_defaults with full derivation logic
-- - Updated check_usage_limit with flow redirect and all metrics
-- - Added storage policies for research-pdfs bucket
-- 
-- Changes in 3.1:
-- - Added all missing functions (23 total)
-- - Added all triggers (17 total)
-- - Added handle_new_user for auto-org creation
-- - Added activity logging functions
-- - Added profile completeness calculators
-- 
-- Changes in 3.0:
-- - Added user_settings table (i18n preferences)
-- - Added coach_daily_tips table (Luna caching)
-- - Added deals, meetings, prospect_activities tables
-- - Added billing v2 with flow-based pricing
-- - Added seller context fields (style_guide, etc.)
-- - Added i18n language fields to all content tables
-- - Updated RLS policies for performance
-- - Consolidated all indexes
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";  -- For embeddings

-- ============================================================
-- 1. ORGANIZATIONS (Multi-tenant container)
-- ============================================================
CREATE TABLE IF NOT EXISTS organizations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  slug TEXT UNIQUE,  -- For URL-friendly names
  owner_id UUID REFERENCES auth.users(id),  -- Organization owner (added for quick lookups)
  
  -- i18n (added in migration_i18n_languages)
  default_working_language TEXT DEFAULT 'en' 
    CHECK (default_working_language IN ('nl', 'en', 'de', 'fr', 'es', 'hi', 'ar')),
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);

-- ============================================================
-- 2. USERS (Sync from auth.users)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email VARCHAR NOT NULL,
  full_name VARCHAR,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 3. ORGANIZATION_MEMBERS (User <-> Org link)
-- ============================================================
CREATE TABLE IF NOT EXISTS organization_members (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
  
  -- i18n override (added in migration_i18n_languages)
  working_language_override TEXT 
    CHECK (working_language_override IS NULL OR working_language_override IN ('nl', 'en', 'de', 'fr', 'es', 'hi', 'ar')),
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(organization_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_org_members_user ON organization_members(user_id);
CREATE INDEX IF NOT EXISTS idx_org_members_org ON organization_members(organization_id);

-- ============================================================
-- 4. USER_SETTINGS (Per-user preferences)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  
  -- Language preferences
  app_language VARCHAR(5) DEFAULT 'en',      -- UI language
  output_language VARCHAR(5) DEFAULT 'en',   -- AI output language
  email_language VARCHAR(5) DEFAULT 'en',    -- Email generation language
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  CONSTRAINT unique_user_settings UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id);

-- ============================================================
-- 5. PROSPECTS (Central prospect entity)
-- ============================================================
CREATE TABLE IF NOT EXISTS prospects (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- Core fields
  company_name TEXT NOT NULL,
  company_name_normalized TEXT GENERATED ALWAYS AS (LOWER(TRIM(company_name))) STORED,
  
  -- Optional enrichment
  website TEXT,
  linkedin_url TEXT,
  industry TEXT,
  company_size TEXT,
  country TEXT,
  city TEXT,
  
  -- Contact info (primary contact - legacy, use prospect_contacts instead)
  contact_name TEXT,
  contact_email TEXT,
  contact_role TEXT,
  contact_linkedin TEXT,
  
  -- Status tracking
  status TEXT DEFAULT 'new' CHECK (status IN ('new', 'researching', 'qualified', 'meeting_scheduled', 'proposal_sent', 'won', 'lost', 'inactive')),
  
  -- i18n (added in migration_i18n_languages)
  preferred_language TEXT DEFAULT 'en'
    CHECK (preferred_language IN ('nl', 'en', 'de', 'fr', 'es', 'hi', 'ar')),
  
  -- Metadata
  notes TEXT,
  tags TEXT[],
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_activity_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(organization_id, company_name_normalized)
);

CREATE INDEX IF NOT EXISTS idx_prospects_org ON prospects(organization_id);
CREATE INDEX IF NOT EXISTS idx_prospects_name_normalized ON prospects(company_name_normalized);
CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_prospects_last_activity ON prospects(organization_id, last_activity_at DESC);
CREATE INDEX IF NOT EXISTS idx_prospects_language ON prospects(organization_id, preferred_language);
CREATE INDEX IF NOT EXISTS idx_prospects_name_search ON prospects USING gin(to_tsvector('simple', company_name));

-- ============================================================
-- 6. PROSPECT_CONTACTS (Multiple contacts per prospect)
-- ============================================================
CREATE TABLE IF NOT EXISTS prospect_contacts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- Basic Contact Info
  name TEXT NOT NULL,
  role TEXT,
  email TEXT,
  phone TEXT,
  linkedin_url TEXT,
  
  -- LinkedIn Analysis Data
  linkedin_headline TEXT,
  linkedin_summary TEXT,
  linkedin_experience JSONB,          -- [{company, title, duration}]
  linkedin_activity_level TEXT,       -- 'active', 'moderate', 'passive'
  linkedin_post_themes TEXT[],
  
  -- AI-Generated Insights (contact understanding)
  communication_style TEXT,           -- 'formal', 'informal', 'technical', 'strategic'
  probable_drivers TEXT,              -- Motivations
  decision_authority TEXT,            -- 'decision_maker', 'influencer', 'gatekeeper', 'user'
  urgency_signals TEXT,
  
  -- Contact Analysis
  profile_brief TEXT,                 -- Full markdown analysis
  pain_points_for_role TEXT,
  
  -- Legacy action fields (now generated in Prep instead)
  conversation_approach TEXT,         -- DEPRECATED: Generated in prep_generator
  opening_suggestions TEXT[],         -- DEPRECATED: Generated in prep_generator
  questions_to_ask TEXT[],            -- DEPRECATED: Generated in prep_generator
  topics_to_avoid TEXT[],             -- DEPRECATED: Generated in prep_generator
  
  -- Relationship Tracking
  is_primary BOOLEAN DEFAULT false,
  relationship_strength TEXT,         -- 'new', 'warm', 'strong'
  last_contact_date TIMESTAMPTZ,
  notes TEXT,
  
  -- Meta
  analyzed_at TIMESTAMPTZ,
  analysis_source TEXT,               -- 'linkedin', 'manual', 'crm_import'
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prospect_contacts_prospect ON prospect_contacts(prospect_id);
CREATE INDEX IF NOT EXISTS idx_prospect_contacts_org ON prospect_contacts(organization_id);
CREATE INDEX IF NOT EXISTS idx_prospect_contacts_primary ON prospect_contacts(prospect_id, is_primary) WHERE is_primary = true;
CREATE INDEX IF NOT EXISTS idx_prospect_contacts_name ON prospect_contacts(organization_id, LOWER(name));

-- ============================================================
-- 6b. PROSPECT_NOTES (Notes for prospects)
-- ============================================================
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

CREATE INDEX IF NOT EXISTS idx_prospect_notes_prospect ON prospect_notes(prospect_id);
CREATE INDEX IF NOT EXISTS idx_prospect_notes_org ON prospect_notes(organization_id);
CREATE INDEX IF NOT EXISTS idx_prospect_notes_user ON prospect_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_prospect_notes_pinned ON prospect_notes(prospect_id, is_pinned DESC, created_at DESC);

-- ============================================================
-- 7. SALES_PROFILES (Per user sales profile)
-- ============================================================
CREATE TABLE IF NOT EXISTS sales_profiles (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  
  -- Profile data
  full_name TEXT,
  role TEXT,
  experience_years INTEGER,
  sales_methodology TEXT,
  communication_style TEXT,
  strengths TEXT[],
  areas_to_improve TEXT[],
  target_industries TEXT[],
  target_regions TEXT[],
  target_company_sizes TEXT[],
  quarterly_goals TEXT,
  preferred_meeting_types TEXT[],
  
  -- AI-generated content
  sales_narrative TEXT,
  ai_summary TEXT,
  methodology_description TEXT,
  style_notes TEXT,
  
  -- Interview responses (JSONB for flexibility)
  interview_responses JSONB,
  
  -- Personalization settings (JSONB)
  personalization_settings JSONB,
  
  -- Style Guide (added in migration_seller_context)
  style_guide JSONB,                  -- {tone, formality, emoji_usage, signoff, writing_length, ...}
  email_tone TEXT,                    -- 'direct', 'warm', 'formal', 'casual'
  uses_emoji BOOLEAN DEFAULT FALSE,
  email_signoff TEXT,
  writing_length_preference TEXT,     -- 'concise', 'detailed'
  
  -- Completeness tracking
  profile_completeness INTEGER DEFAULT 0,
  version INTEGER DEFAULT 1,
  last_reviewed_at TIMESTAMPTZ,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(organization_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_sales_profiles_user ON sales_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_sales_profiles_org ON sales_profiles(organization_id);
CREATE INDEX IF NOT EXISTS idx_sales_profiles_style_guide ON sales_profiles USING GIN (style_guide);

-- ============================================================
-- 8. COMPANY_PROFILES (Per org company profile - SELLER's company)
-- ============================================================
CREATE TABLE IF NOT EXISTS company_profiles (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- Company info
  company_name TEXT,
  industry TEXT,
  website TEXT,
  
  -- Products (JSONB array of {name, description, benefits, target_audience})
  products JSONB DEFAULT '[]'::jsonb,
  
  -- Value propositions
  core_value_props TEXT[],
  differentiators TEXT[],
  
  -- ICP - Ideal Customer Profile (JSONB object)
  -- Structure: {industries: [], company_sizes: [], pain_points: [], decision_makers: []}
  ideal_customer_profile JSONB DEFAULT '{}'::jsonb,
  
  -- Case studies (JSONB array)
  case_studies JSONB DEFAULT '[]'::jsonb,
  
  -- AI-generated content
  company_narrative TEXT,
  ai_summary TEXT,
  
  -- Completeness tracking
  profile_completeness INTEGER DEFAULT 0,
  version INTEGER DEFAULT 1,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(organization_id)
);

CREATE INDEX IF NOT EXISTS idx_company_profiles_org ON company_profiles(organization_id);

-- ============================================================
-- 9. PROFILE_VERSIONS (Version history)
-- ============================================================
CREATE TABLE IF NOT EXISTS profile_versions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  profile_type TEXT NOT NULL CHECK (profile_type IN ('sales', 'company')),
  profile_id UUID NOT NULL,
  version INTEGER NOT NULL,
  data JSONB NOT NULL,
  changed_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  change_summary TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_profile_versions_profile ON profile_versions(profile_type, profile_id);

-- ============================================================
-- 10. RESEARCH_BRIEFS (Prospect research)
-- ============================================================
CREATE TABLE IF NOT EXISTS research_briefs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  
  -- Link to prospect (preferred)
  prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
  
  -- Link to contact (optional)
  contact_id UUID REFERENCES prospect_contacts(id),
  
  -- Legacy fields (kept for backwards compatibility)
  company_name TEXT NOT NULL,
  company_linkedin_url TEXT,
  country TEXT,
  city TEXT,
  
  -- Status
  status TEXT NOT NULL CHECK (status IN ('pending', 'researching', 'completed', 'failed')),
  
  -- i18n (added in migration_i18n_languages)
  language TEXT DEFAULT 'en',
  
  -- Research data
  research_data JSONB DEFAULT '{}'::jsonb,
  brief_content TEXT,
  pdf_url TEXT,
  
  -- Error tracking
  error_message TEXT,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_research_briefs_org ON research_briefs(organization_id);
CREATE INDEX IF NOT EXISTS idx_research_briefs_user ON research_briefs(user_id);
CREATE INDEX IF NOT EXISTS idx_research_briefs_prospect ON research_briefs(prospect_id);
CREATE INDEX IF NOT EXISTS idx_research_briefs_contact ON research_briefs(contact_id) WHERE contact_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_research_briefs_status ON research_briefs(status);
CREATE INDEX IF NOT EXISTS idx_research_briefs_created ON research_briefs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_research_briefs_org_status ON research_briefs(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_research_briefs_language ON research_briefs(organization_id, language);

-- ============================================================
-- 11. RESEARCH_SOURCES (Research data sources)
-- ============================================================
CREATE TABLE IF NOT EXISTS research_sources (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  research_id UUID NOT NULL REFERENCES research_briefs(id) ON DELETE CASCADE,
  source_type TEXT NOT NULL CHECK (source_type IN ('claude', 'gemini', 'kvk', 'premium', 'web')),
  source_name TEXT NOT NULL,
  data JSONB NOT NULL,
  fetched_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_research_sources_research ON research_sources(research_id);

-- ============================================================
-- 12. DEALS (Sales opportunities - for grouping activities)
-- ============================================================
CREATE TABLE IF NOT EXISTS deals (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- User-entered fields
  name TEXT NOT NULL,
  description TEXT,
  is_active BOOLEAN DEFAULT true,
  
  -- CRM Sync fields (populated by future CRM integration)
  crm_deal_id TEXT,
  crm_source TEXT,                    -- 'hubspot', 'salesforce', 'pipedrive'
  crm_stage TEXT,
  crm_value_cents BIGINT,
  crm_currency TEXT,
  crm_probability INTEGER,            -- 0-100
  crm_expected_close DATE,
  crm_owner TEXT,
  crm_synced_at TIMESTAMPTZ,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_deals_prospect ON deals(prospect_id);
CREATE INDEX IF NOT EXISTS idx_deals_organization ON deals(organization_id);
CREATE INDEX IF NOT EXISTS idx_deals_active ON deals(organization_id, is_active);
CREATE INDEX IF NOT EXISTS idx_deals_crm ON deals(crm_deal_id) WHERE crm_deal_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_deals_created ON deals(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deals_created_by ON deals(created_by);

-- ============================================================
-- 13. MEETINGS (Individual meetings)
-- ============================================================
CREATE TABLE IF NOT EXISTS meetings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  deal_id UUID REFERENCES deals(id) ON DELETE SET NULL,
  prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- Meeting Info
  title TEXT NOT NULL,
  meeting_type TEXT,                  -- 'discovery', 'demo', 'negotiation', 'closing', 'review', 'other'
  
  -- Scheduling
  scheduled_date TIMESTAMPTZ,
  actual_date TIMESTAMPTZ,
  duration_minutes INTEGER,
  location TEXT,
  
  -- Attendees
  contact_ids UUID[] DEFAULT '{}',
  
  -- Notes
  notes TEXT,
  
  -- Status
  status TEXT DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no_show')),
  outcome TEXT CHECK (outcome IS NULL OR outcome IN ('positive', 'neutral', 'negative')),
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_meetings_deal ON meetings(deal_id);
CREATE INDEX IF NOT EXISTS idx_meetings_prospect ON meetings(prospect_id);
CREATE INDEX IF NOT EXISTS idx_meetings_organization ON meetings(organization_id);
CREATE INDEX IF NOT EXISTS idx_meetings_scheduled ON meetings(scheduled_date);
CREATE INDEX IF NOT EXISTS idx_meetings_status ON meetings(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_meetings_created ON meetings(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_meetings_created_by ON meetings(created_by);

-- ============================================================
-- 14. MEETING_PREPS (Meeting preparations)
-- ============================================================
CREATE TABLE IF NOT EXISTS meeting_preps (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  
  -- Links
  prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
  research_brief_id UUID REFERENCES research_briefs(id) ON DELETE SET NULL,
  deal_id UUID REFERENCES deals(id) ON DELETE SET NULL,
  meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL,
  
  -- Contact links (added in migration_contact_links)
  contact_ids UUID[] DEFAULT '{}',
  
  -- Legacy field
  prospect_company_name TEXT,
  
  -- Meeting info
  meeting_type TEXT,
  meeting_date TIMESTAMPTZ,
  custom_notes TEXT,
  
  -- i18n (added in migration_i18n_languages)
  language TEXT DEFAULT 'en',
  
  -- Generated content
  brief_content TEXT,
  
  -- Status
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'generating', 'completed', 'failed')),
  error_message TEXT,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_meeting_preps_org ON meeting_preps(organization_id);
CREATE INDEX IF NOT EXISTS idx_meeting_preps_user ON meeting_preps(user_id);
CREATE INDEX IF NOT EXISTS idx_meeting_preps_prospect ON meeting_preps(prospect_id);
CREATE INDEX IF NOT EXISTS idx_meeting_preps_research ON meeting_preps(research_brief_id);
CREATE INDEX IF NOT EXISTS idx_meeting_preps_deal ON meeting_preps(deal_id);
CREATE INDEX IF NOT EXISTS idx_meeting_preps_meeting ON meeting_preps(meeting_id);
CREATE INDEX IF NOT EXISTS idx_meeting_preps_contact_ids ON meeting_preps USING GIN(contact_ids);
CREATE INDEX IF NOT EXISTS idx_meeting_preps_org_status ON meeting_preps(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_meeting_preps_created ON meeting_preps(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_meeting_preps_language ON meeting_preps(organization_id, language);

-- ============================================================
-- 15. FOLLOWUPS (Post-meeting follow-ups)
-- ============================================================
CREATE TABLE IF NOT EXISTS followups (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  
  -- Links
  prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
  meeting_prep_id UUID REFERENCES meeting_preps(id) ON DELETE SET NULL,
  deal_id UUID REFERENCES deals(id) ON DELETE SET NULL,
  meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL,
  
  -- Calendar/Recording links (SPEC-038)
  calendar_meeting_id UUID REFERENCES calendar_meetings(id) ON DELETE SET NULL,
  external_recording_id UUID REFERENCES external_recordings(id) ON DELETE SET NULL,
  
  -- Contact links (added in migration_contact_links)
  contact_ids UUID[] DEFAULT '{}',
  
  -- Legacy field
  prospect_company_name TEXT,
  
  -- Meeting info
  meeting_date DATE,
  meeting_subject TEXT,
  
  -- Audio/transcript
  audio_url TEXT,
  audio_filename TEXT,
  audio_size_bytes INTEGER,
  audio_duration_seconds INTEGER,
  
  -- Transcription
  transcription_text TEXT,
  transcription_segments JSONB DEFAULT '[]'::jsonb,
  speaker_count INTEGER DEFAULT 0,
  
  -- Generated summary
  executive_summary TEXT,
  full_summary_content TEXT,          -- Added in migration_enhanced_followup
  key_points TEXT[] DEFAULT '{}',
  concerns TEXT[] DEFAULT '{}',
  decisions TEXT[] DEFAULT '{}',
  next_steps TEXT[] DEFAULT '{}',
  action_items JSONB DEFAULT '[]'::jsonb,
  
  -- Commercial insights (added in migration_enhanced_followup)
  include_coaching BOOLEAN DEFAULT false,
  commercial_signals JSONB,           -- BANT, cross-sell, upsell, deal risks
  observations JSONB,                 -- Doubts, unspoken needs, opportunities
  coaching_feedback JSONB,            -- Sales coaching analysis
  
  -- Email draft
  email_draft TEXT,
  email_tone TEXT DEFAULT 'professional',
  
  -- i18n (added in migration_i18n_languages)
  language TEXT DEFAULT 'en',
  email_language TEXT DEFAULT 'en',
  
  -- Status
  status TEXT NOT NULL DEFAULT 'uploading' CHECK (status IN ('uploading', 'transcribing', 'summarizing', 'completed', 'failed')),
  error_message TEXT,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_followups_org ON followups(organization_id);
CREATE INDEX IF NOT EXISTS idx_followups_user ON followups(user_id);
CREATE INDEX IF NOT EXISTS idx_followups_prospect ON followups(prospect_id);
CREATE INDEX IF NOT EXISTS idx_followups_prep ON followups(meeting_prep_id);
CREATE INDEX IF NOT EXISTS idx_followups_deal ON followups(deal_id);
CREATE INDEX IF NOT EXISTS idx_followups_meeting ON followups(meeting_id);
CREATE INDEX IF NOT EXISTS idx_followups_contact_ids ON followups USING GIN(contact_ids);
CREATE INDEX IF NOT EXISTS idx_followups_org_status ON followups(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_followups_created ON followups(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_followups_language ON followups(organization_id, language);
CREATE INDEX IF NOT EXISTS idx_followups_include_coaching ON followups(include_coaching) WHERE include_coaching = true;

-- ============================================================
-- 16. FOLLOWUP_ACTIONS (Generated actions from follow-ups)
-- ============================================================
CREATE TABLE IF NOT EXISTS followup_actions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  followup_id UUID NOT NULL REFERENCES followups(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  
  -- Action details
  action_type TEXT NOT NULL,          -- 'share_email', 'customer_report', 'internal_report', 'action_items', 'sales_coaching'
  title TEXT,
  content TEXT,                       -- Generated content (markdown)
  
  -- Status
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'generating', 'completed', 'failed')),
  error_message TEXT,
  
  -- Metadata
  metadata JSONB DEFAULT '{}'::jsonb,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_followup_actions_followup ON followup_actions(followup_id);
CREATE INDEX IF NOT EXISTS idx_followup_actions_org ON followup_actions(organization_id);
CREATE INDEX IF NOT EXISTS idx_followup_actions_type ON followup_actions(action_type);

-- ============================================================
-- 17. PROSPECT_ACTIVITIES (Timeline logging)
-- ============================================================
CREATE TABLE IF NOT EXISTS prospect_activities (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
  deal_id UUID REFERENCES deals(id) ON DELETE SET NULL,
  meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- Activity Info
  activity_type TEXT NOT NULL,        -- 'research', 'contact_added', 'prep', 'meeting', 'followup', 'deal_created', 'note'
  activity_id UUID,
  
  -- Display
  title TEXT NOT NULL,
  description TEXT,
  icon TEXT,
  
  -- Extra data
  metadata JSONB DEFAULT '{}',
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_activities_prospect ON prospect_activities(prospect_id);
CREATE INDEX IF NOT EXISTS idx_activities_deal ON prospect_activities(deal_id);
CREATE INDEX IF NOT EXISTS idx_activities_meeting ON prospect_activities(meeting_id);
CREATE INDEX IF NOT EXISTS idx_activities_organization ON prospect_activities(organization_id);
CREATE INDEX IF NOT EXISTS idx_activities_created ON prospect_activities(prospect_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activities_type ON prospect_activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_prospect_activities_created_by ON prospect_activities(created_by);

-- ============================================================
-- 18. KNOWLEDGE_BASE_FILES (Uploaded documents)
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_base_files (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE SET NULL,
  
  -- File info
  filename TEXT NOT NULL,
  file_size INTEGER,
  file_type TEXT,
  storage_path TEXT NOT NULL,
  
  -- Processing
  status TEXT NOT NULL DEFAULT 'uploading' CHECK (status IN ('uploading', 'processing', 'completed', 'failed')),
  chunk_count INTEGER DEFAULT 0,
  error_message TEXT,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_kb_files_org ON knowledge_base_files(organization_id);
CREATE INDEX IF NOT EXISTS idx_kb_files_status ON knowledge_base_files(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_kb_files_created ON knowledge_base_files(organization_id, created_at DESC);

-- ============================================================
-- 19. KNOWLEDGE_BASE_CHUNKS (Document chunks with embeddings)
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_base_chunks (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  file_id UUID NOT NULL REFERENCES knowledge_base_files(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- Chunk data
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  
  -- Vector embedding (1536 dimensions for OpenAI/Voyage)
  embedding vector(1536),
  
  -- Metadata
  metadata JSONB DEFAULT '{}'::jsonb,
  
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_file ON knowledge_base_chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_org ON knowledge_base_chunks(organization_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding ON knowledge_base_chunks 
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- 20. SUBSCRIPTION_PLANS (Static Configuration)
-- ============================================================
CREATE TABLE IF NOT EXISTS subscription_plans (
  id TEXT PRIMARY KEY,                -- 'free', 'light_solo', 'unlimited_solo', 'enterprise'
  name TEXT NOT NULL,
  description TEXT,
  price_cents INTEGER,                -- Price in cents (0, 995, 2995, NULL)
  original_price_cents INTEGER,       -- Original price for strikethrough (added in billing_v2)
  billing_interval TEXT,              -- 'month', 'year', NULL
  stripe_price_id TEXT,               -- Stripe Price ID
  features JSONB NOT NULL DEFAULT '{}',
  is_active BOOLEAN DEFAULT true,
  display_order INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert v4 plans (Pricing v4 - January 2026 - Early Bird Pricing)
-- Free: Test & Experience (trial)
-- Pro: €99 regular → €75 early bird, AI Notetaker INCLUDED
-- Pro+: €149 regular → €125 early bird, AI Notetaker INCLUDED
-- Enterprise: Teams with CRM integrations
INSERT INTO subscription_plans (id, name, description, price_cents, original_price_cents, billing_interval, features, display_order, is_active) VALUES
('free', 'Free', 'Test & experience DealMotion', 0, NULL, NULL, '{
  "flow_limit": 2,
  "user_limit": 1,
  "ai_notetaker": false,
  "knowledge_base": true,
  "transcription": true,
  "crm_integration": false,
  "team_sharing": false,
  "priority_support": false
}'::jsonb, 1, true),
('pro_monthly', 'Pro', 'Stop wasting hours on research & prep', 7500, 9900, 'month', '{
  "flow_limit": -1,
  "user_limit": 1,
  "ai_notetaker": true,
  "knowledge_base": true,
  "transcription": true,
  "crm_integration": false,
  "team_sharing": false,
  "priority_support": true
}'::jsonb, 2, true),
('pro_yearly', 'Pro', 'Stop wasting hours on research & prep', 76500, 100800, 'year', '{
  "flow_limit": -1,
  "user_limit": 1,
  "ai_notetaker": true,
  "knowledge_base": true,
  "transcription": true,
  "crm_integration": false,
  "team_sharing": false,
  "priority_support": true
}'::jsonb, 3, true),
('pro_plus_monthly', 'Pro+', 'Never take notes again — AI does it for you', 12500, 14900, 'month', '{
  "flow_limit": -1,
  "user_limit": 1,
  "ai_notetaker": true,
  "knowledge_base": true,
  "transcription": true,
  "crm_integration": false,
  "team_sharing": false,
  "priority_support": true
}'::jsonb, 4, true),
('pro_plus_yearly', 'Pro+', 'Never take notes again — AI does it for you', 127500, 152400, 'year', '{
  "flow_limit": -1,
  "user_limit": 1,
  "ai_notetaker": true,
  "knowledge_base": true,
  "transcription": true,
  "crm_integration": false,
  "team_sharing": false,
  "priority_support": true
}'::jsonb, 5, true),
('enterprise', 'Enterprise', 'For teams with CRM integrations', NULL, NULL, NULL, '{
  "flow_limit": -1,
  "user_limit": -1,
  "ai_notetaker": true,
  "knowledge_base": true,
  "transcription": true,
  "crm_integration": true,
  "crm_providers": ["dynamics", "salesforce", "hubspot", "pipedrive", "zoho"],
  "team_sharing": true,
  "priority_support": true,
  "sso": true,
  "dedicated_support": true
}'::jsonb, 6, true)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 21. ORGANIZATION_SUBSCRIPTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS organization_subscriptions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  plan_id TEXT NOT NULL REFERENCES subscription_plans(id) DEFAULT 'free',
  status TEXT NOT NULL DEFAULT 'active',  -- 'trialing', 'active', 'past_due', 'canceled', 'suspended'
  
  -- Stripe references
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT UNIQUE,
  
  -- Billing cycle
  current_period_start TIMESTAMPTZ,
  current_period_end TIMESTAMPTZ,
  cancel_at_period_end BOOLEAN DEFAULT false,
  canceled_at TIMESTAMPTZ,
  
  -- Trial
  trial_start TIMESTAMPTZ,
  trial_end TIMESTAMPTZ,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(organization_id)
);

CREATE INDEX IF NOT EXISTS idx_org_subs_stripe_customer ON organization_subscriptions(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_org_subs_stripe_subscription ON organization_subscriptions(stripe_subscription_id);
CREATE INDEX IF NOT EXISTS idx_org_subs_status ON organization_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_org_subs_plan ON organization_subscriptions(plan_id);

-- ============================================================
-- 22. USAGE_RECORDS (Per Billing Period)
-- ============================================================
CREATE TABLE IF NOT EXISTS usage_records (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  period_start TIMESTAMPTZ NOT NULL,
  period_end TIMESTAMPTZ NOT NULL,
  
  -- Usage counters
  flow_count INTEGER DEFAULT 0,       -- Added in billing_v2 (primary metric)
  research_count INTEGER DEFAULT 0,
  preparation_count INTEGER DEFAULT 0,
  followup_count INTEGER DEFAULT 0,
  transcription_seconds INTEGER DEFAULT 0,
  kb_document_count INTEGER DEFAULT 0,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(organization_id, period_start)
);

CREATE INDEX IF NOT EXISTS idx_usage_org_period ON usage_records(organization_id, period_start, period_end);

-- ============================================================
-- 23. FLOW_PACK_PRODUCTS (Available flow pack options)
-- ============================================================
CREATE TABLE IF NOT EXISTS flow_pack_products (
  id TEXT PRIMARY KEY,                  -- 'pack_5', 'pack_10', etc.
  name TEXT NOT NULL,
  flows INTEGER NOT NULL,
  price_cents INTEGER NOT NULL,
  stripe_price_id TEXT,
  is_active BOOLEAN DEFAULT true,
  display_order INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default flow pack products
INSERT INTO flow_pack_products (id, name, flows, price_cents, display_order, is_active) VALUES
('pack_5', 'Flow Pack 5', 5, 995, 1, true)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 24. FLOW_PACKS (Purchased flow packs per organization)
-- ============================================================
CREATE TABLE IF NOT EXISTS flow_packs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  flows_purchased INTEGER NOT NULL,
  flows_remaining INTEGER NOT NULL,
  price_cents INTEGER NOT NULL,
  stripe_payment_intent_id TEXT,
  stripe_checkout_session_id TEXT,
  status TEXT NOT NULL DEFAULT 'active',  -- 'active', 'depleted', 'expired', 'refunded'
  purchased_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ,                 -- Optional expiration
  depleted_at TIMESTAMPTZ,                -- When all flows were used
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flow_packs_org ON flow_packs(organization_id);
CREATE INDEX IF NOT EXISTS idx_flow_packs_status ON flow_packs(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_flow_packs_active ON flow_packs(organization_id) WHERE status = 'active' AND flows_remaining > 0;

-- ============================================================
-- 25. PAYMENT_HISTORY
-- ============================================================
CREATE TABLE IF NOT EXISTS payment_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- Stripe references
  stripe_invoice_id TEXT UNIQUE,
  stripe_payment_intent_id TEXT,
  stripe_charge_id TEXT,
  
  -- Payment details
  amount_cents INTEGER NOT NULL,
  currency TEXT DEFAULT 'eur',
  status TEXT NOT NULL,               -- 'paid', 'failed', 'refunded', 'pending'
  
  -- Invoice
  invoice_pdf_url TEXT,
  invoice_number TEXT,
  
  paid_at TIMESTAMPTZ,
  failed_at TIMESTAMPTZ,
  refunded_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payment_history_org ON payment_history(organization_id, created_at DESC);

-- ============================================================
-- 24. STRIPE_WEBHOOK_EVENTS (Idempotency)
-- ============================================================
CREATE TABLE IF NOT EXISTS stripe_webhook_events (
  id TEXT PRIMARY KEY,                -- Stripe event ID (evt_...)
  event_type TEXT NOT NULL,
  processed_at TIMESTAMPTZ DEFAULT NOW(),
  payload JSONB
);

-- ============================================================
-- 25. COACH_DAILY_TIPS (Luna AI cache)
-- ============================================================
CREATE TABLE IF NOT EXISTS coach_daily_tips (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  tip_date DATE NOT NULL DEFAULT CURRENT_DATE,
  tip_data JSONB NOT NULL,
  -- tip_data: {id, category, title, content, icon, is_personalized}
  is_personalized BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(user_id, tip_date)
);

CREATE INDEX IF NOT EXISTS idx_coach_daily_tips_user_date ON coach_daily_tips(user_id, tip_date);
CREATE INDEX IF NOT EXISTS idx_coach_daily_tips_created ON coach_daily_tips(created_at);

-- ============================================================
-- 26. COACH_BEHAVIOR_EVENTS (User activity tracking for Luna)
-- ============================================================
CREATE TABLE IF NOT EXISTS coach_behavior_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,            -- 'tip_shown', 'action_taken', 'page_view', etc.
  event_data JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_coach_behavior_events_user ON coach_behavior_events(user_id);
CREATE INDEX IF NOT EXISTS idx_coach_behavior_events_org ON coach_behavior_events(organization_id);
CREATE INDEX IF NOT EXISTS idx_coach_behavior_events_type ON coach_behavior_events(event_type);
CREATE INDEX IF NOT EXISTS idx_coach_behavior_events_created ON coach_behavior_events(user_id, created_at);

-- ============================================================
-- 27. COACH_USER_PATTERNS (Learned user behavior patterns)
-- ============================================================
CREATE TABLE IF NOT EXISTS coach_user_patterns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  pattern_type TEXT NOT NULL,          -- 'work_hours', 'step_timing', 'dismiss_pattern', etc.
  pattern_data JSONB NOT NULL,
  confidence FLOAT DEFAULT 0.5,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(user_id, pattern_type)
);

CREATE INDEX IF NOT EXISTS idx_coach_user_patterns_user ON coach_user_patterns(user_id);
CREATE INDEX IF NOT EXISTS idx_coach_user_patterns_org ON coach_user_patterns(organization_id);

-- ============================================================
-- 28. COACH_SUGGESTIONS (Suggestion tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS coach_suggestions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  suggestion_type TEXT NOT NULL,       -- Suggestion category
  suggestion_data JSONB,
  action_taken TEXT,                   -- NULL, 'accepted', 'dismissed', 'deferred'
  created_at TIMESTAMPTZ DEFAULT NOW(),
  acted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_coach_suggestions_user ON coach_suggestions(user_id);
CREATE INDEX IF NOT EXISTS idx_coach_suggestions_org ON coach_suggestions(organization_id);
CREATE INDEX IF NOT EXISTS idx_coach_suggestions_type ON coach_suggestions(suggestion_type);

-- ============================================================
-- 29. COACH_SUCCESS_PATTERNS (Organization-wide success patterns)
-- ============================================================
CREATE TABLE IF NOT EXISTS coach_success_patterns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  pattern_type TEXT NOT NULL,          -- Insight type
  pattern_data JSONB NOT NULL,
  sample_size INTEGER DEFAULT 0,
  confidence FLOAT DEFAULT 0.5,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_coach_success_patterns_org ON coach_success_patterns(organization_id);
CREATE INDEX IF NOT EXISTS idx_coach_success_patterns_type ON coach_success_patterns(pattern_type);

-- ============================================================
-- 30. COACH_SETTINGS (Per-user coach preferences)
-- ============================================================
CREATE TABLE IF NOT EXISTS coach_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  settings JSONB DEFAULT '{}',         -- {notification_frequency, preferred_focus_areas, etc.}
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_coach_settings_user ON coach_settings(user_id);

-- ============================================================
-- LEGACY/FUTURE TABLES (referenced in indexes, not in code)
-- ============================================================
-- Note: These tables exist in the database but are not actively used.
-- They may be for future features or legacy functionality.

-- 31. PRODUCTS (Future: Product catalog)
CREATE TABLE IF NOT EXISTS products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  features JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_org ON products(org_id);

-- 32. ICPS (Future: Ideal Customer Profiles - detailed)
CREATE TABLE IF NOT EXISTS icps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  product_id UUID REFERENCES products(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  criteria JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_icps_org ON icps(org_id);
CREATE INDEX IF NOT EXISTS idx_icps_product ON icps(product_id);

-- 33. PERSONAS (Future: Buyer personas)
CREATE TABLE IF NOT EXISTS personas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  icp_id UUID REFERENCES icps(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  role TEXT,
  pain_points TEXT[],
  goals TEXT[],
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_personas_org ON personas(org_id);
CREATE INDEX IF NOT EXISTS idx_personas_icp ON personas(icp_id);

-- ============================================================
-- STORAGE BUCKETS
-- ============================================================

INSERT INTO storage.buckets (id, name, public) VALUES
('knowledge-base-files', 'knowledge-base-files', false),
('followup-audio', 'followup-audio', false),
('research-pdfs', 'research-pdfs', false)
ON CONFLICT (id) DO NOTHING;

-- Storage policies for research PDFs
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

-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Get user's organization IDs
CREATE OR REPLACE FUNCTION get_user_org_ids()
RETURNS SETOF UUID AS $$
  SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
$$ LANGUAGE SQL SECURITY DEFINER SET search_path = '';

-- Get or create prospect
CREATE OR REPLACE FUNCTION get_or_create_prospect(
  p_organization_id UUID,
  p_company_name TEXT
) RETURNS UUID AS $$
DECLARE
  v_prospect_id UUID;
  v_normalized_name TEXT;
BEGIN
  v_normalized_name := LOWER(TRIM(p_company_name));
  
  SELECT id INTO v_prospect_id
  FROM prospects
  WHERE organization_id = p_organization_id
    AND company_name_normalized = v_normalized_name;
  
  IF v_prospect_id IS NULL THEN
    INSERT INTO prospects (organization_id, company_name)
    VALUES (p_organization_id, p_company_name)
    RETURNING id INTO v_prospect_id;
  END IF;
  
  RETURN v_prospect_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Get or create usage record (with explicit period)
CREATE OR REPLACE FUNCTION get_or_create_usage_record(
  p_organization_id UUID,
  p_period_start TIMESTAMPTZ,
  p_period_end TIMESTAMPTZ
)
RETURNS UUID AS $$
DECLARE
  v_usage_id UUID;
BEGIN
  SELECT id INTO v_usage_id
  FROM usage_records
  WHERE organization_id = p_organization_id
    AND period_start = p_period_start;
  
  IF v_usage_id IS NULL THEN
    INSERT INTO usage_records (organization_id, period_start, period_end)
    VALUES (p_organization_id, p_period_start, p_period_end)
    RETURNING id INTO v_usage_id;
  END IF;
  
  RETURN v_usage_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Check flow limit (returns BOOLEAN - true if allowed)
CREATE OR REPLACE FUNCTION check_flow_limit(p_organization_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
  v_plan_id TEXT;
  v_features JSONB;
  v_limit INTEGER;
  v_current INTEGER;
  v_pack_balance INTEGER;
BEGIN
  SELECT plan_id INTO v_plan_id
  FROM public.organization_subscriptions
  WHERE organization_id = p_organization_id;
  
  IF v_plan_id IS NULL THEN
    v_plan_id := 'free';
  END IF;
  
  SELECT features INTO v_features
  FROM public.subscription_plans
  WHERE id = v_plan_id;
  
  v_limit := COALESCE((v_features->>'flow_limit')::INTEGER, 2);
  
  -- Unlimited plan
  IF v_limit = -1 THEN
    RETURN TRUE;
  END IF;
  
  -- Check monthly usage
  SELECT COALESCE(flow_count, 0) INTO v_current
  FROM public.usage_records
  WHERE organization_id = p_organization_id
    AND period_start = date_trunc('month', NOW());
  
  -- Within monthly limit
  IF COALESCE(v_current, 0) < v_limit THEN
    RETURN TRUE;
  END IF;
  
  -- Check flow pack balance
  v_pack_balance := public.get_flow_pack_balance(p_organization_id);
  
  RETURN v_pack_balance > 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Get flow pack balance for organization
CREATE OR REPLACE FUNCTION get_flow_pack_balance(p_organization_id UUID)
RETURNS INTEGER AS $$
BEGIN
  RETURN COALESCE(
    (SELECT SUM(flows_remaining)
     FROM public.flow_packs
     WHERE organization_id = p_organization_id
       AND status = 'active'
       AND flows_remaining > 0
       AND (expires_at IS NULL OR expires_at > NOW())
    ), 0
  )::INTEGER;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Consume flow from pack (returns TRUE if consumed)
CREATE OR REPLACE FUNCTION consume_flow_pack(p_organization_id UUID, p_amount INTEGER DEFAULT 1)
RETURNS BOOLEAN AS $$
DECLARE
  v_pack_id UUID;
  v_remaining INTEGER;
BEGIN
  -- Find oldest active pack with remaining flows
  SELECT id, flows_remaining INTO v_pack_id, v_remaining
  FROM public.flow_packs
  WHERE organization_id = p_organization_id
    AND status = 'active'
    AND flows_remaining > 0
    AND (expires_at IS NULL OR expires_at > NOW())
  ORDER BY purchased_at ASC
  LIMIT 1
  FOR UPDATE;
  
  IF v_pack_id IS NULL THEN
    RETURN FALSE;
  END IF;
  
  -- Consume the flow
  UPDATE public.flow_packs
  SET 
    flows_remaining = flows_remaining - p_amount,
    depleted_at = CASE WHEN flows_remaining - p_amount <= 0 THEN NOW() ELSE NULL END,
    status = CASE WHEN flows_remaining - p_amount <= 0 THEN 'depleted' ELSE 'active' END,
    updated_at = NOW()
  WHERE id = v_pack_id;
  
  RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Increment flow count (tries flow pack first, then monthly quota)
CREATE OR REPLACE FUNCTION increment_flow(p_organization_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
  v_usage_id UUID;
  v_pack_consumed BOOLEAN;
BEGIN
  -- Try to consume from flow pack first
  v_pack_consumed := public.consume_flow_pack(p_organization_id, 1);
  
  IF v_pack_consumed THEN
    -- Flow consumed from pack, also increment research_count for tracking
    v_usage_id := public.get_or_create_usage_record(
      p_organization_id,
      date_trunc('month', NOW()),
      date_trunc('month', NOW()) + INTERVAL '1 month'
    );
    
    UPDATE public.usage_records 
    SET research_count = research_count + 1,
        updated_at = NOW() 
    WHERE id = v_usage_id;
    
    RETURN TRUE;
  END IF;
  
  -- No pack available, use monthly quota
  v_usage_id := public.get_or_create_usage_record(
    p_organization_id,
    date_trunc('month', NOW()),
    date_trunc('month', NOW()) + INTERVAL '1 month'
  );
  
  UPDATE public.usage_records 
  SET flow_count = flow_count + 1,
      research_count = research_count + 1,
      updated_at = NOW() 
  WHERE id = v_usage_id;
  
  RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Update prospect activity trigger function
CREATE OR REPLACE FUNCTION update_prospect_activity()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.prospect_id IS NOT NULL THEN
    UPDATE prospects SET last_activity_at = NOW() WHERE id = NEW.prospect_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Handle new user (auto-create organization)
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
  new_org_id UUID;
  free_plan_id TEXT := 'free';
BEGIN
  -- Create personal organization
  INSERT INTO public.organizations (name, slug)
  VALUES (
    'Personal - ' || COALESCE(NEW.email, NEW.id::TEXT),
    'personal-' || NEW.id::TEXT
  )
  RETURNING id INTO new_org_id;
  
  -- Add user as owner
  INSERT INTO public.organization_members (organization_id, user_id, role)
  VALUES (new_org_id, NEW.id, 'owner');
  
  -- Create free subscription
  INSERT INTO public.organization_subscriptions (organization_id, plan_id, status)
  VALUES (new_org_id, free_plan_id, 'active');
  
  -- Create initial usage record
  INSERT INTO public.usage_records (organization_id, period_start, period_end)
  VALUES (new_org_id, date_trunc('month', NOW()), date_trunc('month', NOW()) + INTERVAL '1 month');
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Get style guide with defaults (derives from profile if not set)
CREATE OR REPLACE FUNCTION get_style_guide_with_defaults(profile_row sales_profiles)
RETURNS JSONB AS $$
DECLARE
  result JSONB;
BEGIN
  -- If style_guide exists, return it
  IF profile_row.style_guide IS NOT NULL THEN
    RETURN profile_row.style_guide;
  END IF;
  
  -- Otherwise, derive from existing fields
  result := jsonb_build_object(
    'tone', COALESCE(
      CASE 
        WHEN profile_row.communication_style ILIKE '%direct%' THEN 'direct'
        WHEN profile_row.communication_style ILIKE '%warm%' OR profile_row.communication_style ILIKE '%relationship%' THEN 'warm'
        WHEN profile_row.communication_style ILIKE '%formal%' THEN 'formal'
        WHEN profile_row.communication_style ILIKE '%casual%' OR profile_row.communication_style ILIKE '%informal%' THEN 'casual'
        ELSE 'professional'
      END,
      'professional'
    ),
    'formality', 'professional',
    'language_style', 'business',
    'persuasion_style', COALESCE(
      CASE 
        WHEN profile_row.sales_methodology ILIKE '%challenger%' THEN 'logic'
        WHEN profile_row.sales_methodology ILIKE '%story%' OR profile_row.sales_methodology ILIKE '%narrative%' THEN 'story'
        WHEN profile_row.sales_methodology ILIKE '%reference%' OR profile_row.sales_methodology ILIKE '%social%' THEN 'reference'
        ELSE 'logic'
      END,
      'logic'
    ),
    'emoji_usage', COALESCE(profile_row.uses_emoji, false),
    'signoff', COALESCE(profile_row.email_signoff, 'Best regards'),
    'writing_length', COALESCE(profile_row.writing_length_preference, 'concise'),
    'generated_at', NULL,
    'confidence_score', 0.5
  );
  
  RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Cleanup old coach tips
CREATE OR REPLACE FUNCTION cleanup_old_coach_tips()
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM coach_daily_tips
  WHERE tip_date < CURRENT_DATE - INTERVAL '7 days';
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Calculate sales profile completeness
CREATE OR REPLACE FUNCTION calculate_sales_profile_completeness(profile_data JSONB)
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

-- Calculate company profile completeness
CREATE OR REPLACE FUNCTION calculate_company_profile_completeness(profile_data JSONB)
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

-- Get or create default deal for a prospect
CREATE OR REPLACE FUNCTION get_or_create_default_deal(
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
  WHERE prospect_id = p_prospect_id
    AND is_active = true
  ORDER BY created_at DESC
  LIMIT 1;
  
  IF v_deal_id IS NULL THEN
    INSERT INTO public.deals (prospect_id, organization_id, name)
    VALUES (p_prospect_id, p_organization_id, 'Deal - ' || COALESCE(p_prospect_name, 'Unknown'))
    RETURNING id INTO v_deal_id;
  END IF;
  
  RETURN v_deal_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Get or create subscription for organization
CREATE OR REPLACE FUNCTION get_or_create_subscription(p_organization_id UUID)
RETURNS UUID AS $$
DECLARE
  v_subscription_id UUID;
BEGIN
  SELECT id INTO v_subscription_id
  FROM organization_subscriptions
  WHERE organization_id = p_organization_id;
  
  IF v_subscription_id IS NULL THEN
    INSERT INTO organization_subscriptions (organization_id, plan_id, status)
    VALUES (p_organization_id, 'free', 'active')
    RETURNING id INTO v_subscription_id;
  END IF;
  
  RETURN v_subscription_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Increment usage (supports different usage types)
CREATE OR REPLACE FUNCTION increment_usage(
  p_organization_id UUID,
  p_usage_type TEXT,
  p_amount INTEGER DEFAULT 1
)
RETURNS VOID AS $$
DECLARE
  v_period_start TIMESTAMPTZ;
  v_period_end TIMESTAMPTZ;
  v_usage_id UUID;
BEGIN
  v_period_start := date_trunc('month', NOW());
  v_period_end := v_period_start + INTERVAL '1 month';
  v_usage_id := get_or_create_usage_record(p_organization_id, v_period_start, v_period_end);
  
  IF p_usage_type = 'research' THEN
    UPDATE usage_records SET research_count = research_count + p_amount, updated_at = NOW() WHERE id = v_usage_id;
  ELSIF p_usage_type = 'preparation' THEN
    UPDATE usage_records SET preparation_count = preparation_count + p_amount, updated_at = NOW() WHERE id = v_usage_id;
  ELSIF p_usage_type = 'followup' THEN
    UPDATE usage_records SET followup_count = followup_count + p_amount, updated_at = NOW() WHERE id = v_usage_id;
  ELSIF p_usage_type = 'transcription' THEN
    UPDATE usage_records SET transcription_seconds = transcription_seconds + p_amount, updated_at = NOW() WHERE id = v_usage_id;
  ELSIF p_usage_type = 'kb_document' THEN
    UPDATE usage_records SET kb_document_count = kb_document_count + p_amount, updated_at = NOW() WHERE id = v_usage_id;
  END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Check usage limit (returns BOOLEAN - true if allowed)
CREATE OR REPLACE FUNCTION check_usage_limit(
  p_organization_id UUID,
  p_metric TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
  v_plan_id TEXT;
  v_features JSONB;
  v_limit INTEGER;
  v_current INTEGER;
  v_limit_key TEXT;
BEGIN
  -- For 'flow' metric, use dedicated function
  IF p_metric = 'flow' THEN
    RETURN public.check_flow_limit(p_organization_id);
  END IF;

  -- Get organization's plan
  SELECT plan_id INTO v_plan_id
  FROM public.organization_subscriptions
  WHERE organization_id = p_organization_id;
  
  IF v_plan_id IS NULL THEN v_plan_id := 'free'; END IF;
  
  SELECT features INTO v_features
  FROM public.subscription_plans WHERE id = v_plan_id;
  
  -- Build limit key (e.g., 'research' -> 'research_limit')
  v_limit_key := p_metric || '_limit';
  v_limit := (v_features->>v_limit_key)::INTEGER;
  
  -- If limit not found, check flow_limit for backwards compatibility
  IF v_limit IS NULL THEN
    IF p_metric IN ('research', 'preparation', 'followup') THEN
      RETURN public.check_flow_limit(p_organization_id);
    END IF;
    -- Otherwise unlimited
    RETURN TRUE;
  END IF;
  
  IF v_limit = -1 THEN
    RETURN TRUE;
  END IF;
  
  SELECT COALESCE(
    CASE p_metric
      WHEN 'research' THEN research_count
      WHEN 'preparation' THEN preparation_count
      WHEN 'followup' THEN followup_count
      WHEN 'flow' THEN flow_count
      WHEN 'transcription_seconds' THEN transcription_seconds
      WHEN 'kb_document' THEN kb_document_count
      ELSE 0
    END, 0
  ) INTO v_current
  FROM public.usage_records
  WHERE organization_id = p_organization_id
    AND period_start = date_trunc('month', NOW());
  
  RETURN COALESCE(v_current, 0) < v_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Is organization member helper
CREATE OR REPLACE FUNCTION is_org_member(org_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM organization_members
    WHERE organization_id = org_id AND user_id = auth.uid()
  );
END;
$$ LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '';

-- Get knowledge base stats
CREATE OR REPLACE FUNCTION get_knowledge_base_stats(p_organization_id UUID)
RETURNS TABLE (
  total_files INTEGER,
  total_chunks INTEGER,
  total_size_bytes BIGINT
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    COUNT(DISTINCT f.id)::INTEGER as total_files,
    COUNT(c.id)::INTEGER as total_chunks,
    COALESCE(SUM(f.file_size), 0)::BIGINT as total_size_bytes
  FROM knowledge_base_files f
  LEFT JOIN knowledge_base_chunks c ON c.file_id = f.id
  WHERE f.organization_id = p_organization_id
    AND f.status = 'completed';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Update updated_at column (alternative naming)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Update coach tables updated_at
CREATE OR REPLACE FUNCTION update_coach_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Update followup_actions updated_at
CREATE OR REPLACE FUNCTION update_followup_actions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Update KB file processed_at when status changes to completed
CREATE OR REPLACE FUNCTION update_kb_file_processed_at()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
    NEW.processed_at = NOW();
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Update user_settings updated_at
CREATE OR REPLACE FUNCTION update_user_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Update prospect_contacts updated_at
CREATE OR REPLACE FUNCTION update_prospect_contacts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Get or create prospect contact
CREATE OR REPLACE FUNCTION get_or_create_prospect_contact(
  p_prospect_id UUID,
  p_organization_id UUID,
  p_name TEXT,
  p_email TEXT DEFAULT NULL,
  p_linkedin_url TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
  v_contact_id UUID;
BEGIN
  SELECT id INTO v_contact_id
  FROM prospect_contacts
  WHERE prospect_id = p_prospect_id
    AND LOWER(name) = LOWER(p_name)
  LIMIT 1;
  
  IF v_contact_id IS NULL THEN
    INSERT INTO prospect_contacts (prospect_id, organization_id, name, email, linkedin_url, is_primary)
    VALUES (
      p_prospect_id, p_organization_id, p_name, p_email, p_linkedin_url,
      NOT EXISTS(SELECT 1 FROM prospect_contacts WHERE prospect_id = p_prospect_id)
    )
    RETURNING id INTO v_contact_id;
  END IF;
  
  RETURN v_contact_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- Ensure single primary contact per prospect
CREATE OR REPLACE FUNCTION ensure_single_primary_contact()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.is_primary = true THEN
    UPDATE prospect_contacts
    SET is_primary = false
    WHERE prospect_id = NEW.prospect_id
      AND id != NEW.id
      AND is_primary = true;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Activity logging functions
CREATE OR REPLACE FUNCTION log_deal_activity()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO prospect_activities (prospect_id, deal_id, organization_id, activity_type, title, description, metadata, created_by)
  VALUES (
    NEW.prospect_id, NEW.id, NEW.organization_id, 'deal_created',
    'Deal Created: ' || NEW.name, NEW.description,
    jsonb_build_object('deal_id', NEW.id, 'is_active', NEW.is_active),
    NEW.created_by
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

CREATE OR REPLACE FUNCTION log_meeting_activity()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO prospect_activities (prospect_id, deal_id, meeting_id, organization_id, activity_type, title, description, metadata, created_by)
  VALUES (
    NEW.prospect_id, NEW.deal_id, NEW.id, NEW.organization_id, 'meeting',
    'Meeting: ' || NEW.title, NEW.notes,
    jsonb_build_object('meeting_id', NEW.id, 'meeting_type', NEW.meeting_type, 'status', NEW.status),
    NEW.created_by
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

CREATE OR REPLACE FUNCTION log_prep_activity()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO prospect_activities (prospect_id, organization_id, activity_type, title, description, metadata)
  SELECT 
    NEW.prospect_id, NEW.organization_id, 'prep_created', 'Meeting Preparation',
    'Status: ' || NEW.status,
    jsonb_build_object('prep_id', NEW.id, 'status', NEW.status)
  WHERE NEW.prospect_id IS NOT NULL AND NEW.organization_id IS NOT NULL;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

CREATE OR REPLACE FUNCTION log_followup_activity()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO prospect_activities (prospect_id, organization_id, activity_type, title, description, metadata)
  SELECT 
    NEW.prospect_id, NEW.organization_id, 'followup_created', 'Follow-up Brief',
    'Status: ' || NEW.status,
    jsonb_build_object('followup_id', NEW.id, 'status', NEW.status)
  WHERE NEW.prospect_id IS NOT NULL AND NEW.organization_id IS NOT NULL;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

CREATE OR REPLACE FUNCTION log_research_activity()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO prospect_activities (prospect_id, organization_id, activity_type, title, description, metadata)
  SELECT 
    NEW.prospect_id, NEW.organization_id, 'research_completed', 'Research Brief',
    'Status: ' || NEW.status,
    jsonb_build_object('research_id', NEW.id, 'status', NEW.status)
  WHERE NEW.prospect_id IS NOT NULL AND NEW.organization_id IS NOT NULL;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- ============================================================
-- TRIGGERS (30 total - matching database)
-- ============================================================

-- Auto-create organization for new users
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Updated_at triggers (using update_updated_at)
CREATE TRIGGER set_updated_at_deals BEFORE UPDATE ON deals
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at_meetings BEFORE UPDATE ON meetings
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_subscription_plans_updated_at BEFORE UPDATE ON subscription_plans
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_organization_subscriptions_updated_at BEFORE UPDATE ON organization_subscriptions
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_usage_records_updated_at BEFORE UPDATE ON usage_records
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Updated_at triggers (using update_updated_at_column)
CREATE TRIGGER update_company_profiles_updated_at BEFORE UPDATE ON company_profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_sales_profiles_updated_at BEFORE UPDATE ON sales_profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Updated_at triggers (using specific functions)
CREATE TRIGGER trigger_user_settings_updated_at BEFORE UPDATE ON user_settings
  FOR EACH ROW EXECUTE FUNCTION update_user_settings_updated_at();
CREATE TRIGGER trigger_prospect_contacts_updated_at BEFORE UPDATE ON prospect_contacts
  FOR EACH ROW EXECUTE FUNCTION update_prospect_contacts_updated_at();
CREATE TRIGGER trigger_prospect_notes_updated_at BEFORE UPDATE ON prospect_notes
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trigger_followup_actions_updated_at BEFORE UPDATE ON followup_actions
  FOR EACH ROW EXECUTE FUNCTION update_followup_actions_updated_at();

-- Coach table triggers
CREATE TRIGGER coach_settings_updated_at BEFORE UPDATE ON coach_settings
  FOR EACH ROW EXECUTE FUNCTION update_coach_updated_at();
CREATE TRIGGER coach_success_patterns_updated_at BEFORE UPDATE ON coach_success_patterns
  FOR EACH ROW EXECUTE FUNCTION update_coach_updated_at();
CREATE TRIGGER coach_patterns_updated_at BEFORE UPDATE ON coach_user_patterns
  FOR EACH ROW EXECUTE FUNCTION update_coach_updated_at();

-- Knowledge base file processing
CREATE TRIGGER kb_file_status_change BEFORE UPDATE ON knowledge_base_files
  FOR EACH ROW EXECUTE FUNCTION update_kb_file_processed_at();

-- Primary contact enforcement
CREATE TRIGGER trigger_single_primary_contact
  BEFORE INSERT OR UPDATE ON prospect_contacts
  FOR EACH ROW EXECUTE FUNCTION ensure_single_primary_contact();

-- Activity logging triggers
CREATE TRIGGER log_deal_created
  AFTER INSERT ON deals
  FOR EACH ROW EXECUTE FUNCTION log_deal_activity();
CREATE TRIGGER log_meeting_created
  AFTER INSERT ON meetings
  FOR EACH ROW EXECUTE FUNCTION log_meeting_activity();
CREATE TRIGGER log_prep_completed
  AFTER INSERT OR UPDATE ON meeting_preps
  FOR EACH ROW EXECUTE FUNCTION log_prep_activity();
CREATE TRIGGER log_followup_completed
  AFTER INSERT OR UPDATE ON followups
  FOR EACH ROW EXECUTE FUNCTION log_followup_activity();
CREATE TRIGGER log_research_completed
  AFTER INSERT OR UPDATE ON research_briefs
  FOR EACH ROW EXECUTE FUNCTION log_research_activity();

-- Prospect activity tracking
CREATE TRIGGER update_prospect_activity_research 
  AFTER INSERT OR UPDATE ON research_briefs
  FOR EACH ROW EXECUTE FUNCTION update_prospect_activity();
CREATE TRIGGER update_prospect_activity_prep 
  AFTER INSERT OR UPDATE ON meeting_preps
  FOR EACH ROW EXECUTE FUNCTION update_prospect_activity();
CREATE TRIGGER update_prospect_activity_followup 
  AFTER INSERT OR UPDATE ON followups
  FOR EACH ROW EXECUTE FUNCTION update_prospect_activity();

-- ============================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================
-- Note: See migration_fix_rls_performance.sql for optimized policies
-- All tables have RLS enabled with org-based access control

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE prospects ENABLE ROW LEVEL SECURITY;
ALTER TABLE prospect_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE prospect_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE profile_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_briefs ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE deals ENABLE ROW LEVEL SECURITY;
ALTER TABLE meetings ENABLE ROW LEVEL SECURITY;
ALTER TABLE meeting_preps ENABLE ROW LEVEL SECURITY;
ALTER TABLE followups ENABLE ROW LEVEL SECURITY;
ALTER TABLE followup_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE prospect_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_base_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_base_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE stripe_webhook_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE coach_daily_tips ENABLE ROW LEVEL SECURITY;
ALTER TABLE coach_behavior_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE coach_user_patterns ENABLE ROW LEVEL SECURITY;
ALTER TABLE coach_suggestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE coach_success_patterns ENABLE ROW LEVEL SECURITY;
ALTER TABLE coach_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE icps ENABLE ROW LEVEL SECURITY;
ALTER TABLE personas ENABLE ROW LEVEL SECURITY;
ALTER TABLE flow_pack_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE flow_packs ENABLE ROW LEVEL SECURITY;

-- RLS Policies for flow_pack_products (read-only for authenticated users)
CREATE POLICY "flow_pack_products_select" ON flow_pack_products
  FOR SELECT TO authenticated
  USING (is_active = true);

-- RLS Policies for flow_packs (org-based access)
CREATE POLICY "flow_packs_select" ON flow_packs
  FOR SELECT TO authenticated
  USING (organization_id IN (
    SELECT om.organization_id FROM organization_members om 
    WHERE om.user_id = (SELECT auth.uid())
  ));

-- ============================================================
-- VIEWS
-- ============================================================

CREATE OR REPLACE VIEW prospect_hub_summary 
WITH (security_invoker = true)
AS
SELECT 
  p.id AS prospect_id,
  p.organization_id,
  p.company_name,
  p.status,
  p.created_at,
  p.last_activity_at,
  (SELECT COUNT(*) FROM research_briefs rb WHERE rb.prospect_id = p.id AND rb.status = 'completed') AS research_count,
  (SELECT COUNT(*) FROM prospect_contacts pc WHERE pc.prospect_id = p.id) AS contact_count,
  (SELECT COUNT(*) FROM deals d WHERE d.prospect_id = p.id AND d.is_active = true) AS active_deal_count,
  (SELECT COUNT(*) FROM meetings m WHERE m.prospect_id = p.id) AS meeting_count,
  (SELECT COUNT(*) FROM meeting_preps mp WHERE mp.prospect_id = p.id AND mp.status = 'completed') AS prep_count,
  (SELECT COUNT(*) FROM followups f WHERE f.prospect_id = p.id AND f.status = 'completed') AS followup_count
FROM prospects p;

CREATE OR REPLACE VIEW deal_summary 
WITH (security_invoker = true)
AS
SELECT 
  d.id AS deal_id,
  d.prospect_id,
  d.organization_id,
  d.name,
  d.description,
  d.is_active,
  d.created_at,
  p.company_name,
  (SELECT COUNT(*) FROM meetings m WHERE m.deal_id = d.id) AS meeting_count,
  (SELECT COUNT(*) FROM meeting_preps mp WHERE mp.deal_id = d.id AND mp.status = 'completed') AS prep_count,
  (SELECT COUNT(*) FROM followups f WHERE f.deal_id = d.id AND f.status = 'completed') AS followup_count,
  d.crm_deal_id IS NOT NULL AS is_crm_synced,
  d.crm_stage,
  d.crm_value_cents,
  d.crm_currency,
  d.crm_synced_at
FROM deals d
JOIN prospects p ON p.id = d.prospect_id;

-- ============================================================
-- ADMIN PANEL TABLES (v3.6)
-- ============================================================

-- Admin Users - Role-based admin access
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'support' 
        CHECK (role IN ('super_admin', 'admin', 'support', 'viewer')),
    is_active BOOLEAN DEFAULT true,
    last_admin_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    UNIQUE(user_id)
);

-- Admin Audit Log - Track all admin actions
CREATE TABLE IF NOT EXISTS admin_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_user_id UUID NOT NULL REFERENCES admin_users(id),
    action TEXT NOT NULL,
    target_type TEXT,
    target_id UUID,
    target_identifier TEXT,
    details JSONB,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Admin Alerts - System-generated alerts
CREATE TABLE IF NOT EXISTS admin_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_type TEXT NOT NULL 
        CHECK (alert_type IN ('error', 'warning', 'info', 'payment_failed', 'usage_limit', 'security')),
    severity TEXT DEFAULT 'medium' 
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    target_type TEXT,                -- 'user' or 'organization'
    target_id UUID,                  -- UUID of user or organization
    target_name TEXT,                -- Display name for quick reference
    title TEXT NOT NULL,
    description TEXT,                -- Alert details (was: message)
    context JSONB,                   -- Additional context data (was: metadata)
    status TEXT DEFAULT 'active' 
        CHECK (status IN ('active', 'acknowledged', 'resolved')),
    acknowledged_by UUID REFERENCES admin_users(id),
    acknowledged_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES admin_users(id),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Admin Notes - Notes on users and organizations
CREATE TABLE IF NOT EXISTS admin_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    target_type TEXT NOT NULL,           -- 'user' or 'organization'
    target_id UUID NOT NULL,             -- UUID of user or organization
    target_identifier TEXT,              -- Display identifier (email or org name)
    content TEXT NOT NULL,               -- Note content (was: note)
    is_pinned BOOLEAN DEFAULT false,
    admin_user_id UUID NOT NULL REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for admin tables
CREATE INDEX IF NOT EXISTS idx_admin_users_user_id ON admin_users(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_admin_user ON admin_audit_log(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created_at ON admin_audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_alerts_status ON admin_alerts(status);
CREATE INDEX IF NOT EXISTS idx_admin_alerts_created_at ON admin_alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_notes_target ON admin_notes(target_type, target_id);

-- RLS Policies for admin tables
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_notes ENABLE ROW LEVEL SECURITY;

-- Admin helper functions
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_is_admin BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM public.admin_users
        WHERE user_id = (SELECT auth.uid())
        AND is_active = true
    ) INTO v_is_admin;
    RETURN COALESCE(v_is_admin, false);
END;
$$;

CREATE OR REPLACE FUNCTION public.is_super_admin()
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_is_super BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM public.admin_users
        WHERE user_id = (SELECT auth.uid())
        AND role = 'super_admin'
        AND is_active = true
    ) INTO v_is_super;
    RETURN COALESCE(v_is_super, false);
END;
$$;

CREATE OR REPLACE FUNCTION public.get_admin_role()
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_role TEXT;
BEGIN
    SELECT role INTO v_role
    FROM public.admin_users
    WHERE user_id = (SELECT auth.uid())
    AND is_active = true;
    RETURN v_role;
END;
$$;

-- RLS policies
CREATE POLICY admin_users_select ON admin_users
    FOR SELECT TO authenticated
    USING (public.is_admin());

CREATE POLICY admin_users_insert ON admin_users
    FOR INSERT TO authenticated
    WITH CHECK (public.is_super_admin());

CREATE POLICY admin_users_update ON admin_users
    FOR UPDATE TO authenticated
    USING (public.is_super_admin());

CREATE POLICY admin_users_delete ON admin_users
    FOR DELETE TO authenticated
    USING (public.is_super_admin());

CREATE POLICY admin_audit_log_select ON admin_audit_log
    FOR SELECT TO authenticated
    USING (public.is_admin());

CREATE POLICY admin_audit_log_insert ON admin_audit_log
    FOR INSERT TO authenticated
    WITH CHECK (public.is_admin());

CREATE POLICY admin_alerts_select ON admin_alerts
    FOR SELECT TO authenticated
    USING (public.is_admin());

CREATE POLICY admin_alerts_update ON admin_alerts
    FOR UPDATE TO authenticated
    USING (public.is_admin());

CREATE POLICY admin_notes_select ON admin_notes
    FOR SELECT TO authenticated
    USING (public.is_admin());

CREATE POLICY admin_notes_insert ON admin_notes
    FOR INSERT TO authenticated
    WITH CHECK (public.is_admin());

CREATE POLICY admin_notes_update ON admin_notes
    FOR UPDATE TO authenticated
    USING (public.is_admin());

CREATE POLICY admin_notes_delete ON admin_notes
    FOR DELETE TO authenticated
    USING (public.is_admin());

-- Trigger for admin_notes updated_at
CREATE TRIGGER update_admin_notes_updated_at
    BEFORE UPDATE ON admin_notes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- ADMIN DASHBOARD FUNCTIONS
-- ============================================================

CREATE OR REPLACE FUNCTION public.calculate_mrr()
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_result JSON;
BEGIN
    SELECT json_build_object(
        'mrr_cents', COALESCE((
            SELECT SUM(sp.price_cents)
            FROM public.organization_subscriptions os
            JOIN public.subscription_plans sp ON os.plan_id = sp.id
            WHERE os.status = 'active'
            AND sp.price_cents > 0
        ), 0),
        'paid_users', COALESCE((
            SELECT COUNT(*)
            FROM public.organization_subscriptions os
            JOIN public.subscription_plans sp ON os.plan_id = sp.id
            WHERE os.status = 'active'
            AND sp.price_cents > 0
        ), 0)
    ) INTO v_result;
    
    RETURN v_result;
END;
$$;

CREATE OR REPLACE FUNCTION public.get_job_stats_24h()
RETURNS TABLE(
    total_jobs INTEGER,
    successful_jobs INTEGER,
    failed_jobs INTEGER,
    success_rate NUMERIC
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::INTEGER as total_jobs,
        COUNT(*) FILTER (WHERE status = 'completed')::INTEGER as successful_jobs,
        COUNT(*) FILTER (WHERE status = 'failed')::INTEGER as failed_jobs,
        CASE 
            WHEN COUNT(*) > 0 THEN 
                ROUND(COUNT(*) FILTER (WHERE status = 'completed')::NUMERIC / COUNT(*)::NUMERIC * 100, 2)
            ELSE 0
        END as success_rate
    FROM public.research_briefs
    WHERE created_at > NOW() - INTERVAL '24 hours';
END;
$$;

CREATE OR REPLACE FUNCTION public.get_admin_dashboard_metrics()
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_result JSON;
    v_total_users INTEGER;
    v_users_growth_week INTEGER;
    v_active_users_7d INTEGER;
    v_mrr JSON;
    v_active_alerts INTEGER;
BEGIN
    -- Total users
    SELECT COUNT(*) INTO v_total_users
    FROM public.users;
    
    -- Users growth this week
    SELECT COUNT(*) INTO v_users_growth_week
    FROM public.users
    WHERE created_at > NOW() - INTERVAL '7 days';
    
    -- Active users in last 7 days (users with activity)
    SELECT COUNT(DISTINCT organization_id) INTO v_active_users_7d
    FROM public.prospect_activities
    WHERE created_at > NOW() - INTERVAL '7 days';
    
    -- MRR
    SELECT public.calculate_mrr() INTO v_mrr;
    
    -- Active alerts
    SELECT COUNT(*) INTO v_active_alerts
    FROM public.admin_alerts
    WHERE status = 'active';
    
    SELECT json_build_object(
        'total_users', COALESCE(v_total_users, 0),
        'users_growth_week', COALESCE(v_users_growth_week, 0),
        'active_users_7d', COALESCE(v_active_users_7d, 0),
        'mrr_cents', COALESCE((v_mrr->>'mrr_cents')::integer, 0),
        'paid_users', COALESCE((v_mrr->>'paid_users')::integer, 0),
        'active_alerts', COALESCE(v_active_alerts, 0)
    ) INTO v_result;
    
    RETURN v_result;
END;
$$;

CREATE OR REPLACE FUNCTION public.get_admin_usage_trends(p_days INTEGER DEFAULT 7)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_result JSON;
BEGIN
    SELECT json_agg(day_data ORDER BY day_date) INTO v_result
    FROM (
        SELECT 
            day_date::date,
            json_build_object(
                'date', day_date::date,
                'researches', COALESCE((
                    SELECT COUNT(*) 
                    FROM public.research_briefs 
                    WHERE created_at::date = day_date::date
                ), 0),
                'preps', COALESCE((
                    SELECT COUNT(*) 
                    FROM public.meeting_preps 
                    WHERE created_at::date = day_date::date
                ), 0),
                'followups', COALESCE((
                    SELECT COUNT(*) 
                    FROM public.followups 
                    WHERE created_at::date = day_date::date
                ), 0),
                'new_users', COALESCE((
                    SELECT COUNT(*) 
                    FROM public.users 
                    WHERE created_at::date = day_date::date
                ), 0)
            ) as day_data
        FROM generate_series(
            NOW() - (p_days || ' days')::interval,
            NOW(),
            '1 day'::interval
        ) AS day_date
    ) trends;
    
    RETURN COALESCE(v_result, '[]'::json);
END;
$$;

CREATE OR REPLACE FUNCTION public.get_user_health_data(p_user_id UUID)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_result JSON;
    v_org_id UUID;
    v_plan TEXT;
    v_days_inactive INTEGER;
    v_error_count INTEGER;
    v_flow_count INTEGER;
    v_flow_limit INTEGER;
    v_profile_completeness INTEGER;
    v_has_failed_payment BOOLEAN;
BEGIN
    -- Get organization via organization_members
    SELECT om.organization_id INTO v_org_id
    FROM public.organization_members om
    WHERE om.user_id = p_user_id
    LIMIT 1;
    
    IF v_org_id IS NULL THEN
        RETURN json_build_object('error', 'User not found in organization');
    END IF;
    
    -- Get plan
    SELECT COALESCE(os.plan_id, 'free') INTO v_plan
    FROM public.organization_subscriptions os
    WHERE os.organization_id = v_org_id;
    
    -- Days since last activity
    SELECT COALESCE(
        EXTRACT(DAY FROM NOW() - MAX(created_at))::integer,
        999
    ) INTO v_days_inactive
    FROM public.prospect_activities
    WHERE organization_id = v_org_id;
    
    -- Error count in last 30 days
    SELECT COUNT(*) INTO v_error_count
    FROM public.research_briefs
    WHERE organization_id = v_org_id
    AND status = 'failed'
    AND created_at > NOW() - INTERVAL '30 days';
    
    -- Current flow usage from usage_records and subscription_plans
    SELECT COALESCE(ur.flow_count, 0), COALESCE((sp.features->>'flow_limit')::integer, 2)
    INTO v_flow_count, v_flow_limit
    FROM public.organization_subscriptions os
    JOIN public.subscription_plans sp ON os.plan_id = sp.id
    LEFT JOIN public.usage_records ur ON ur.organization_id = v_org_id 
        AND ur.period_start = date_trunc('month', NOW())
    WHERE os.organization_id = v_org_id;
    
    -- Profile completeness (simplified)
    SELECT COALESCE(
        (SELECT CASE 
            WHEN sp.job_title IS NOT NULL AND sp.experience_years IS NOT NULL THEN 80
            WHEN sp.job_title IS NOT NULL THEN 50
            ELSE 20
        END
        FROM public.sales_profiles sp
        WHERE sp.organization_id = v_org_id), 0
    ) INTO v_profile_completeness;
    
    -- Check for failed payments
    SELECT EXISTS (
        SELECT 1 FROM public.organization_subscriptions os
        WHERE os.organization_id = v_org_id
        AND os.status = 'past_due'
    ) INTO v_has_failed_payment;
    
    SELECT json_build_object(
        'plan', COALESCE(v_plan, 'free'),
        'days_since_last_activity', COALESCE(v_days_inactive, 0),
        'error_count_30d', COALESCE(v_error_count, 0),
        'flow_count', COALESCE(v_flow_count, 0),
        'flow_limit', COALESCE(v_flow_limit, 2),
        'flow_usage_percent', CASE 
            WHEN v_flow_limit <= 0 THEN 0
            ELSE ROUND(v_flow_count::numeric / v_flow_limit, 2)
        END,
        'profile_completeness', COALESCE(v_profile_completeness, 0),
        'has_failed_payment', COALESCE(v_has_failed_payment, false)
    ) INTO v_result;
    
    RETURN v_result;
END;
$$;

-- ============================================================
-- 45. CALENDAR CONNECTIONS (OAuth for Google/Microsoft)
-- ============================================================
-- Stores OAuth tokens and sync status per user per provider.
-- SPEC-038: Meetings & Calendar Integration

CREATE TABLE IF NOT EXISTS calendar_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    provider TEXT NOT NULL CHECK (provider IN ('google', 'microsoft')),
    
    -- OAuth tokens (encrypted before storage)
    access_token_encrypted BYTEA NOT NULL,
    refresh_token_encrypted BYTEA,
    token_expires_at TIMESTAMPTZ,
    encryption_key_id UUID,
    
    -- Account info
    email TEXT,
    
    -- Sync status
    last_sync_at TIMESTAMPTZ,
    last_sync_status TEXT CHECK (last_sync_status IN ('success', 'failed', 'partial')),
    last_sync_error TEXT,
    needs_reauth BOOLEAN DEFAULT false,
    
    -- Settings
    sync_enabled BOOLEAN DEFAULT true,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_calendar_connections_org ON calendar_connections(organization_id);
CREATE INDEX IF NOT EXISTS idx_calendar_connections_user ON calendar_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_calendar_connections_sync ON calendar_connections(sync_enabled, last_sync_at);
CREATE INDEX IF NOT EXISTS idx_calendar_connections_needs_reauth ON calendar_connections(needs_reauth) WHERE needs_reauth = true;

ALTER TABLE calendar_connections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own connections" ON calendar_connections 
    FOR SELECT USING (user_id = (SELECT auth.uid()));
CREATE POLICY "Users can insert own connections" ON calendar_connections 
    FOR INSERT WITH CHECK (user_id = (SELECT auth.uid()));
CREATE POLICY "Users can update own connections" ON calendar_connections 
    FOR UPDATE USING (user_id = (SELECT auth.uid()));
CREATE POLICY "Users can delete own connections" ON calendar_connections 
    FOR DELETE USING (user_id = (SELECT auth.uid()));

-- ============================================================
-- 46. CALENDAR MEETINGS (Synced from external calendars)
-- ============================================================
-- Synchronized meetings from Google/Microsoft calendars.
-- Note: Separate from the existing `meetings` table (manual meetings linked to deals).

CREATE TABLE IF NOT EXISTS calendar_meetings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    calendar_connection_id UUID NOT NULL REFERENCES calendar_connections(id) ON DELETE CASCADE,
    external_event_id TEXT NOT NULL,
    
    title TEXT NOT NULL,
    description TEXT,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    original_timezone TEXT DEFAULT 'UTC',
    location TEXT,
    meeting_url TEXT,
    
    is_recurring BOOLEAN DEFAULT false,
    recurrence_rule TEXT,
    recurring_event_id TEXT,
    
    status TEXT DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'tentative', 'cancelled')),
    attendees JSONB DEFAULT '[]',
    
    prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
    prospect_link_type TEXT CHECK (prospect_link_type IN ('auto', 'manual')),
    preparation_id UUID REFERENCES meeting_preps(id) ON DELETE SET NULL,
    followup_id UUID REFERENCES followups(id) ON DELETE SET NULL,
    legacy_meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL,
    
    etag TEXT,
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(calendar_connection_id, external_event_id)
);

CREATE INDEX IF NOT EXISTS idx_calendar_meetings_org ON calendar_meetings(organization_id);
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_user ON calendar_meetings(user_id);
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_time ON calendar_meetings(start_time);
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_end_time ON calendar_meetings(end_time);
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_prospect ON calendar_meetings(prospect_id) WHERE prospect_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_status ON calendar_meetings(status) WHERE status != 'cancelled';
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_recurring ON calendar_meetings(recurring_event_id) WHERE is_recurring = true;
CREATE INDEX IF NOT EXISTS idx_calendar_meetings_connection ON calendar_meetings(calendar_connection_id);

ALTER TABLE calendar_meetings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Org members can view meetings" ON calendar_meetings 
    FOR SELECT USING (organization_id IN (SELECT organization_id FROM organization_members WHERE user_id = (SELECT auth.uid())));
CREATE POLICY "Users can insert own meetings" ON calendar_meetings 
    FOR INSERT WITH CHECK (user_id = (SELECT auth.uid()));
CREATE POLICY "Users can update own meetings" ON calendar_meetings 
    FOR UPDATE USING (user_id = (SELECT auth.uid()));
CREATE POLICY "Users can delete own meetings" ON calendar_meetings 
    FOR DELETE USING (user_id = (SELECT auth.uid()));

-- ============================================================
-- 47. RECORDING INTEGRATIONS (Fireflies/Zoom/Teams config)
-- ============================================================

CREATE TABLE IF NOT EXISTS recording_integrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    provider TEXT NOT NULL CHECK (provider IN ('fireflies', 'zoom', 'teams')),
    credentials JSONB NOT NULL,
    
    account_email TEXT,
    account_name TEXT,
    
    last_sync_at TIMESTAMPTZ,
    last_sync_status TEXT CHECK (last_sync_status IN ('success', 'failed')),
    last_sync_error TEXT,
    needs_reauth BOOLEAN DEFAULT false,
    
    auto_import BOOLEAN DEFAULT true,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_recording_integrations_org ON recording_integrations(organization_id);
CREATE INDEX IF NOT EXISTS idx_recording_integrations_user ON recording_integrations(user_id);
CREATE INDEX IF NOT EXISTS idx_recording_integrations_provider ON recording_integrations(provider);
CREATE INDEX IF NOT EXISTS idx_recording_integrations_auto_import ON recording_integrations(auto_import) WHERE auto_import = true;

ALTER TABLE recording_integrations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own integrations" ON recording_integrations 
    FOR ALL USING (user_id = (SELECT auth.uid()));

-- ============================================================
-- 48. EXTERNAL RECORDINGS (Imported before processing)
-- ============================================================

CREATE TABLE IF NOT EXISTS external_recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    integration_id UUID NOT NULL REFERENCES recording_integrations(id) ON DELETE CASCADE,
    external_id TEXT NOT NULL,
    provider TEXT NOT NULL CHECK (provider IN ('fireflies', 'zoom', 'teams', 'mobile')),
    
    title TEXT,
    recording_date TIMESTAMPTZ NOT NULL,
    duration_seconds INTEGER,
    participants JSONB DEFAULT '[]',
    
    audio_url TEXT,
    transcript_url TEXT,
    transcript_text TEXT,
    
    matched_meeting_id UUID REFERENCES calendar_meetings(id) ON DELETE SET NULL,
    matched_prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
    match_confidence DECIMAL(5,4) CHECK (match_confidence >= 0 AND match_confidence <= 1),
    
    import_status TEXT DEFAULT 'pending' CHECK (import_status IN ('pending', 'imported', 'skipped', 'failed')),
    imported_followup_id UUID REFERENCES followups(id) ON DELETE SET NULL,
    import_error TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(integration_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_external_recordings_org ON external_recordings(organization_id);
CREATE INDEX IF NOT EXISTS idx_external_recordings_user ON external_recordings(user_id);
CREATE INDEX IF NOT EXISTS idx_external_recordings_status ON external_recordings(import_status);
CREATE INDEX IF NOT EXISTS idx_external_recordings_date ON external_recordings(recording_date);
CREATE INDEX IF NOT EXISTS idx_external_recordings_meeting ON external_recordings(matched_meeting_id) WHERE matched_meeting_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_external_recordings_prospect ON external_recordings(matched_prospect_id) WHERE matched_prospect_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_external_recordings_integration ON external_recordings(integration_id);

ALTER TABLE external_recordings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Org members can view recordings" ON external_recordings 
    FOR SELECT USING (organization_id IN (SELECT organization_id FROM organization_members WHERE user_id = (SELECT auth.uid())));
CREATE POLICY "Users can insert own recordings" ON external_recordings 
    FOR INSERT WITH CHECK (user_id = (SELECT auth.uid()));
CREATE POLICY "Users can update own recordings" ON external_recordings 
    FOR UPDATE USING (user_id = (SELECT auth.uid()));
CREATE POLICY "Users can delete own recordings" ON external_recordings 
    FOR DELETE USING (user_id = (SELECT auth.uid()));

-- ============================================================
-- FOLLOWUPS TABLE UPDATE (Add calendar/recording references)
-- ============================================================
-- Note: Columns are now in main CREATE TABLE statement.
-- These indexes are still needed:

CREATE INDEX IF NOT EXISTS idx_followups_calendar_meeting ON followups(calendar_meeting_id) WHERE calendar_meeting_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_followups_external_recording ON followups(external_recording_id) WHERE external_recording_id IS NOT NULL;

-- ============================================================
-- TRIGGERS FOR NEW TABLES
-- ============================================================

DROP TRIGGER IF EXISTS update_calendar_connections_updated_at ON calendar_connections;
CREATE TRIGGER update_calendar_connections_updated_at
    BEFORE UPDATE ON calendar_connections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_calendar_meetings_updated_at ON calendar_meetings;
CREATE TRIGGER update_calendar_meetings_updated_at
    BEFORE UPDATE ON calendar_meetings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_recording_integrations_updated_at ON recording_integrations;
CREATE TRIGGER update_recording_integrations_updated_at
    BEFORE UPDATE ON recording_integrations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_external_recordings_updated_at ON external_recordings;
CREATE TRIGGER update_external_recordings_updated_at
    BEFORE UPDATE ON external_recordings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 49. MOBILE RECORDINGS (Recordings from mobile/PWA app)
-- ============================================================
-- Stores recordings made via the DealMotion mobile app or PWA.
-- These are uploaded and processed into followups for AI analysis.

CREATE TABLE IF NOT EXISTS mobile_recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Prospect link (optional)
    prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
    
    -- File info
    storage_path TEXT NOT NULL,
    original_filename TEXT,
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    
    -- Mobile sync
    local_recording_id TEXT NOT NULL,  -- ID from mobile app for deduplication
    source TEXT NOT NULL DEFAULT 'mobile_app',  -- 'mobile_app', 'pwa', 'browser'
    
    -- Processing status
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error TEXT,
    
    -- Link to followup when imported/processed
    followup_id UUID REFERENCES followups(id) ON DELETE SET NULL,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    
    -- Unique constraint: one local_recording_id per organization
    UNIQUE(organization_id, local_recording_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mobile_recordings_org ON mobile_recordings(organization_id);
CREATE INDEX IF NOT EXISTS idx_mobile_recordings_user ON mobile_recordings(user_id);
CREATE INDEX IF NOT EXISTS idx_mobile_recordings_status ON mobile_recordings(status);

-- RLS
ALTER TABLE mobile_recordings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own org recordings" ON mobile_recordings
    FOR SELECT USING (organization_id IN (
        SELECT organization_id FROM organization_members WHERE user_id = (SELECT auth.uid())
    ));

CREATE POLICY "Users can insert recordings" ON mobile_recordings
    FOR INSERT WITH CHECK (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can update own recordings" ON mobile_recordings
    FOR UPDATE USING (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can delete own recordings" ON mobile_recordings
    FOR DELETE USING (user_id = (SELECT auth.uid()));

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_mobile_recordings_updated_at ON mobile_recordings;
CREATE TRIGGER update_mobile_recordings_updated_at
    BEFORE UPDATE ON mobile_recordings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- STORAGE BUCKET: recordings (for mobile app uploads)
-- ============================================================
INSERT INTO storage.buckets (id, name, public) 
VALUES ('recordings', 'recordings', false)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Users can upload recordings"
    ON storage.objects FOR INSERT
    TO authenticated
    WITH CHECK (bucket_id = 'recordings');

CREATE POLICY "Users can read recordings"
    ON storage.objects FOR SELECT
    TO authenticated
    USING (bucket_id = 'recordings');

CREATE POLICY "Users can delete recordings"
    ON storage.objects FOR DELETE
    TO authenticated
    USING (bucket_id = 'recordings');

-- ============================================================
-- SCHEDULED RECORDINGS (AI Notetaker via Recall.ai)
-- Added in v3.9 for SPEC-043
-- ============================================================

CREATE TABLE IF NOT EXISTS scheduled_recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Recall.ai reference
    recall_bot_id TEXT UNIQUE,
    
    -- Meeting info
    meeting_url TEXT NOT NULL,
    meeting_title TEXT,
    meeting_platform TEXT, -- 'teams', 'meet', 'zoom', 'webex'
    scheduled_time TIMESTAMPTZ NOT NULL,
    
    -- Status: scheduled, joining, waiting_room, recording, processing, complete, error, cancelled
    status TEXT NOT NULL DEFAULT 'scheduled',
    
    -- Linking
    prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
    followup_id UUID REFERENCES followups(id) ON DELETE SET NULL,
    
    -- Recording data (after completion)
    recording_url TEXT,
    duration_seconds INTEGER,
    participants TEXT[], -- Array of participant names
    
    -- Error handling
    error_message TEXT,
    
    -- Metadata
    source TEXT DEFAULT 'manual', -- 'manual', 'email_invite', 'calendar_sync'
    invite_email TEXT, -- If created via email invite
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Indexes for scheduled_recordings
CREATE INDEX IF NOT EXISTS idx_scheduled_recordings_org ON scheduled_recordings(organization_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_recordings_user ON scheduled_recordings(user_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_recordings_recall ON scheduled_recordings(recall_bot_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_recordings_status ON scheduled_recordings(status);
CREATE INDEX IF NOT EXISTS idx_scheduled_recordings_scheduled ON scheduled_recordings(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_scheduled_recordings_prospect ON scheduled_recordings(prospect_id);

-- RLS for scheduled_recordings
ALTER TABLE scheduled_recordings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view org scheduled recordings"
    ON scheduled_recordings FOR SELECT
    USING (organization_id IN (
        SELECT organization_id FROM users WHERE id = (SELECT auth.uid())
    ));

CREATE POLICY "Users can insert own scheduled recordings"
    ON scheduled_recordings FOR INSERT
    WITH CHECK (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can update own scheduled recordings"
    ON scheduled_recordings FOR UPDATE
    USING (user_id = (SELECT auth.uid()));

CREATE POLICY "Users can delete own scheduled recordings"
    ON scheduled_recordings FOR DELETE
    USING (user_id = (SELECT auth.uid()));

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_scheduled_recordings_updated_at ON scheduled_recordings;
CREATE TRIGGER update_scheduled_recordings_updated_at
    BEFORE UPDATE ON scheduled_recordings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- AUTOPILOT_PROPOSALS (SPEC-045: DealMotion Autopilot)
-- ============================================================
CREATE TABLE IF NOT EXISTS autopilot_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Type & trigger
    proposal_type TEXT NOT NULL CHECK (proposal_type IN (
        'research_prep',      -- New meeting, unknown org
        'prep_only',          -- Known prospect, no prep
        'followup_pack',      -- Post-meeting
        'reactivation',       -- Silent prospect
        'complete_flow'       -- Research done, no next step
    )),
    
    trigger_type TEXT NOT NULL CHECK (trigger_type IN (
        'calendar_new_org',
        'calendar_known_prospect',
        'meeting_ended',
        'transcript_ready',
        'prospect_silent',
        'flow_incomplete',
        'manual'
    )),
    trigger_entity_id UUID,
    trigger_entity_type TEXT,
    
    -- Content
    title TEXT NOT NULL,
    description TEXT,
    luna_message TEXT NOT NULL,
    
    -- Actions
    suggested_actions JSONB NOT NULL DEFAULT '[]',
    
    -- State
    status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN (
        'proposed', 'accepted', 'executing', 'completed',
        'declined', 'snoozed', 'expired', 'failed'
    )),
    priority INTEGER DEFAULT 50 CHECK (priority >= 0 AND priority <= 100),
    
    -- Decision
    decided_at TIMESTAMPTZ,
    decision_reason TEXT,
    snoozed_until TIMESTAMPTZ,
    
    -- Execution
    execution_started_at TIMESTAMPTZ,
    execution_completed_at TIMESTAMPTZ,
    execution_result JSONB,
    execution_error TEXT,
    artifacts JSONB DEFAULT '[]',
    
    -- Expiry
    expires_at TIMESTAMPTZ,
    expired_reason TEXT,
    
    -- Metadata
    context_data JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proposals_user_status ON autopilot_proposals(user_id, status);
CREATE INDEX IF NOT EXISTS idx_proposals_org ON autopilot_proposals(organization_id);
CREATE INDEX IF NOT EXISTS idx_proposals_expires ON autopilot_proposals(expires_at) WHERE status = 'proposed';
CREATE INDEX IF NOT EXISTS idx_proposals_trigger ON autopilot_proposals(trigger_entity_id, trigger_entity_type);
CREATE INDEX IF NOT EXISTS idx_proposals_created ON autopilot_proposals(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposals_priority ON autopilot_proposals(user_id, priority DESC) WHERE status = 'proposed';

CREATE UNIQUE INDEX IF NOT EXISTS idx_proposals_unique_trigger 
ON autopilot_proposals(trigger_entity_id, trigger_entity_type, user_id) 
WHERE status IN ('proposed', 'accepted', 'executing');

ALTER TABLE autopilot_proposals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own proposals" ON autopilot_proposals FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can update own proposals" ON autopilot_proposals FOR UPDATE USING (user_id = auth.uid());
CREATE POLICY "Users can insert own proposals" ON autopilot_proposals FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Service role can manage all proposals" ON autopilot_proposals FOR ALL USING (auth.role() = 'service_role');

-- ============================================================
-- AUTOPILOT_SETTINGS (User configuration)
-- ============================================================
CREATE TABLE IF NOT EXISTS autopilot_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    enabled BOOLEAN DEFAULT true,
    auto_research_new_meetings BOOLEAN DEFAULT true,
    auto_prep_known_prospects BOOLEAN DEFAULT true,
    auto_followup_after_meeting BOOLEAN DEFAULT true,
    reactivation_days_threshold INTEGER DEFAULT 14,
    prep_hours_before_meeting INTEGER DEFAULT 24,
    notification_style TEXT DEFAULT 'balanced' CHECK (notification_style IN ('eager', 'balanced', 'minimal')),
    excluded_meeting_keywords TEXT[] DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_autopilot_settings_user ON autopilot_settings(user_id);

ALTER TABLE autopilot_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own settings" ON autopilot_settings FOR ALL USING (user_id = auth.uid());
CREATE POLICY "Service role can manage all settings" ON autopilot_settings FOR ALL USING (auth.role() = 'service_role');

-- ============================================================
-- MEETING_OUTCOMES (Learning data)
-- ============================================================
CREATE TABLE IF NOT EXISTS meeting_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    calendar_meeting_id UUID REFERENCES calendar_meetings(id) ON DELETE SET NULL,
    preparation_id UUID REFERENCES meeting_preps(id) ON DELETE SET NULL,
    followup_id UUID REFERENCES followups(id) ON DELETE SET NULL,
    prospect_id UUID REFERENCES prospects(id) ON DELETE SET NULL,
    
    outcome_rating TEXT CHECK (outcome_rating IN ('positive', 'neutral', 'negative')),
    outcome_source TEXT CHECK (outcome_source IN ('user_input', 'followup_sentiment', 'inferred')),
    
    prep_viewed BOOLEAN DEFAULT false,
    prep_view_duration_seconds INTEGER,
    prep_scroll_depth FLOAT,
    
    had_contact_analysis BOOLEAN,
    had_kb_content BOOLEAN,
    prep_length_words INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outcomes_user ON meeting_outcomes(user_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_prep ON meeting_outcomes(preparation_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_org ON meeting_outcomes(organization_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_prospect ON meeting_outcomes(prospect_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_calendar ON meeting_outcomes(calendar_meeting_id);

ALTER TABLE meeting_outcomes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own outcomes" ON meeting_outcomes FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can insert own outcomes" ON meeting_outcomes FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Users can update own outcomes" ON meeting_outcomes FOR UPDATE USING (user_id = auth.uid());
CREATE POLICY "Service role can manage all outcomes" ON meeting_outcomes FOR ALL USING (auth.role() = 'service_role');

-- ============================================================
-- USER_PREP_PREFERENCES (Learned preferences)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_prep_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    
    preferred_length TEXT CHECK (preferred_length IN ('short', 'medium', 'long')),
    valued_sections TEXT[] DEFAULT '{}',
    deemphasized_sections TEXT[] DEFAULT '{}',
    
    avg_prep_view_duration_seconds INTEGER,
    prep_completion_rate FLOAT,
    positive_outcome_rate FLOAT,
    
    sample_size INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prep_preferences_user ON user_prep_preferences(user_id);

ALTER TABLE user_prep_preferences ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own preferences" ON user_prep_preferences FOR ALL USING (user_id = auth.uid());
CREATE POLICY "Service role can manage all preferences" ON user_prep_preferences FOR ALL USING (auth.role() = 'service_role');

-- ============================================================
-- AUTOPILOT TRIGGERS
-- ============================================================
CREATE OR REPLACE FUNCTION update_autopilot_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS autopilot_proposals_updated_at ON autopilot_proposals;
CREATE TRIGGER autopilot_proposals_updated_at
    BEFORE UPDATE ON autopilot_proposals
    FOR EACH ROW EXECUTE FUNCTION update_autopilot_updated_at();

DROP TRIGGER IF EXISTS autopilot_settings_updated_at ON autopilot_settings;
CREATE TRIGGER autopilot_settings_updated_at
    BEFORE UPDATE ON autopilot_settings
    FOR EACH ROW EXECUTE FUNCTION update_autopilot_updated_at();

DROP TRIGGER IF EXISTS user_prep_preferences_updated_at ON user_prep_preferences;
CREATE TRIGGER user_prep_preferences_updated_at
    BEFORE UPDATE ON user_prep_preferences
    FOR EACH ROW EXECUTE FUNCTION update_autopilot_updated_at();

-- ============================================================
-- GDPR COMPLIANCE TABLES (v4.1)
-- ============================================================

-- Add deletion tracking to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS 
    deletion_status TEXT DEFAULT 'active' 
    CHECK (deletion_status IN ('active', 'pending_deletion', 'deleted', 'anonymized'));
ALTER TABLE users ADD COLUMN IF NOT EXISTS deletion_requested_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deletion_scheduled_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deletion_completed_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deletion_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_users_deletion_status 
    ON users(deletion_status) WHERE deletion_status != 'active';
CREATE INDEX IF NOT EXISTS idx_users_deletion_scheduled 
    ON users(deletion_scheduled_at) WHERE deletion_status = 'pending_deletion';

-- GDPR Deletion Requests (Audit Trail)
CREATE TABLE IF NOT EXISTS gdpr_deletion_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    user_email TEXT NOT NULL,
    organization_id UUID,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scheduled_for TIMESTAMPTZ NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'processing', 'completed', 'cancelled', 'failed')),
    processing_started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancellation_reason TEXT,
    deletion_summary JSONB,
    error_message TEXT,
    billing_data_anonymized BOOLEAN DEFAULT false,
    billing_retention_hash TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gdpr_deletion_user ON gdpr_deletion_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_gdpr_deletion_status ON gdpr_deletion_requests(status);
CREATE INDEX IF NOT EXISTS idx_gdpr_deletion_scheduled ON gdpr_deletion_requests(scheduled_for) 
    WHERE status = 'pending';

-- GDPR Data Exports
CREATE TABLE IF NOT EXISTS gdpr_data_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'processing', 'ready', 'downloaded', 'expired', 'failed')),
    processing_started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    storage_path TEXT,
    file_size_bytes INTEGER,
    download_url TEXT,
    download_expires_at TIMESTAMPTZ,
    downloaded_at TIMESTAMPTZ,
    download_count INTEGER DEFAULT 0,
    expires_at TIMESTAMPTZ,
    error_message TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gdpr_export_user ON gdpr_data_exports(user_id);
CREATE INDEX IF NOT EXISTS idx_gdpr_export_status ON gdpr_data_exports(status);
CREATE INDEX IF NOT EXISTS idx_gdpr_export_expires ON gdpr_data_exports(expires_at) WHERE status = 'ready';

-- Billing Archive (Anonymized retention)
CREATE TABLE IF NOT EXISTS billing_archive (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_hash TEXT NOT NULL,
    organization_hash TEXT,
    original_payment_id UUID,
    stripe_invoice_id TEXT,
    stripe_payment_intent_id TEXT,
    stripe_charge_id TEXT,
    amount_cents INTEGER NOT NULL,
    currency TEXT DEFAULT 'eur',
    status TEXT NOT NULL,
    invoice_pdf_url TEXT,
    invoice_number TEXT,
    original_paid_at TIMESTAMPTZ,
    original_created_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ DEFAULT NOW(),
    archive_reason TEXT DEFAULT 'user_deletion',
    gdpr_request_id UUID REFERENCES gdpr_deletion_requests(id),
    retention_expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 years'
);

CREATE INDEX IF NOT EXISTS idx_billing_archive_hash ON billing_archive(user_hash);
CREATE INDEX IF NOT EXISTS idx_billing_archive_retention ON billing_archive(retention_expires_at);

-- GDPR Exports Storage Bucket
INSERT INTO storage.buckets (id, name, public) 
VALUES ('gdpr-exports', 'gdpr-exports', false)
ON CONFLICT (id) DO NOTHING;

-- RLS for GDPR tables
ALTER TABLE gdpr_deletion_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE gdpr_data_exports ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_archive ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own deletion requests" ON gdpr_deletion_requests 
    FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid()));
CREATE POLICY "Users can update own pending deletion" ON gdpr_deletion_requests 
    FOR UPDATE TO authenticated USING (user_id = (SELECT auth.uid()) AND status = 'pending');
CREATE POLICY "Users can view own exports" ON gdpr_data_exports 
    FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid()));
CREATE POLICY "Admin can view billing archive" ON billing_archive 
    FOR SELECT TO authenticated USING (public.is_admin());
CREATE POLICY "Service role manages deletion requests" ON gdpr_deletion_requests 
    FOR ALL TO service_role USING (true);
CREATE POLICY "Service role manages exports" ON gdpr_data_exports 
    FOR ALL TO service_role USING (true);
CREATE POLICY "Service role manages billing archive" ON billing_archive 
    FOR ALL TO service_role USING (true);

-- GDPR Triggers
CREATE TRIGGER update_gdpr_deletion_requests_updated_at
    BEFORE UPDATE ON gdpr_deletion_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_gdpr_data_exports_updated_at
    BEFORE UPDATE ON gdpr_data_exports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- GDPR Helper Functions
CREATE OR REPLACE FUNCTION generate_user_hash(p_user_id UUID)
RETURNS TEXT AS $$
BEGIN
    RETURN encode(
        digest(p_user_id::text || '-dealmotion-billing-archive-' || extract(epoch from now())::text, 'sha256'),
        'hex'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

CREATE OR REPLACE FUNCTION can_user_be_deleted(p_user_id UUID)
RETURNS TABLE(can_delete BOOLEAN, reason TEXT) AS $$
DECLARE
    v_active_subscription BOOLEAN;
    v_pending_deletion BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM public.organization_subscriptions os
        JOIN public.organization_members om ON os.organization_id = om.organization_id
        WHERE om.user_id = p_user_id AND os.status = 'active' 
        AND os.plan_id != 'free' AND os.cancel_at_period_end = false
    ) INTO v_active_subscription;
    
    IF v_active_subscription THEN
        RETURN QUERY SELECT false, 'Active subscription must be cancelled first';
        RETURN;
    END IF;
    
    SELECT EXISTS (
        SELECT 1 FROM public.gdpr_deletion_requests
        WHERE user_id = p_user_id AND status IN ('pending', 'processing')
    ) INTO v_pending_deletion;
    
    IF v_pending_deletion THEN
        RETURN QUERY SELECT false, 'Deletion already in progress';
        RETURN;
    END IF;
    
    RETURN QUERY SELECT true, NULL::TEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- ============================================================
-- END OF SCHEMA
-- ============================================================
-- Version: 4.1
-- Last Updated: 23 December 2025
-- 
-- Changes in 4.1:
-- - Added GDPR compliance tables (AVG/GDPR Implementation)
-- - Added gdpr_deletion_requests table (deletion audit trail)
-- - Added gdpr_data_exports table (export tracking)
-- - Added billing_archive table (anonymized billing retention)
-- - Added deletion tracking columns to users table
-- - Added gdpr-exports storage bucket
-- - Added generate_user_hash function
-- - Added can_user_be_deleted function
-- - Added RLS policies for all GDPR tables
--
-- Changes in 4.0:
-- - Added autopilot_proposals table (SPEC-045: DealMotion Autopilot)
-- - Added autopilot_settings table (user configuration)
-- - Added meeting_outcomes table (learning data)
-- - Added user_prep_preferences table (learned preferences)
-- - Added RLS policies for all autopilot tables
-- - Added unique constraint for duplicate proposal prevention
-- 
-- Changes in 3.9:
-- - Added scheduled_recordings table (AI Notetaker via Recall.ai)
-- - SPEC-043: AI Notetaker / Recall.ai Integration
-- 
-- Changes in 3.8:
-- - Added mobile_recordings table (for PWA/mobile app recordings)
-- - Added recordings storage bucket
-- - Added RLS policies for mobile_recordings
-- 
-- Summary:
-- - Tables: 53 (50 + 3 GDPR)
-- - Views: 2
-- - Functions: 45 (43 + 2 GDPR)
-- - Triggers: 43 (41 + 2 GDPR)
-- - Storage Buckets: 5 (with policies)
-- - Indexes: 222 (215 + 7 GDPR)
-- 
-- This file is for REFERENCE ONLY. Do not run on existing database!
-- Use individual migration files for updates.
-- ============================================================
