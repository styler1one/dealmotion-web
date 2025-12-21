/**
 * DealMotion Autopilot - TypeScript Types
 * SPEC-045 / TASK-048
 */

// =============================================================================
// ENUMS
// =============================================================================

export type ProposalType =
  | 'research_prep'      // New meeting, unknown org
  | 'prep_only'          // Known prospect, no prep
  | 'followup_pack'      // Post-meeting
  | 'reactivation'       // Silent prospect
  | 'complete_flow'      // Research done, no next step

export type ProposalStatus =
  | 'proposed'
  | 'accepted'
  | 'executing'
  | 'completed'
  | 'declined'
  | 'snoozed'
  | 'expired'
  | 'failed'

export type TriggerType =
  | 'calendar_new_org'
  | 'calendar_known_prospect'
  | 'meeting_ended'
  | 'transcript_ready'
  | 'prospect_silent'
  | 'flow_incomplete'
  | 'manual'

export type NotificationStyle = 'eager' | 'balanced' | 'minimal'

export type OutcomeRating = 'positive' | 'neutral' | 'negative'

export type LunaMode = 'morning' | 'proposal' | 'urgency' | 'celebration' | 'coach'


// =============================================================================
// PROPOSAL
// =============================================================================

export interface SuggestedAction {
  action: string
  params: Record<string, unknown>
}

export interface ProposalArtifact {
  type: 'research' | 'prep' | 'followup' | 'redirect'
  id?: string
  route?: string
  message?: string
}

export interface AutopilotProposal {
  id: string
  organization_id: string
  user_id: string
  proposal_type: ProposalType
  trigger_type: TriggerType
  trigger_entity_id: string | null
  trigger_entity_type: string | null
  title: string
  description: string | null
  luna_message: string
  proposal_reason: string | null  // Why this proposal was created
  suggested_actions: SuggestedAction[]
  status: ProposalStatus
  priority: number
  decided_at: string | null
  decision_reason: string | null
  snoozed_until: string | null
  execution_started_at: string | null
  execution_completed_at: string | null
  execution_result: Record<string, unknown> | null
  execution_error: string | null
  artifacts: ProposalArtifact[]
  expires_at: string | null
  expired_reason: string | null
  context_data: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface ProposalCounts {
  proposed: number
  executing: number
  completed: number
  declined: number
  snoozed: number
  expired: number
  failed: number
}

export interface ProposalsResponse {
  proposals: AutopilotProposal[]
  counts: ProposalCounts
  total: number
}

export interface ProposalActionRequest {
  reason?: string
  snooze_until?: string
}


// =============================================================================
// SETTINGS
// =============================================================================

export interface AutopilotSettings {
  id: string
  user_id: string
  enabled: boolean
  auto_research_new_meetings: boolean
  auto_prep_known_prospects: boolean
  auto_followup_after_meeting: boolean
  reactivation_days_threshold: number
  prep_hours_before_meeting: number
  notification_style: NotificationStyle
  excluded_meeting_keywords: string[]
  created_at: string
  updated_at: string
}

export interface AutopilotSettingsUpdate {
  enabled?: boolean
  auto_research_new_meetings?: boolean
  auto_prep_known_prospects?: boolean
  auto_followup_after_meeting?: boolean
  reactivation_days_threshold?: number
  prep_hours_before_meeting?: number
  notification_style?: NotificationStyle
  excluded_meeting_keywords?: string[]
}


// =============================================================================
// LUNA GREETING
// =============================================================================

export interface LunaGreeting {
  mode: LunaMode
  message: string
  emphasis: string | null
  action: string | null
  action_route: string | null
  pending_count: number
  urgent_count: number
}

export interface UpcomingMeeting {
  id: string
  title: string
  company: string | null
  start_time: string
  starts_in_hours: number
  has_prep: boolean
  prospect_id: string | null
}


// =============================================================================
// STATS
// =============================================================================

export interface AutopilotStats {
  pending_count: number
  urgent_count: number
  completed_today: number
  upcoming_meetings: UpcomingMeeting[]
  luna_greeting: LunaGreeting
}


// =============================================================================
// OUTCOMES
// =============================================================================

export interface AutopilotMeetingOutcome {
  id: string
  organization_id: string
  user_id: string
  calendar_meeting_id: string | null
  preparation_id: string | null
  followup_id: string | null
  prospect_id: string | null
  outcome_rating: OutcomeRating | null
  outcome_source: 'user_input' | 'followup_sentiment' | 'inferred' | null
  prep_viewed: boolean
  prep_view_duration_seconds: number | null
  prep_scroll_depth: number | null
  had_contact_analysis: boolean | null
  had_kb_content: boolean | null
  prep_length_words: number | null
  created_at: string
}

export interface OutcomeRequest {
  outcome_rating: OutcomeRating
  calendar_meeting_id?: string
  preparation_id?: string
  followup_id?: string
  prospect_id?: string
}

export interface PrepViewedRequest {
  preparation_id: string
  view_duration_seconds: number
  scroll_depth: number
}


// =============================================================================
// CONTEXT
// =============================================================================

export interface AutopilotContextValue {
  // State
  isLoading: boolean
  isEnabled: boolean
  proposals: AutopilotProposal[]
  counts: ProposalCounts
  stats: AutopilotStats | null
  settings: AutopilotSettings | null
  
