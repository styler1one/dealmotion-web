'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/date-utils'
import { logger } from '@/lib/logger'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { Toaster } from '@/components/ui/toaster'
import { DashboardLayout } from '@/components/layout'
import { useTranslations } from 'next-intl'
import { useSettings } from '@/lib/settings-context'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { User } from '@supabase/supabase-js'
import { ImportRecordingModal } from '@/components/import-recording-modal'
import { FollowupUploadForm } from '@/components/forms'
import { BrowserRecording } from '@/components/browser-recording'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
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

// Transcript data interface
interface TranscriptData {
  id: string
  title: string | null
  transcript_text: string | null
  recording_date: string | null
  duration_seconds: number | null
  participants: string[]
  provider: string
}

// Interface for ImportRecordingModal compatibility
interface ExternalRecordingForModal {
  id: string
  provider: string
  external_id: string
  title: string | null
  recording_date: string
  duration_seconds: number | null
  participants: string[]
  matched_meeting_id: string | null
  matched_prospect_id: string | null
}

interface UnifiedRecording {
  id: string
  source: string
  source_table: string
  title: string | null
  prospect_id: string | null
  prospect_name: string | null
  duration_seconds: number | null
  file_size_bytes: number | null
  status: string
  error: string | null
  followup_id: string | null
  audio_url: string | null
  recorded_at: string | null
  created_at: string
  processed_at: string | null
}

interface RecordingsResponse {
  recordings: UnifiedRecording[]
  total: number
  sources: Record<string, number>
}

interface RecordingsStats {
  total_recordings: number
  pending_count: number
  processing_count: number
  completed_count: number
  failed_count: number
  by_source: Record<string, number>
}

