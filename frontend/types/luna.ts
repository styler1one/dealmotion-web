/**
 * Luna Unified AI Assistant - TypeScript Types
 * SPEC-046-Luna-Unified-AI-Assistant
 */

// =============================================================================
// ENUMS
// =============================================================================

export type MessageType =
  | 'start_research'
  | 'review_research'
  | 'prepare_outreach'
  | 'first_touch_sent'
  | 'suggest_meeting_creation'
  | 'create_prep'
  | 'prep_ready'
  | 'review_meeting_summary'
  | 'review_customer_report'
  | 'send_followup_email'
  | 'create_action_items'
  | 'update_crm_notes'
  | 'deal_analysis'
  | 'sales_coaching_feedback'

export type MessageStatus =
  | 'pending'
  | 'executing'
  | 'completed'
  | 'dismissed'
  | 'snoozed'
  | 'expired'
  | 'failed'

export type ActionType = 'navigate' | 'execute' | 'inline'

export type SnoozeOption =
  | 'later_today'
  | 'tomorrow_morning'
  | 'next_working_day'
  | 'after_meeting'
  | 'custom'

export type Surface = 'home' | 'widget'

export type LunaMode = 'morning' | 'proposal' | 'urgency' | 'celebration' | 'focus'

export type TipCategory = 'research' | 'prep' | 'followup' | 'general'

export type OutreachChannel =
  | 'linkedin_connect'
  | 'linkedin_message'
  | 'email'
  | 'whatsapp'
  | 'other'

export type OutreachStatus = 'draft' | 'sent' | 'skipped'

// =============================================================================
// MESSAGE MODELS
// =============================================================================

export interface LunaMessage {
  id: string
  userId: string
  organizationId: string
  messageType: MessageType
  dedupeKey: string
  title: string
  description?: string
  lunaMessage: string
  actionType: ActionType
  actionRoute?: string
  actionData: Record<string, any>
  priority: number
  priorityInputs: Record<string, any>
  expiresAt?: string
  snoozeUntil?: string
  status: MessageStatus
  prospectId?: string
  contactId?: string
  meetingId?: string
  researchId?: string
  prepId?: string
  followupId?: string
  outreachId?: string
  errorCode?: string
  errorMessage?: string
  retryable: boolean
  createdAt: string
  updatedAt: string
  viewedAt?: string
  actedAt?: string
}

export interface MessageCounts {
  pending: number
  executing: number
  completed: number
  dismissed: number
  snoozed: number
  expired: number
  failed: number
  urgent: number
}

export interface MessagesResponse {
  messages: LunaMessage[]
  counts: MessageCounts
  total: number
}

// =============================================================================
// ACTION MODELS
// =============================================================================

export interface MessageActionRequest {
  reason?: string
  snoozeUntil?: string
  snoozeOption?: SnoozeOption
  surface?: Surface
}

export interface MessageShowRequest {
  surface: Surface
}

export interface MessageActionResponse {
  success: boolean
  messageId: string
  newStatus: MessageStatus
  error?: string
}

// =============================================================================
// SETTINGS MODELS
// =============================================================================

export interface LunaSettings {
  id: string
  userId: string
  organizationId: string
  enabled: boolean
  showWidget: boolean
  showContextualTips: boolean
  prepReminderHours: number
  outreachCooldownDays: number
  excludedMeetingKeywords: string[]
  createdAt: string
  updatedAt: string
}

export interface LunaSettingsUpdate {
  enabled?: boolean
  showWidget?: boolean
  showContextualTips?: boolean
  prepReminderHours?: number
  outreachCooldownDays?: number
  excludedMeetingKeywords?: string[]
}

// =============================================================================
// GREETING MODELS
// =============================================================================

export interface LunaGreeting {
  mode: LunaMode
  message: string
  emphasis?: string
  action?: string
  actionRoute?: string
  pendingCount: number
  urgentCount: number
}

// =============================================================================
// STATS MODELS
// =============================================================================

export interface TodayStats {
  researchCompleted: number
  prepsCompleted: number
  followupsCompleted: number
  outreachSent: number
  totalActions: number
}

export interface LunaStats {
  today: TodayStats
  pendingCount: number
  urgentCount: number
  completedToday: number
}

// =============================================================================
// TIP OF DAY
// =============================================================================

export interface TipOfDay {
  id: string
  content: string
  icon: string
  category: TipCategory
}

// =============================================================================
// UPCOMING MEETING
// =============================================================================

export interface UpcomingMeeting {
  id: string
  title: string
  company?: string
  startTime: string
  startsInHours: number
  hasPrep: boolean
  prospectId?: string
  prepId?: string
}

// =============================================================================
// FEATURE FLAGS
// =============================================================================

export interface FeatureFlagsResponse {
  lunaEnabled: boolean
  lunaShadowMode: boolean
  lunaWidgetEnabled: boolean
  lunaP1Features: boolean
}

// =============================================================================
// OUTREACH MODELS
// =============================================================================

export interface OutreachMessage {
  id: string
  userId: string
  organizationId: string
  prospectId: string
  contactId?: string
  researchId?: string
  channel: OutreachChannel
  status: OutreachStatus
  sentAt?: string
  subject?: string
  body?: string
  payload: Record<string, any>
  createdAt: string
  updatedAt: string
}

export interface OutreachGenerateRequest {
  prospectId: string
  contactId: string
  researchId?: string
  channel: OutreachChannel
  tone?: string
}

export interface OutreachGenerateResponse {
  subject?: string
  body: string
  characterCount: number
}

// =============================================================================
// CONTEXT VALUE
// =============================================================================

export interface LunaContextValue {
  // State
  isLoading: boolean
  isEnabled: boolean
  settings: LunaSettings | null
  messages: LunaMessage[]
  counts: MessageCounts
  stats: LunaStats | null
  greeting: LunaGreeting | null
  tip: TipOfDay | null
  upcomingMeetings: UpcomingMeeting[]
  featureFlags: FeatureFlagsResponse | null
  
  // Actions
  refreshMessages: () => Promise<void>
  refreshStats: () => Promise<void>
  refreshGreeting: () => Promise<void>
  acceptMessage: (id: string) => Promise<void>
  dismissMessage: (id: string) => Promise<void>
  snoozeMessage: (id: string, option: SnoozeOption, customUntil?: string) => Promise<void>
  markMessageShown: (id: string, surface: Surface) => Promise<void>
  updateSettings: (updates: LunaSettingsUpdate) => Promise<void>
  triggerDetection: () => Promise<void>
}
