/**
 * AI Notetaker Types
 * SPEC-043: AI Notetaker / Recall.ai Integration
 */

export type RecordingStatus = 
  | 'scheduled'
  | 'joining'
  | 'waiting_room'
  | 'recording'
  | 'processing'
  | 'complete'
  | 'error'
  | 'cancelled'

export type MeetingPlatform = 'teams' | 'meet' | 'zoom' | 'webex'

export interface ScheduledRecording {
  id: string
  recall_bot_id: string | null
  status: RecordingStatus
  meeting_url: string
  meeting_title: string | null
  meeting_platform: MeetingPlatform | null
  scheduled_time: string
  prospect_id: string | null
  prospect_name: string | null
  followup_id: string | null
  duration_seconds: number | null
  created_at: string
}

export interface ScheduleRecordingRequest {
  meeting_url: string
  scheduled_time?: string // ISO string, null = join immediately
  meeting_title?: string
  prospect_id?: string
  // Context fields (same as regular followup)
  meeting_prep_id?: string
  contact_ids?: string[]
  deal_id?: string
  calendar_meeting_id?: string
}

export interface ScheduleRecordingResponse {
  id: string
  recall_bot_id: string | null
  status: RecordingStatus
  meeting_url: string
  meeting_title: string | null
  meeting_platform: MeetingPlatform
  scheduled_time: string
  prospect_id: string | null
  prospect_name: string | null
}

export interface ScheduledRecordingsResponse {
  recordings: ScheduledRecording[]
}

export interface CancelRecordingResponse {
  success: boolean
  message: string
}

// UI status info for display
export const RECORDING_STATUS_INFO: Record<RecordingStatus, {
  label: string
  color: string
  icon: string
  animate?: boolean
}> = {
  scheduled: {
    label: 'Scheduled',
    color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    icon: 'clock'
  },
  joining: {
    label: 'Joining meeting...',
    color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    icon: 'loader',
    animate: true
  },
  waiting_room: {
    label: 'In waiting room',
    color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    icon: 'clock',
    animate: true
  },
  recording: {
    label: 'Recording...',
    color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    icon: 'mic',
    animate: true
  },
  processing: {
    label: 'Processing...',
    color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
    icon: 'loader',
    animate: true
  },
  complete: {
    label: 'Complete',
    color: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    icon: 'check'
  },
  error: {
    label: 'Error',
    color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    icon: 'alertTriangle'
  },
  cancelled: {
    label: 'Cancelled',
    color: 'bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-400',
    icon: 'x'
  }
}

// Platform display info
export const PLATFORM_INFO: Record<MeetingPlatform, {
  label: string
  icon: string
  color: string
}> = {
  teams: {
    label: 'Microsoft Teams',
    icon: '🟣',
    color: 'text-purple-600'
  },
  meet: {
    label: 'Google Meet',
    icon: '🟢',
    color: 'text-green-600'
  },
  zoom: {
    label: 'Zoom',
    icon: '🔵',
    color: 'text-blue-600'
  },
  webex: {
    label: 'Webex',
    icon: '🟠',
    color: 'text-orange-600'
  }
}