const SOURCE_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  mobile: { label: 'Mobile App', icon: '📱', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-400' },
  fireflies: { label: 'Fireflies', icon: '🔥', color: 'bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-400' },
  teams: { label: 'Teams', icon: '💼', color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-400' },
  zoom: { label: 'Zoom', icon: '📹', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-400' },
  web_upload: { label: 'Web Upload', icon: '🌐', color: 'bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-400' },
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending: { label: 'Pending', color: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/50 dark:text-yellow-400' },
  processing: { label: 'Processing', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-400' },
  completed: { label: 'Completed', color: 'bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-400' },
  failed: { label: 'Failed', color: 'bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-400' },
}

export default function RecordingsPage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const t = useTranslations('recordings')
  const tCommon = useTranslations('common')
  const { settings } = useSettings()
  
  const [user, setUser] = useState<User | null>(null)
  const [recordings, setRecordings] = useState<UnifiedRecording[]>([])
  const [stats, setStats] = useState<RecordingsStats | null>(null)
  const [loading, setLoading] = useState(true)
  
  // Filters
  const [sourceFilter, setSourceFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  
  // Import modal state
  const [selectedRecordingForImport, setSelectedRecordingForImport] = useState<ExternalRecordingForModal | null>(null)
  const [isImportModalOpen, setIsImportModalOpen] = useState(false)
  
  // Upload sheet state
  const [uploadSheetOpen, setUploadSheetOpen] = useState(false)
  
  // Transcript sheet state
  const [transcriptSheetOpen, setTranscriptSheetOpen] = useState(false)
  const [selectedTranscript, setSelectedTranscript] = useState<TranscriptData | null>(null)
  const [loadingTranscript, setLoadingTranscript] = useState(false)
  const [editedTranscript, setEditedTranscript] = useState<string>('')
  const [savingTranscript, setSavingTranscript] = useState(false)
  const [transcriptDirty, setTranscriptDirty] = useState(false)
  
  // Recording sheet state  
  const [recordingSheetOpen, setRecordingSheetOpen] = useState(false)
  
  // Delete confirmation state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [recordingToDelete, setRecordingToDelete] = useState<UnifiedRecording | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Recording context selection
  const [recordingProspects, setRecordingProspects] = useState<Array<{id: string; company_name: string}>>([])
  const [selectedRecordingProspect, setSelectedRecordingProspect] = useState<{id: string; company_name: string} | null>(null)
  const [recordingPreparations, setRecordingPreparations] = useState<Array<{id: string; meeting_subject: string}>>([])
  const [selectedRecordingPrep, setSelectedRecordingPrep] = useState<{id: string; meeting_subject: string} | null>(null)
  const [recordingContacts, setRecordingContacts] = useState<Array<{id: string; name: string}>>([])
  const [selectedRecordingContacts, setSelectedRecordingContacts] = useState<Array<{id: string; name: string}>>([])
  const [loadingRecordingContext, setLoadingRecordingContext] = useState(false)
  
  const fetchRecordings = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      if (sourceFilter !== 'all') params.append('source', sourceFilter)
      if (statusFilter !== 'all') params.append('status', statusFilter)
      params.append('limit', '100')
      
      const { data, error } = await api.get<RecordingsResponse>(`/api/v1/recordings?${params.toString()}`)
      
      if (!error && data) {
        setRecordings(data.recordings)
      }
    } catch (error) {
      logger.error('Error fetching recordings', error)
    } finally {
      setLoading(false)
    }
  }, [sourceFilter, statusFilter])

  const fetchStats = useCallback(async () => {
    try {
      const { data, error } = await api.get<RecordingsStats>('/api/v1/recordings/stats')
      if (!error && data) {
        setStats(data)
      }
    } catch (error) {
      logger.error('Error fetching stats', error)
    }
  }, [])

  // Fetch prospects for recording context
  const fetchRecordingProspects = useCallback(async () => {
    try {
      const { data, error } = await api.get<{ prospects: Array<{id: string; company_name: string}> }>('/api/v1/prospects?limit=100')
      if (!error && data) {
        setRecordingProspects(data.prospects || [])
      }
    } catch (error) {
      logger.error('Error fetching prospects for recording', error)
    }
  }, [])

  // Fetch preps and contacts when prospect is selected
  const fetchProspectContext = useCallback(async (prospectId: string) => {
    setLoadingRecordingContext(true)
    setRecordingPreparations([])
    setSelectedRecordingPrep(null)
    setRecordingContacts([])
    setSelectedRecordingContacts([])
    
    try {
      const { data, error } = await api.get<{
        preps?: Array<{id: string; meeting_subject?: string; status: string}>
        contacts?: Array<{id: string; name: string}>
      }>(`/api/v1/prospects/${prospectId}/hub`)
      
      if (!error && data) {
        // Only show completed preparations
        const completedPreps = (data.preps || [])
          .filter(p => p.status === 'completed')
          .map(p => ({ id: p.id, meeting_subject: p.meeting_subject || 'Preparation' }))
        setRecordingPreparations(completedPreps)
        
        // Set contacts
        setRecordingContacts(data.contacts || [])
      }
    } catch (error) {
      logger.error('Error fetching prospect context', error)
    } finally {
      setLoadingRecordingContext(false)
    }
  }, [])

  const recordingsRef = useRef<UnifiedRecording[]>([])
  recordingsRef.current = recordings

  useEffect(() => {
    Promise.all([
      supabase.auth.getUser().then(({ data: { user } }) => setUser(user)),
      fetchRecordings(),
      fetchStats(),
    ])
  }, [fetchRecordings, fetchStats])

  // Fetch prospects when recording sheet opens
  useEffect(() => {
    if (recordingSheetOpen && recordingProspects.length === 0) {
      fetchRecordingProspects()
    }
  }, [recordingSheetOpen, recordingProspects.length, fetchRecordingProspects])

  // Fetch context when prospect is selected
  useEffect(() => {
    if (selectedRecordingProspect) {
      fetchProspectContext(selectedRecordingProspect.id)
    }
  }, [selectedRecordingProspect, fetchProspectContext])

  // Auto-refresh for processing recordings
  useEffect(() => {
    const interval = setInterval(() => {
      const hasProcessing = recordingsRef.current.some(r => 
        ['pending', 'processing'].includes(r.status)
      )
      if (hasProcessing) {
        fetchRecordings()
        fetchStats()
      }
    }, 5000)
    
    return () => clearInterval(interval)
  }, [fetchRecordings, fetchStats])

  // Refetch when filters change
  useEffect(() => {
    setLoading(true)
    fetchRecordings()
  }, [sourceFilter, statusFilter, fetchRecordings])

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-'
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const formatFileSize = (bytes: number | null) => {
    if (!bytes) return '-'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  // Handle analyze button click - opens import modal for external recordings
  const handleAnalyze = (recording: UnifiedRecording) => {
    // Convert to format expected by ImportRecordingModal
    const modalRecording: ExternalRecordingForModal = {
      id: recording.id,
      provider: recording.source,
      external_id: recording.id,
      title: recording.title,
      recording_date: recording.recorded_at || recording.created_at,
      duration_seconds: recording.duration_seconds,
      participants: [], // We don't have this in unified format
      matched_meeting_id: null,
      matched_prospect_id: recording.prospect_id,
    }
    setSelectedRecordingForImport(modalRecording)
    setIsImportModalOpen(true)
  }

  // Handle successful import from modal
  const handleImported = (followupId: string) => {
    setIsImportModalOpen(false)
    setSelectedRecordingForImport(null)
    // Refresh data
    fetchRecordings()
    fetchStats()
    // Navigate to the new followup
    router.push(`/dashboard/followup/${followupId}`)
  }

  // Handle successful upload from sheet
  const handleUploadSuccess = (result?: { id: string; prospect_id?: string }) => {
    setUploadSheetOpen(false)
    // Refresh data
    fetchRecordings()
    fetchStats()
    // Navigate to the new followup if we have the id
    if (result?.id) {
      router.push(`/dashboard/followup/${result.id}`)
    }
  }

  // Handle view transcript
  const handleViewTranscript = async (recording: UnifiedRecording) => {
    setLoadingTranscript(true)
    setTranscriptSheetOpen(true)
    setTranscriptDirty(false)
    
    try {
      const { data, error } = await api.get<TranscriptData>(`/api/v1/recordings/transcript/${recording.id}`)
      
      if (error || !data) {
        toast({
          title: t('transcript.loadFailed'),
          description: error?.message || 'Failed to load transcript',
          variant: 'destructive',
        })
        setSelectedTranscript(null)
        setEditedTranscript('')
      } else {
        setSelectedTranscript(data)
        setEditedTranscript(data.transcript_text || '')
      }
    } catch (err) {
      logger.error('Failed to fetch transcript:', err)
      toast({
        title: t('transcript.loadFailed'),
        variant: 'destructive',
      })
    } finally {
      setLoadingTranscript(false)
    }
  }

  // Handle save transcript
  const handleSaveTranscript = async () => {
    if (!selectedTranscript) return
    
    setSavingTranscript(true)
    try {
      const { data, error } = await api.put<{ success: boolean; message: string }>(
        `/api/v1/recordings/transcript/${selectedTranscript.id}`,
        { transcript_text: editedTranscript }
      )
      
      if (error || !data?.success) {
        toast({
          title: t('transcript.saveFailed'),
          description: error?.message || data?.message || 'Failed to save',
          variant: 'destructive',
        })
      } else {
        toast({
          title: t('transcript.saved'),
        })
        setTranscriptDirty(false)
        // Update the selected transcript with new text
        setSelectedTranscript({
          ...selectedTranscript,
          transcript_text: editedTranscript
        })
      }
    } catch (err) {
      logger.error('Failed to save transcript:', err)
      toast({
        title: t('transcript.saveFailed'),
        variant: 'destructive',
      })
    } finally {
      setSavingTranscript(false)
    }
  }

  // Handle recording complete from browser recording
  const handleRecordingComplete = (followupId: string) => {
    setRecordingSheetOpen(false)
    fetchRecordings()
    fetchStats()
    router.push(`/dashboard/followup/${followupId}`)
  }

  const handleRecordingClick = (recording: UnifiedRecording) => {
    // If completed and has followup, go to followup detail
    if (recording.followup_id) {
      router.push(`/dashboard/followup/${recording.followup_id}`)
    } else if (recording.prospect_id) {
      // Otherwise go to prospect hub
      router.push(`/dashboard/prospects/${recording.prospect_id}`)
    }
  }

  // Handle delete recording
  const handleDeleteRecording = async () => {
    if (!recordingToDelete) return
    
    setDeleting(true)
    try {
      const { data, error } = await api.delete<{ success: boolean; message: string }>(
        `/api/v1/recordings/${recordingToDelete.source_table}/${recordingToDelete.id}`
      )
      
      if (error || !data?.success) {
        toast({
          title: t('delete.failed'),
          description: error?.message || data?.message || 'Failed to delete',
          variant: 'destructive',
        })
      } else {
        toast({
          title: t('delete.success'),
        })
        // Refresh data
        fetchRecordings()
        fetchStats()
      }
    } catch (err) {
      logger.error('Failed to delete recording:', err)
      toast({
        title: t('delete.failed'),
        variant: 'destructive',
      })
    } finally {
      setDeleting(false)
      setDeleteDialogOpen(false)
      setRecordingToDelete(null)
    }
  }

  if (loading) {
    return (
      <DashboardLayout user={user}>
        <div className="flex items-center justify-center h-full">
          <div className="text-center space-y-4">
            <Icons.spinner className="h-8 w-8 animate-spin text-orange-600 mx-auto" />
            <p className="text-slate-500 dark:text-slate-400">{t('loading')}</p>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout user={user}>
      <div className="p-4 lg:p-6">
        {/* Page Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">
            {t('title')}
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            {t('subtitle')}
          </p>
        </div>

        {/* Two Column Layout */}
        <div className="flex gap-6">
          
          {/* Left Column - Recordings List */}
          <div className="flex-1 min-w-0">
            {/* Filters */}
            <div className="flex items-center gap-3 mb-4">
              <Select value={sourceFilter} onValueChange={setSourceFilter}>
                <SelectTrigger className="w-[160px]">
                  <SelectValue placeholder={t('filters.allSources')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('filters.allSources')}</SelectItem>
                  <SelectItem value="mobile">📱 Mobile App</SelectItem>
                  <SelectItem value="fireflies">🔥 Fireflies</SelectItem>
                  <SelectItem value="teams">💼 Teams</SelectItem>
                  <SelectItem value="zoom">📹 Zoom</SelectItem>
                  <SelectItem value="web_upload">🌐 Web Upload</SelectItem>
                </SelectContent>
              </Select>

              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder={t('filters.allStatus')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('filters.allStatus')}</SelectItem>
                  <SelectItem value="pending">{t('status.pending')}</SelectItem>
                  <SelectItem value="processing">{t('status.processing')}</SelectItem>
                  <SelectItem value="completed">{t('status.completed')}</SelectItem>
                  <SelectItem value="failed">{t('status.failed')}</SelectItem>
                </SelectContent>
              </Select>

              <div className="flex-1" />

              <Button variant="ghost" size="sm" onClick={() => { fetchRecordings(); fetchStats(); }}>
                <Icons.refresh className="h-4 w-4" />
              </Button>
            </div>

            {recordings.length === 0 ? (
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-12 text-center">
                <Icons.mic className="h-16 w-16 text-slate-200 dark:text-slate-700 mx-auto mb-4" />
                <h3 className="font-semibold text-slate-700 dark:text-slate-200 mb-2">{t('empty.title')}</h3>
                <p className="text-slate-500 dark:text-slate-400 text-sm mb-4">
                  {t('empty.description')}
                </p>
                <div className="flex justify-center gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setUploadSheetOpen(true)}
                  >
                    <Icons.upload className="h-4 w-4 mr-2" />
                    {t('empty.uploadWeb')}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => router.push('/dashboard/settings')}
                  >
                    <Icons.settings className="h-4 w-4 mr-2" />
                    {t('empty.connectIntegration')}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {recordings.map((recording) => {
                  const sourceInfo = SOURCE_LABELS[recording.source] || { label: recording.source, icon: '📁', color: 'bg-slate-100 text-slate-700' }
                  const statusInfo = STATUS_LABELS[recording.status] || { label: recording.status, color: 'bg-slate-100 text-slate-700' }
                  const isClickable = recording.followup_id || recording.prospect_id

                  return (
                    <div
                      key={`${recording.source_table}-${recording.id}`}
                      className={`bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 hover:shadow-md dark:hover:shadow-slate-800/50 transition-all group ${isClickable ? 'cursor-pointer' : ''}`}
                      onClick={() => isClickable && handleRecordingClick(recording)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            {/* Source badge */}
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${sourceInfo.color}`}>
                              {sourceInfo.icon} {sourceInfo.label}
                            </span>
                            
                            {/* Status badge */}
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusInfo.color}`}>
                              {recording.status === 'processing' && <Icons.spinner className="h-3 w-3 animate-spin" />}
                              {recording.status === 'completed' && <Icons.check className="h-3 w-3" />}
                              {recording.status === 'failed' && <Icons.alertCircle className="h-3 w-3" />}
                              {statusInfo.label}
                            </span>
                          </div>

                          <h4 className="font-semibold text-slate-900 dark:text-white truncate mt-2">
                            {recording.title || recording.prospect_name || t('untitled')}
                          </h4>
                          
                          {recording.prospect_name && recording.title && (
                            <p className="text-sm text-slate-500 dark:text-slate-400 truncate">
                              {recording.prospect_name}
                            </p>
                          )}
                          
                          <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400 mt-2">
                            {recording.duration_seconds && (
                              <span className="flex items-center gap-1">
                                <Icons.clock className="h-3 w-3" />
                                {formatDuration(recording.duration_seconds)}
                              </span>
                            )}
                            {recording.file_size_bytes && (
                              <span className="flex items-center gap-1">
                                <Icons.fileText className="h-3 w-3" />
                                {formatFileSize(recording.file_size_bytes)}
                              </span>
                            )}
                            <span>
                              {formatDate(recording.recorded_at || recording.created_at, settings.output_language)}
                            </span>
                          </div>

                          {recording.error && (
                            <p className="text-xs text-red-500 dark:text-red-400 mt-2 line-clamp-1">
                              {recording.error}
                            </p>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-1 ml-4">
                          {/* View Transcript button for external recordings */}
                          {recording.source_table === 'external_recordings' && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-8 text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleViewTranscript(recording)
                              }}
                            >
                              <Icons.fileText className="h-3 w-3 mr-1" />
                              {t('viewTranscript')}
                            </Button>
                          )}
                          {/* Analyze button for external recordings not yet imported */}
                          {!recording.followup_id && recording.source_table === 'external_recordings' && (
                            <Button
                              variant="default"
                              size="sm"
                              className="h-8 text-xs bg-orange-600 hover:bg-orange-700 opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleAnalyze(recording)
                              }}
                            >
                              <Icons.sparkles className="h-3 w-3 mr-1" />
                              {t('analyze')}
                            </Button>
                          )}
                          {/* View Analysis button for already analyzed recordings */}
                          {recording.followup_id && (
                            <Button
                              variant="default"
                              size="sm"
                              className="h-8 text-xs bg-orange-600 hover:bg-orange-700 opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => {
                                e.stopPropagation()
                                router.push(`/dashboard/followup/${recording.followup_id}`)
                              }}
                            >
                              <Icons.eye className="h-3 w-3 mr-1" />
                              {t('viewAnalysis')}
                            </Button>
                          )}
                          {!recording.followup_id && recording.prospect_id && recording.source_table !== 'external_recordings' && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-8 text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => {
                                e.stopPropagation()
                                router.push(`/dashboard/prospects/${recording.prospect_id}`)
                              }}
                            >
                              <Icons.building className="h-3 w-3 mr-1" />
                              Hub
                            </Button>
                          )}
                          {/* Delete button */}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0 text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={(e) => {
                              e.stopPropagation()
                              setRecordingToDelete(recording)
                              setDeleteDialogOpen(true)
                            }}
                          >
                            <Icons.trash className="h-4 w-4" />
                          </Button>
                          {isClickable && (
                            <Icons.chevronRight className="h-5 w-5 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Right Column - Sticky Sidebar */}
          <div className="w-80 flex-shrink-0 hidden lg:block">
            <div className="sticky top-4 space-y-4">
              
              {/* Stats Panel */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <Icons.barChart className="h-4 w-4 text-slate-400" />
                  {t('stats.title')}
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-green-50 dark:bg-green-900/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-green-600 dark:text-green-400">{stats?.completed_count || 0}</p>
                    <p className="text-xs text-green-700 dark:text-green-300">{t('status.completed')}</p>
                  </div>
                  <div className="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{stats?.processing_count || 0}</p>
                    <p className="text-xs text-blue-700 dark:text-blue-300">{t('status.processing')}</p>
                  </div>
                  <div className="bg-yellow-50 dark:bg-yellow-900/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{stats?.pending_count || 0}</p>
                    <p className="text-xs text-yellow-700 dark:text-yellow-300">{t('status.pending')}</p>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-slate-600 dark:text-slate-400">{stats?.total_recordings || 0}</p>
                    <p className="text-xs text-slate-600 dark:text-slate-400">{t('stats.total')}</p>
                  </div>
                </div>
              </div>

              {/* Sources Breakdown */}
              {stats && Object.keys(stats.by_source).length > 0 && (
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                    <Icons.folderOpen className="h-4 w-4 text-slate-400" />
                    {t('stats.bySources')}
                  </h3>
                  <div className="space-y-2">
                    {Object.entries(stats.by_source).map(([source, count]) => {
                      const sourceInfo = SOURCE_LABELS[source] || { label: source, icon: '📁', color: '' }
                      return (
                        <div key={source} className="flex items-center justify-between">
                          <span className="text-sm text-slate-600 dark:text-slate-400 flex items-center gap-2">
                            <span>{sourceInfo.icon}</span>
                            {sourceInfo.label}
                          </span>
                          <span className="text-sm font-medium text-slate-900 dark:text-white">{count}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Quick Actions */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-gradient-to-br from-orange-50 to-amber-50 dark:from-orange-950 dark:to-amber-950 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <Icons.zap className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                  {t('quickActions.title')}
                </h3>
                <div className="space-y-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start"
                    onClick={() => setUploadSheetOpen(true)}
                  >
                    <Icons.upload className="h-4 w-4 mr-2" />
                    {t('quickActions.uploadRecording')}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700 dark:text-red-400 dark:border-red-800 dark:hover:bg-red-900/20"
                    onClick={() => setRecordingSheetOpen(true)}
                  >
                    <Icons.mic className="h-4 w-4 mr-2" />
                    {t('quickActions.startRecording')}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start"
                    onClick={() => router.push('/dashboard/settings')}
                  >
                    <Icons.settings className="h-4 w-4 mr-2" />
                    {t('quickActions.manageIntegrations')}
                  </Button>
                </div>
              </div>

            </div>
          </div>
        </div>

        <Toaster />

        {/* Import Recording Modal */}
        <ImportRecordingModal
          isOpen={isImportModalOpen}
          onClose={() => {
            setIsImportModalOpen(false)
            setSelectedRecordingForImport(null)
          }}
          recording={selectedRecordingForImport}
          onImported={handleImported}
        />

        {/* Upload Recording Sheet */}
        <Sheet open={uploadSheetOpen} onOpenChange={setUploadSheetOpen}>
          <SheetContent side="right" className="sm:max-w-md overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Icons.upload className="w-5 h-5 text-orange-600" />
                {t('quickActions.uploadRecording')}
              </SheetTitle>
              <SheetDescription>
                {t('subtitle')}
              </SheetDescription>
            </SheetHeader>
            <div className="mt-6">
              <FollowupUploadForm
                onSuccess={handleUploadSuccess}
                isSheet={true}
              />
            </div>
          </SheetContent>
        </Sheet>

        {/* Transcript Viewer/Editor Sheet */}
        <Sheet open={transcriptSheetOpen} onOpenChange={(open) => {
          if (!open && transcriptDirty) {
            // Could add confirmation dialog here
          }
          setTranscriptSheetOpen(open)
        }}>
          <SheetContent side="right" className="sm:max-w-xl overflow-hidden flex flex-col">
            <SheetHeader className="flex-shrink-0">
              <SheetTitle className="flex items-center gap-2">
                <Icons.fileText className="w-5 h-5 text-blue-600" />
                {t('transcript.title')}
              </SheetTitle>
              {selectedTranscript && (
                <SheetDescription>
                  {selectedTranscript.title || t('untitled')}
                  {selectedTranscript.duration_seconds && (
                    <span className="ml-2">• {formatDuration(selectedTranscript.duration_seconds)}</span>
                  )}
                </SheetDescription>
              )}
            </SheetHeader>
            
            <div className="flex-1 mt-4 overflow-hidden flex flex-col">
              {loadingTranscript ? (
                <div className="flex items-center justify-center h-full">
                  <Icons.spinner className="h-8 w-8 animate-spin text-slate-400" />
                </div>
              ) : selectedTranscript ? (
                <>
                  {/* Participants */}
                  {selectedTranscript.participants && selectedTranscript.participants.length > 0 && (
                    <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3 mb-4 flex-shrink-0">
                      <h4 className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
                        {t('transcript.participants')}
                      </h4>
                      <div className="flex flex-wrap gap-1">
                        {selectedTranscript.participants.map((p, i) => (
                          <span key={i} className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                            {p}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Editable Transcript */}
                  <div className="flex-1 overflow-hidden">
                    <textarea
                      className="w-full h-full p-3 text-sm font-sans leading-relaxed resize-none rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      value={editedTranscript}
                      onChange={(e) => {
                        setEditedTranscript(e.target.value)
                        setTranscriptDirty(true)
                      }}
                      placeholder={t('transcript.notAvailable')}
                    />
                  </div>
                  
                  {/* Save button */}
                  <div className="flex items-center justify-between pt-4 flex-shrink-0 border-t border-slate-200 dark:border-slate-700 mt-4">
                    <span className="text-xs text-slate-500">
                      {transcriptDirty && t('transcript.unsavedChanges')}
                    </span>
                    <Button
                      onClick={handleSaveTranscript}
                      disabled={!transcriptDirty || savingTranscript}
                      className="gap-2"
                    >
                      {savingTranscript ? (
                        <Icons.spinner className="h-4 w-4 animate-spin" />
                      ) : (
                        <Icons.check className="h-4 w-4" />
                      )}
                      {t('transcript.save')}
                    </Button>
                  </div>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-slate-400">
                  <Icons.fileText className="h-12 w-12 mb-3" />
                  <p className="text-sm">{t('transcript.notAvailable')}</p>
                </div>
              )}
            </div>
          </SheetContent>
        </Sheet>

        {/* Browser Recording Sheet */}
        <Sheet open={recordingSheetOpen} onOpenChange={(open) => {
          setRecordingSheetOpen(open)
          if (!open) {
            // Reset selection when closing
            setSelectedRecordingProspect(null)
            setSelectedRecordingPrep(null)
            setSelectedRecordingContacts([])
          }
        }}>
          <SheetContent side="right" className="sm:max-w-md overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Icons.mic className="w-5 h-5 text-red-600" />
                {t('quickActions.startRecording')}
              </SheetTitle>
              <SheetDescription>
                {t('recording.description')}
              </SheetDescription>
            </SheetHeader>
            
            <div className="mt-6 space-y-4">
              {/* Prospect Selection */}
              <div>
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 block">
                  {t('recording.selectProspect')}
                </label>
                <Select
                  value={selectedRecordingProspect?.id || ''}
                  onValueChange={(value) => {
                    const prospect = recordingProspects.find(p => p.id === value)
                    setSelectedRecordingProspect(prospect || null)
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('recording.selectProspectPlaceholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {recordingProspects.map((prospect) => (
                      <SelectItem key={prospect.id} value={prospect.id}>
                        {prospect.company_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Preparation Selection (Optional) */}
              {selectedRecordingProspect && (
                <div>
                  <label className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 block">
                    {t('recording.selectPrep')} <span className="text-slate-400">({tCommon('optional')})</span>
                  </label>
                  {loadingRecordingContext ? (
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <Icons.spinner className="h-4 w-4 animate-spin" />
                      {tCommon('loading')}
                    </div>
                  ) : recordingPreparations.length > 0 ? (
                    <Select
                      value={selectedRecordingPrep?.id || ''}
                      onValueChange={(value) => {
                        const prep = recordingPreparations.find(p => p.id === value)
                        setSelectedRecordingPrep(prep || null)
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={t('recording.selectPrepPlaceholder')} />
                      </SelectTrigger>
                      <SelectContent>
                        {recordingPreparations.map((prep) => (
                          <SelectItem key={prep.id} value={prep.id}>
                            {prep.meeting_subject}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <p className="text-sm text-slate-400">{t('recording.noPreps')}</p>
                  )}
                </div>
              )}

              {/* Contact Selection (Optional, Multi) */}
              {selectedRecordingProspect && recordingContacts.length > 0 && (
                <div>
                  <label className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 block">
                    {t('recording.selectContacts')} <span className="text-slate-400">({tCommon('optional')})</span>
                  </label>
                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {recordingContacts.map((contact) => {
                      const isSelected = selectedRecordingContacts.some(c => c.id === contact.id)
                      return (
                        <label 
                          key={contact.id}
                          className="flex items-center gap-2 p-2 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {
                              if (isSelected) {
                                setSelectedRecordingContacts(prev => prev.filter(c => c.id !== contact.id))
                              } else {
                                setSelectedRecordingContacts(prev => [...prev, contact])
                              }
                            }}
                            className="rounded border-slate-300"
                          />
                          <span className="text-sm">{contact.name}</span>
                        </label>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Recording Button */}
              <div className="pt-4 border-t border-slate-200 dark:border-slate-700">
                {selectedRecordingProspect ? (
                  <>
                    <p className="text-sm text-slate-500 dark:text-slate-400 text-center mb-4">
                      {t('recording.instructions')}
                    </p>
                    
                    <div className="flex justify-center">
                      <BrowserRecording
                        prospectId={selectedRecordingProspect.id}
                        meetingTitle={selectedRecordingPrep?.meeting_subject}
                        meetingPrepId={selectedRecordingPrep?.id}
                        contactIds={selectedRecordingContacts.map(c => c.id)}
                        onRecordingComplete={handleRecordingComplete}
                      />
                    </div>
                    
                    <p className="text-xs text-slate-400 dark:text-slate-500 text-center mt-4">
                      {t('recording.hint')}
                    </p>
                  </>
                ) : (
                  <div className="text-center py-4">
                    <Icons.mic className="h-8 w-8 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      {t('recording.selectProspectFirst')}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </SheetContent>
        </Sheet>

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('delete.confirmTitle')}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('delete.confirmDescription', { title: recordingToDelete?.title || recordingToDelete?.prospect_name || t('untitled') })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={deleting}>
                {tCommon('cancel')}
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDeleteRecording}
                disabled={deleting}
                className="bg-red-600 hover:bg-red-700"
              >
                {deleting ? (
                  <Icons.spinner className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Icons.trash className="h-4 w-4 mr-2" />
                )}
                {t('delete.confirm')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </DashboardLayout>
  )
}

