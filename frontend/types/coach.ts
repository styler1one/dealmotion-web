/**
 * AI Sales Coach "Luna" - TypeScript Types
 * TASK-029 / SPEC-028
 */

// =============================================================================
// ENUMS
// =============================================================================

export type EventType =
  | 'page_view'
  | 'action_completed'
  | 'suggestion_shown'
  | 'suggestion_clicked'
  | 'suggestion_dismissed'
  | 'suggestion_snoozed'
  | 'widget_expanded'
  | 'widget_collapsed'
  | 'settings_changed'

export type SuggestionType =
  | 'add_contacts'
  | 'create_prep'
  | 'create_followup'
  | 'generate_action'
  | 'review_coaching'
  | 'overdue_prospect'
  | 'meeting_reminder'
  | 'complete_profile'
  | 'tip_of_day'

export type SuggestionAction = 'clicked' | 'dismissed' | 'snoozed' | 'expired'

export type PatternType =
  | 'work_hours'
  | 'step_timing'
  | 'preferred_actions'
  | 'dismiss_patterns'
  | 'success_patterns'

export type NotificationFrequency = 'minimal' | 'normal' | 'frequent'

export type WidgetState = 'minimized' | 'compact' | 'expanded' | 'hidden'

export type EntityType = 'research' | 'prep' | 'followup' | 'prospect' | 'deal'


// =============================================================================
// SETTINGS
// =============================================================================

export interface CoachSettings {
  id: string
  user_id: string
  is_enabled: boolean
  show_inline_tips: boolean
  show_completion_modals: boolean
  quiet_hours_start: string | null
  quiet_hours_end: string | null
  notification_frequency: NotificationFrequency
  widget_state: WidgetState
  dismissed_tip_ids: string[]
  created_at: string
  updated_at: string
}

export interface CoachSettingsUpdate {
  is_enabled?: boolean
  show_inline_tips?: boolean
  show_completion_modals?: boolean
  quiet_hours_start?: string | null
  quiet_hours_end?: string | null
  notification_frequency?: NotificationFrequency
  widget_state?: WidgetState
  dismissed_tip_ids?: string[]
}


// =============================================================================
// SUGGESTIONS
// =============================================================================

export interface Suggestion {
  id: string
  user_id: string
  organization_id: string
  suggestion_type: SuggestionType
  title: string
  description: string
  reason: string | null
  priority: number
  action_route: string | null
  action_label: string | null
  icon: string
  related_entity_type: EntityType | null
  related_entity_id: string | null
  shown_at: string
  expires_at: string | null
  action_taken: SuggestionAction | null
  action_taken_at: string | null
  snooze_until: string | null
  feedback_rating: number | null
}

export interface SuggestionsResponse {
  suggestions: Suggestion[]
  count: number
  has_priority: boolean
}

export interface SuggestionActionRequest {
  action: SuggestionAction
  snooze_until?: string
  feedback_rating?: number
}


// =============================================================================
// BEHAVIOR EVENTS
// =============================================================================

export interface BehaviorEventCreate {
  event_type: EventType
  event_data?: Record<string, unknown>
  page_context?: string
}


// =============================================================================
// PATTERNS
// =============================================================================

export interface UserPattern {
  id: string
  user_id: string
  organization_id: string
  pattern_type: PatternType
  pattern_data: Record<string, unknown>
  confidence: number
  sample_size: number
  created_at: string
  updated_at: string
}

export interface PatternsResponse {
  patterns: UserPattern[]
}


// =============================================================================
// STATS
// =============================================================================

export interface TodayStats {
  research_completed: number
  preps_completed: number
  followups_completed: number
  actions_generated: number
  total_completed: number
  streak_days: number
}

export interface CoachStatsResponse {
  today: TodayStats
  suggestions_pending: number
  patterns_learned: number
}


// =============================================================================
// INLINE TIPS
// =============================================================================

export interface InlineTip {
  id: string
  title: string
  description: string
  icon: string
}

export interface InlineSuggestionsResponse {
  suggestions: InlineTip[]
  count: number
}


// =============================================================================
// CONTEXT
// =============================================================================

export interface CoachContextValue {
  // State
  isEnabled: boolean
  isLoading: boolean
  widgetState: WidgetState
  suggestions: Suggestion[]
  stats: CoachStatsResponse | null
  settings: CoachSettings | null
  
  // Actions
  setWidgetState: (state: WidgetState) => void
  refreshSuggestions: () => Promise<void>
  dismissSuggestion: (id: string) => Promise<void>
  snoozeSuggestion: (id: string, until: Date) => Promise<void>
  clickSuggestion: (id: string) => Promise<void>
  trackEvent: (type: EventType, data?: Record<string, unknown>) => Promise<void>
  updateSettings: (updates: CoachSettingsUpdate) => Promise<void>
  
  // Inline Tips
  dismissTipId: (tipId: string) => Promise<void>
  isDismissed: (tipId: string) => boolean
}


// =============================================================================
// SNOOZE OPTIONS
// =============================================================================

export interface SnoozeOption {
  label: string
  duration: number // minutes
}

export const SNOOZE_OPTIONS: SnoozeOption[] = [
  { label: '1 hour', duration: 60 },
  { label: 'Tonight', duration: getMinutesUntilTonight() },
  { label: 'Tomorrow', duration: getMinutesUntilTomorrow() },
]

function getMinutesUntilTonight(): number {
  const now = new Date()
  const tonight = new Date(now)
  tonight.setHours(20, 0, 0, 0) // 8 PM
  if (tonight <= now) {
    tonight.setDate(tonight.getDate() + 1)
  }
  return Math.ceil((tonight.getTime() - now.getTime()) / 60000)
}

function getMinutesUntilTomorrow(): number {
  const now = new Date()
  const tomorrow = new Date(now)
  tomorrow.setDate(tomorrow.getDate() + 1)
  tomorrow.setHours(9, 0, 0, 0) // 9 AM tomorrow
  return Math.ceil((tomorrow.getTime() - now.getTime()) / 60000)
}

