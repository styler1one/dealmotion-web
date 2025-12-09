/**
 * Types for Follow-up Actions system
 */

export type ActionType = 
  | 'summary'  // Special: auto-generated from followup, not via API
  | 'customer_report'
  | 'share_email'
  | 'commercial_analysis'
  | 'sales_coaching'
  | 'action_items'
  | 'internal_report'

export interface FollowupAction {
  id: string
  followup_id: string
  action_type: ActionType
  content: string | null
  metadata: ActionMetadata
  language: string
  created_at: string
  updated_at: string
  // Computed fields from API
  icon: string
  label: string
  description: string
  word_count: number
}

export interface ActionMetadata {
  status?: 'generating' | 'completed' | 'error'
  error?: string
  word_count?: number
  generated_with_context?: string[]
  // Type-specific fields
  deal_probability?: number
  overall_score?: number
  sections?: string[]
  contact_name?: string
}

export interface ActionTypeInfo {
  type: ActionType
  icon: string
  label: string
  description: string
}

export interface GenerateActionRequest {
  action_type: ActionType
  regenerate?: boolean
}

export interface UpdateActionRequest {
  content?: string
  metadata?: ActionMetadata
}

export interface ActionsListResponse {
  actions: FollowupAction[]
  count: number
}

export interface ActionTypesResponse {
  types: ActionTypeInfo[]
}

// Action type configuration for UI
export const ACTION_TYPES: ActionTypeInfo[] = [
  {
    type: 'summary',
    icon: '📋',
    label: 'Summary',
    description: 'Full meeting summary with key points',
  },
  {
    type: 'share_email',
    icon: '✉️',
    label: 'Follow-up Email',
    description: 'Ready-to-send email to your prospect',
  },
  {
    type: 'action_items',
    icon: '✅',
    label: 'Action Items',
    description: 'Structured tasks with owners and deadlines',
  },
  {
    type: 'commercial_analysis',
    icon: '💰',
    label: 'Deal Analysis',
    description: 'Buying signals, BANT, and deal assessment',
  },
  {
    type: 'customer_report',
    icon: '📄',
    label: 'Client Summary',
    description: 'Professional summary to share with the customer',
  },
  {
    type: 'sales_coaching',
    icon: '🎯',
    label: 'Sales Coaching',
    description: 'Feedback on your sales performance',
  },
  {
    type: 'internal_report',
    icon: '📝',
    label: 'CRM Notes',
    description: 'Short summary for your CRM or team',
  },
]

// Helper to get action type info
export function getActionTypeInfo(type: ActionType): ActionTypeInfo {
  return ACTION_TYPES.find(a => a.type === type) || ACTION_TYPES[0]
}

// Helper to check if action is generating
export function isActionGenerating(action: FollowupAction): boolean {
  return action.metadata?.status === 'generating'
}

// Helper to check if action has error
export function isActionError(action: FollowupAction): boolean {
  return action.metadata?.status === 'error'
}

// Helper to check if action is completed
export function isActionCompleted(action: FollowupAction): boolean {
  return action.metadata?.status === 'completed' && !!action.content
}

