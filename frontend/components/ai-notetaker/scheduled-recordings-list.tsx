'use client'

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { api } from '@/lib/api'
import { logger } from '@/lib/logger'
import { 
  ScheduledRecording, 
  ScheduledRecordingsResponse,
  RECORDING_STATUS_INFO,
  PLATFORM_INFO,
  RecordingStatus
} from '@/types/ai-notetaker'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

interface ScheduledRecordingsListProps {
  onScheduleClick?: () => void
  maxItems?: number
  refreshTrigger?: number
}

export function ScheduledRecordingsList({
  onScheduleClick,
  maxItems = 5,
  refreshTrigger = 0
}: ScheduledRecordingsListProps) {
  const t = useTranslations('aiNotetaker')
  const tCommon = useTranslations('common')
  const router = useRouter()
  const { toast } = useToast()

  const [recordings, setRecordings] = useState<ScheduledRecording[]>([])
  const [loading, setLoading] = useState(true)
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
  const [recordingToCancel, setRecordingToCancel] = useState<ScheduledRecording | null>(null)
  const [cancelling, setCancelling] = useState(false)

  // Fetch scheduled recordings
  const fetchRecordings = async () => {
    try {
      const { data } = await api.get<ScheduledRecordingsResponse>('/api/v1/ai-notetaker/scheduled')
      if (data?.recordings) {
        setRecordings(data.recordings.slice(0, maxItems))
      }
    } catch (error) {
      logger.error('Failed to fetch scheduled recordings', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchRecordings()
    
    // Auto-refresh for active recordings
    const interval = setInterval(() => {
      const hasActive = recordings.some(r => 
        ['joining', 'waiting_room', 'recording', 'processing'].includes(r.status)
      )
      if (hasActive) {
        fetchRecordings()
      }
    }, 10000) // Every 10 seconds
    
    return () => clearInterval(interval)
  }, [refreshTrigger])

  // Handle cancel
  const handleCancel = async () => {
    if (!recordingToCancel) return
    
    setCancelling(true)
    try {
      const { data, error } = await api.delete<{ success: boolean; message: string }>(
        `/api/v1/ai-notetaker/${recordingToCancel.id}`
      )
      
      if (error || !data?.success) {
        throw new Error(data?.message || 'Failed to cancel')
      }
      
      toast({ title: 'Recording cancelled' })
      fetchRecordings()
    } catch (error) {
      logger.error('Failed to cancel recording', error)
      toast({
        title: 'Failed to cancel',
        variant: 'destructive'
      })
    } finally {
      setCancelling(false)
      setCancelDialogOpen(false)
      setRecordingToCancel(null)
    }
  }

  // Format date/time
  const formatDateTime = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const isToday = date.toDateString() === now.toDateString()
    const tomorrow = new Date(now)
    tomorrow.setDate(tomorrow.getDate() + 1)
    const isTomorrow = date.toDateString() === tomorrow.toDateString()
    
    const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    
    if (isToday) return `Today, ${time}`
    if (isTomorrow) return `Tomorrow, ${time}`
    return `${date.toLocaleDateString([], { month: 'short', day: 'numeric' })}, ${time}`
  }

  // Get status icon
  const getStatusIcon = (status: RecordingStatus) => {
    const info = RECORDING_STATUS_INFO[status]
    const iconName = info.icon as keyof typeof Icons
    const Icon = Icons[iconName] || Icons.clock
    return <Icon className={`h-3 w-3 ${info.animate ? 'animate-spin' : ''}`} />
  }

  if (loading) {
    return (
      <div className="p-4 text-center">
        <Icons.spinner className="h-5 w-5 animate-spin mx-auto text-slate-400" />
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <h3 className="font-medium text-sm text-slate-900 dark:text-slate-100 flex items-center gap-2">
        <Icons.calendar className="h-4 w-4" />
        {t('scheduled.title')}
      </h3>

      {recordings.length === 0 ? (
        <div className="text-center py-4">
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-3">
            {t('scheduled.empty')}
          </p>
          {onScheduleClick && (
            <Button
              variant="outline"
              size="sm"
              onClick={onScheduleClick}
              className="text-xs"
            >
              <Icons.fileText className="h-3 w-3 mr-1" />
              {t('title')}
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {recordings.map((recording) => {
            const statusInfo = RECORDING_STATUS_INFO[recording.status]
            const platformInfo = recording.meeting_platform 
              ? PLATFORM_INFO[recording.meeting_platform] 
              : null
            
            return (
              <div
                key={recording.id}
                className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-3 group"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    {/* Title */}
                    <p className="font-medium text-sm text-slate-900 dark:text-slate-100 truncate">
                      {recording.meeting_title || recording.prospect_name || 'Untitled Meeting'}
                    </p>
                    
                    {/* Time and platform */}
                    <div className="flex items-center gap-2 mt-1 text-xs text-slate-500 dark:text-slate-400">
                      <span>{formatDateTime(recording.scheduled_time)}</span>
                      {platformInfo && (
                        <>
                          <span>•</span>
                          <span>{platformInfo.icon} {platformInfo.label.split(' ')[0]}</span>
                        </>
                      )}
                    </div>
                    
                    {/* Status badge */}
                    <div className="mt-2">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${statusInfo.color}`}>
                        {getStatusIcon(recording.status)}
                        {statusInfo.label}
                      </span>
                    </div>
                  </div>
                  
                  {/* Actions */}
                  <div className="flex-shrink-0">
                    {recording.status === 'scheduled' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-slate-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => {
                          setRecordingToCancel(recording)
                          setCancelDialogOpen(true)
                        }}
                      >
                        <Icons.x className="h-4 w-4" />
                      </Button>
                    )}
                    {recording.status === 'complete' && recording.followup_id && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => router.push(`/dashboard/followup/${recording.followup_id}`)}
                      >
                        View →
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Cancel Dialog */}
      <AlertDialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('scheduled.cancelConfirm')}</AlertDialogTitle>
            <AlertDialogDescription>
              This will cancel the AI Notetaker for this meeting. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={cancelling}>
              {tCommon('cancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleCancel}
              disabled={cancelling}
              className="bg-red-600 hover:bg-red-700"
            >
              {cancelling ? (
                <Icons.spinner className="h-4 w-4 animate-spin mr-2" />
              ) : null}
              {t('scheduled.cancel')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

