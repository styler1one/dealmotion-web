/**
 * Centralized TypeScript type definitions for DealMotion.
 * 
 * This file contains all shared types used across the application.
 * Import types from here instead of defining them inline.
 */

// ==========================================
// User & Auth Types
// ==========================================

export interface User {
  id: string
  email?: string  // Optional to match Supabase's User type
  created_at?: string
  user_metadata?: UserMetadata
  app_metadata?: AppMetadata
}

export interface UserMetadata {
  full_name?: string
  avatar_url?: string
  provider?: string
}

export interface AppMetadata {
  provider?: string
  providers?: string[]
}

export interface AuthSession {
  access_token: string
  refresh_token: string
  expires_in: number
  expires_at?: number
  user: User
}

// ==========================================
// Organization Types
// ==========================================

export interface Organization {
  id: string
  name: string
  created_at: string
  updated_at?: string
}

export interface OrganizationMember {
  id: string
  organization_id: string
  user_id: string
  role: 'owner' | 'admin' | 'member'
  created_at: string
}

// ==========================================
// Research Types
// ==========================================

export type ResearchStatus = 'pending' | 'researching' | 'completed' | 'failed'

export interface ResearchBrief {
  id: string
  organization_id?: string
  prospect_id?: string
  company_name: string
  country?: string
  city?: string
  company_linkedin_url?: string
  company_website_url?: string
  status: ResearchStatus
  brief_content?: string
  error_message?: string
  created_at: string
  completed_at?: string
  contact_count?: number
}

export interface CompanyOption {
  company_name: string
  description?: string
  website?: string
  linkedin_url?: string
  location?: string
  confidence: number
}

export interface CompanySearchResponse {
  query_company: string
  query_country: string
  options: CompanyOption[]
  message?: string
}

// ==========================================
// Prospect Types
// ==========================================

export type ProspectStatus = 'new' | 'researching' | 'qualified' | 'meeting_scheduled' | 'proposal_sent' | 'won' | 'lost' | 'inactive'

export interface Prospect {
  id: string
  organization_id: string
  company_name: string
  company_name_normalized?: string
  status: ProspectStatus
  website?: string
  linkedin_url?: string
  industry?: string
  company_size?: string
  country?: string
  city?: string
  employee_count?: string
  annual_revenue?: string
  headquarters_location?: string
  contact_name?: string
  contact_email?: string
  contact_phone?: string
  contact_role?: string
  contact_linkedin?: string
  tags?: string[]
  notes?: string
  last_activity_at?: string
  created_at: string
  updated_at?: string
}

export interface ProspectContact {
  id: string
  prospect_id: string
  name: string
  role?: string
  email?: string
  phone?: string
  linkedin_url?: string
  communication_style?: string
  decision_authority?: 'decision_maker' | 'influencer' | 'gatekeeper' | 'end_user'
  profile_brief?: string
  opening_suggestions?: string[]
  questions_to_ask?: string[]
  topics_to_avoid?: string[]
  analysis_status?: 'pending' | 'analyzing' | 'completed' | 'failed'
  analyzed_at?: string
  created_at: string
  updated_at?: string
}

// ==========================================
// Preparation Types
// ==========================================

export type MeetingType = 'discovery' | 'demo' | 'closing' | 'follow_up' | 'other'
export type PrepStatus = 'pending' | 'generating' | 'completed' | 'failed'

export interface MeetingPrep {
  id: string
  organization_id?: string
  prospect_id?: string
  research_id?: string
  prospect_company_name: string  // This is the actual field name from API
  meeting_type: MeetingType
  meeting_date?: string
  custom_notes?: string
  status: PrepStatus
  brief_content?: string
  error_message?: string
  created_at: string
  completed_at?: string
}

// ==========================================
// Follow-up Types
// ==========================================

export type FollowupStatus = 'pending' | 'processing' | 'transcribing' | 'analyzing' | 'completed' | 'failed'

export interface Followup {
  id: string
  organization_id?: string
  prospect_id?: string
  prep_id?: string
  prospect_company_name?: string  // Company name from prospect
  meeting_subject?: string        // Alternative display name
  status: FollowupStatus
  transcript?: string
  summary?: string
  action_items?: ActionItem[]
  email_draft?: string
  coaching_feedback?: string
  error_message?: string
  created_at: string
  completed_at?: string
  include_coaching?: boolean
}

export interface ActionItem {
  description: string
  owner?: string
  deadline?: string
  priority?: 'high' | 'medium' | 'low'
}