  // Actions
  refreshProposals: () => Promise<void>
  acceptProposal: (id: string, reason?: string) => Promise<void>
  completeProposal: (id: string) => Promise<void>  // For inline actions (skip Inngest)
  declineProposal: (id: string, reason?: string) => Promise<void>
  snoozeProposal: (id: string, until: Date, reason?: string) => Promise<void>
  retryProposal: (id: string) => Promise<void>
  refreshStats: () => Promise<void>
  updateSettings: (updates: AutopilotSettingsUpdate) => Promise<void>
  recordOutcome: (outcome: OutcomeRequest) => Promise<void>
  recordPrepViewed: (data: PrepViewedRequest) => Promise<void>
}


// =============================================================================
// UI HELPERS
// =============================================================================

export const PROPOSAL_STATUS_COLORS: Record<ProposalStatus, string> = {
  proposed: 'bg-yellow-100 text-yellow-800',
  accepted: 'bg-blue-100 text-blue-800',
  executing: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  declined: 'bg-gray-100 text-gray-800',
  snoozed: 'bg-purple-100 text-purple-800',
  expired: 'bg-gray-100 text-gray-500',
  failed: 'bg-red-100 text-red-800',
}

export const PROPOSAL_STATUS_LABELS: Record<ProposalStatus, string> = {
  proposed: 'Actie nodig',
  accepted: 'Geaccepteerd',
  executing: 'Bezig...',
  completed: 'Klaar',
  declined: 'Afgewezen',
  snoozed: 'Uitgesteld',
  expired: 'Verlopen',
  failed: 'Mislukt',
}

export const PROPOSAL_TYPE_ICONS: Record<ProposalType, string> = {
  research_prep: '🔍',
  prep_only: '📋',
  followup_pack: '✉️',
  reactivation: '🔄',
  complete_flow: '➡️',
}

export const LUNA_MODE_ICONS: Record<LunaMode, string> = {
  morning: '☀️',
  proposal: '📬',
  urgency: '⏰',
  celebration: '🎉',
  coach: '💡',
}


// =============================================================================
// SNOOZE OPTIONS
// =============================================================================

export interface SnoozeOption {
  label: string
  getValue: () => Date
}

export const SNOOZE_OPTIONS: SnoozeOption[] = [
  {
    label: '1 hour',
    getValue: () => new Date(Date.now() + 60 * 60 * 1000),
  },
  {
    label: 'This evening',
    getValue: () => {
      const date = new Date()
      date.setHours(20, 0, 0, 0)
      if (date <= new Date()) {
        date.setDate(date.getDate() + 1)
      }
      return date
    },
  },
  {
    label: 'Tomorrow',
    getValue: () => {
      const date = new Date()
      date.setDate(date.getDate() + 1)
      date.setHours(9, 0, 0, 0)
      return date
    },
  },
  {
    label: 'After meeting',
    getValue: () => {
      // Default to 3 hours from now (typical meeting time)
      return new Date(Date.now() + 3 * 60 * 60 * 1000)
    },
  },
  {
    label: 'Next week',
    getValue: () => {
      const date = new Date()
      // Find next Monday
      const daysUntilMonday = (8 - date.getDay()) % 7 || 7
      date.setDate(date.getDate() + daysUntilMonday)
      date.setHours(9, 0, 0, 0)
      return date
    },
  },
  {
    label: 'In 3 days',
    getValue: () => {
      const date = new Date()
      date.setDate(date.getDate() + 3)
      date.setHours(9, 0, 0, 0)
      return date
    },
  },
]
