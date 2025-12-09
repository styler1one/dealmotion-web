/**
 * Activity type constants and helpers
 * 
 * Use these for consistent activity type handling across the app.
 */

import { ActivityType } from '@/types'

// ===========================================
// Activity Icons
// ===========================================

export const ACTIVITY_ICONS: Record<ActivityType | string, string> = {
  research: '🔍',
  prep: '📋',
  followup: '📝',
  meeting: '📅',
  deal_created: '🎯',
  contact_added: '👤',
  note: '📌',
} as const

/**
 * Get icon for an activity type
 * Falls back to a default icon if type is unknown
 */
export function getActivityIcon(type: string, fallback?: string): string {
  return ACTIVITY_ICONS[type] || fallback || '📌'
}

// ===========================================
// Activity Colors (for badges/UI)
// ===========================================

export const ACTIVITY_COLORS: Record<ActivityType | string, { bg: string; text: string }> = {
  research: { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-700 dark:text-blue-400' },
  prep: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-400' },
  followup: { bg: 'bg-orange-100 dark:bg-orange-900/30', text: 'text-orange-700 dark:text-orange-400' },
  meeting: { bg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-700 dark:text-purple-400' },
  deal_created: { bg: 'bg-indigo-100 dark:bg-indigo-900/30', text: 'text-indigo-700 dark:text-indigo-400' },
  contact_added: { bg: 'bg-teal-100 dark:bg-teal-900/30', text: 'text-teal-700 dark:text-teal-400' },
  note: { bg: 'bg-slate-100 dark:bg-slate-800', text: 'text-slate-700 dark:text-slate-400' },
} as const

/**
 * Get colors for an activity type
 */
export function getActivityColors(type: string): { bg: string; text: string } {
  return ACTIVITY_COLORS[type] || ACTIVITY_COLORS.note
}

// ===========================================
// Meeting Status
// ===========================================

export type MeetingStatusType = 'scheduled' | 'completed' | 'cancelled' | 'no_show'

export const MEETING_STATUS_COLORS: Record<MeetingStatusType, { bg: string; text: string }> = {
  scheduled: { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-700 dark:text-blue-400' },
  completed: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-400' },
  cancelled: { bg: 'bg-slate-100 dark:bg-slate-800', text: 'text-slate-700 dark:text-slate-400' },
  no_show: { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-400' },
} as const

// ===========================================
// Prospect Status
// ===========================================

export type ProspectStatusType = 
  | 'new' 
  | 'researching' 
  | 'qualified' 
  | 'meeting_scheduled' 
  | 'proposal_sent' 
  | 'won' 
  | 'lost' 
  | 'on_hold'

export const PROSPECT_STATUS_COLORS: Record<ProspectStatusType, string> = {
  new: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  researching: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  qualified: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  meeting_scheduled: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  proposal_sent: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  won: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  lost: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  on_hold: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400',
} as const

/**
 * Get status color classes for a prospect
 */
export function getProspectStatusColor(status: string): string {
  return PROSPECT_STATUS_COLORS[status as ProspectStatusType] || PROSPECT_STATUS_COLORS.new
}

// ===========================================
// Meeting Types
// ===========================================

export const MEETING_TYPES = [
  'discovery',
  'demo',
  'negotiation',
  'closing',
  'review',
  'other',
] as const

export type SalesMeetingType = typeof MEETING_TYPES[number]