// ==========================================
// Knowledge Base Types
// ==========================================

export type KBFileStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface KBFile {
  id: string
  organization_id: string
  file_name: string
  file_type: string
  file_size: number
  storage_path: string
  status: KBFileStatus
  chunk_count?: number
  error_message?: string
  created_at: string
  processed_at?: string
}

// ==========================================
// Profile Types
// ==========================================

export interface SalesProfile {
  id: string
  user_id: string
  organization_id: string
  full_name?: string
  profile_completeness?: number
  interview_responses?: Record<string, string>
  narrative?: string
  is_complete: boolean
  created_at: string
  updated_at?: string
}

export interface CompanyProfile {
  id: string
  organization_id: string
  company_name?: string
  profile_completeness?: number
  interview_responses?: Record<string, string>
  narrative?: string
  is_complete: boolean
  created_at: string
  updated_at?: string
}

// ==========================================
// Settings Types
// ==========================================

export interface UserSettings {
  user_id: string
  app_language: string
  output_language: string
  email_language: string
  created_at?: string
  updated_at?: string
}

// ==========================================
// Billing Types
// ==========================================

export type SubscriptionStatus = 'active' | 'trialing' | 'past_due' | 'canceled' | 'unpaid' | 'incomplete'
export type PlanId = 'free' | 'solo_monthly' | 'solo_yearly' | 'teams'

export interface SubscriptionPlan {
  id: PlanId
  name: string
  description?: string
  price_cents?: number
  billing_interval?: 'month' | 'year'
  features: PlanFeatures
  is_active: boolean
  display_order: number
}

export interface PlanFeatures {
  research_limit: number
  preparation_limit: number
  followup_limit: number
  transcription_seconds_limit: number
  kb_document_limit: number
  contact_analysis: 'basic' | 'full'
  pdf_watermark: boolean
  user_limit: number
  crm_integration: boolean
  team_sharing: boolean
  priority_support: boolean
  sso: boolean
  analytics_dashboard: boolean
  dedicated_support: boolean
  onboarding_call: boolean
}

export interface Subscription {
  id: string
  organization_id: string
  plan_id: PlanId
  status: SubscriptionStatus
  stripe_customer_id?: string
  stripe_subscription_id?: string
  current_period_start?: string
  current_period_end?: string
  trial_end?: string
  cancel_at_period_end: boolean
  is_paid: boolean
  created_at: string
  updated_at?: string
}

export interface UsageRecord {
  organization_id: string
  period_start: string
  period_end: string
  research_count: number
  preparation_count: number
  followup_count: number
  transcription_seconds: number
  kb_document_count: number
}

// ==========================================
// Deal Types
// ==========================================

export interface Deal {
  id: string
  prospect_id: string
  organization_id: string
  name: string
  description?: string
  is_active: boolean
  
  // CRM Sync fields (read-only, filled by CRM integration)
  crm_deal_id?: string
  crm_source?: string
  crm_stage?: string
  crm_value_cents?: number
  crm_currency?: string
  crm_probability?: number
  crm_expected_close?: string
  crm_owner?: string
  crm_synced_at?: string
  
  created_at: string
  updated_at?: string
  created_by?: string
}

export interface DealWithStats extends Deal {
  meeting_count: number
  prep_count: number
  followup_count: number
  company_name?: string
  latest_meeting?: {
    id: string
    title: string
    scheduled_date?: string
    status: string
  }
}

export interface DealCreate {
  prospect_id: string
  name: string
  description?: string
}

export interface DealUpdate {
  name?: string
  description?: string
  is_active?: boolean
}

// ==========================================
// Meeting Types
// ==========================================

export type MeetingStatus = 'scheduled' | 'completed' | 'cancelled' | 'no_show'
export type MeetingOutcome = 'positive' | 'neutral' | 'negative'
export type SalesMeetingType = 'discovery' | 'demo' | 'negotiation' | 'closing' | 'review' | 'other'

export interface Meeting {
  id: string
  deal_id?: string
  prospect_id: string
  organization_id: string
  title: string
  meeting_type?: SalesMeetingType
  scheduled_date?: string
  actual_date?: string
  duration_minutes?: number
  location?: string
  contact_ids: string[]
  notes?: string
  status: MeetingStatus
  outcome?: MeetingOutcome
  created_at: string
  updated_at?: string
  created_by?: string
}

export interface MeetingWithLinks extends Meeting {
  has_prep: boolean
  prep_id?: string
  has_followup: boolean
  followup_id?: string
  contact_names: string[]
}

export interface MeetingCreate {
  prospect_id: string
  deal_id?: string
  title: string
  meeting_type?: SalesMeetingType
  scheduled_date?: string
  actual_date?: string
  duration_minutes?: number
  location?: string
  contact_ids?: string[]
  notes?: string
}

export interface MeetingUpdate {
  title?: string
  meeting_type?: SalesMeetingType
  deal_id?: string
  scheduled_date?: string
  actual_date?: string
  duration_minutes?: number
  location?: string
  contact_ids?: string[]
  notes?: string
  status?: MeetingStatus
  outcome?: MeetingOutcome
}

// ==========================================
// Activity Types (Timeline)
// ==========================================

export type ActivityType = 'research' | 'contact_added' | 'prep' | 'meeting' | 'followup' | 'deal_created' | 'note'

export interface Activity {
  id: string
  prospect_id: string
  deal_id?: string
  meeting_id?: string
  organization_id: string
  activity_type: ActivityType
  activity_id?: string
  title: string
  description?: string
  icon?: string
  metadata?: Record<string, unknown>
  created_at: string
  created_by?: string
}

export interface ActivityCreate {
  prospect_id: string
  deal_id?: string
  meeting_id?: string
  activity_type: ActivityType
  activity_id?: string
  title: string
  description?: string
  icon?: string
  metadata?: Record<string, unknown>
}

// ==========================================
// Prospect Hub Types
// ==========================================

export interface ProspectHubSummary {
  prospect_id: string
  company_name: string
  status?: string
  research_count: number
  contact_count: number
  active_deal_count: number
  meeting_count: number
  prep_count: number
  followup_count: number
  latest_activity?: Activity
  created_at: string
  last_activity_at?: string
}

// Inline document items for Prospect Hub
export interface ProspectHubPreparation {
  id: string
  prospect_company_name: string
  meeting_type?: string
  status: 'pending' | 'generating' | 'completed' | 'failed'
  created_at: string
  completed_at?: string
  contact_ids?: string[]
  contact_names?: string[]  // Enriched by backend
}

export interface ProspectHubFollowup {
  id: string
  prospect_company_name: string
  meeting_subject?: string
  status: 'pending' | 'transcribing' | 'summarizing' | 'completed' | 'failed'
  created_at: string
  completed_at?: string
  contact_ids?: string[]
  contact_names?: string[]  // Enriched by backend
}

export interface ProspectHub {
  prospect: Prospect
  research?: ResearchBrief
  contacts: ProspectContact[]
  deals: DealWithStats[]
  preparations: ProspectHubPreparation[]
  followups: ProspectHubFollowup[]
  recent_activities: Activity[]
  stats: ProspectHubSummary
}

// ==========================================
// Calendar Meeting Types (for Calendar Integration)
// ==========================================

export interface CalendarMeetingAttendee {
  email: string
  name?: string
  response_status?: string
}

export interface CalendarMeetingPrepStatus {
  has_prep: boolean
  prep_id?: string
  prep_created_at?: string
  is_stale?: boolean
}

export interface CalendarMeeting {
  id: string
  title: string
  description?: string
  start_time: string
  end_time: string
  location?: string
  meeting_url?: string
  is_online: boolean
  status: string
  attendees: CalendarMeetingAttendee[]
  organizer_email?: string
  is_now: boolean
  is_today: boolean
  is_tomorrow: boolean
  prospect_id?: string
  prospect_name?: string
  prep_status?: CalendarMeetingPrepStatus
  is_recurring: boolean
}

// ==========================================
// API Response Types
// ==========================================

export interface ApiError {
  message: string
  code?: string
  details?: Record<string, unknown>
}

export interface PaginatedResponse<T> {
  data: T[]
  count: number
  page: number
  page_size: number
  total_pages: number
}

// ==========================================
// Form Types
// ==========================================

export interface ResearchFormData {
  company_name: string
  company_linkedin_url?: string
  company_website_url?: string
  country?: string
  city?: string
  language?: string
}

export interface PrepFormData {
  research_id?: string
  company_name: string
  meeting_type: MeetingType
  meeting_date?: string
  meeting_notes?: string
  contact_ids?: string[]
  language?: string
}

export interface FollowupFormData {
  prep_id?: string
  company_name: string
  include_coaching?: boolean
  language?: string
}

