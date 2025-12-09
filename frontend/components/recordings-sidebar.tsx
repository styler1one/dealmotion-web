'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { 
  Mic, 
  RefreshCw, 
  Loader2, 
  Clock, 
  Users, 
  ChevronRight,
  ArrowRight,
  CheckCircle,
  AlertCircle,
  Flame
} from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'
import { ImportRecordingModal } from './import-recording-modal'

interface ExternalRecording {
  id: string
  provider: string
  external_id: string
  title: string | null
  recording_date: string
  duration_seconds: number | null
  participants: string[]
  transcript_available: boolean
  audio_url: string | null
  matched_meeting_id: string | null
  matched_prospect_id: string | null
  import_status: string
}

interface RecordingsResponse {
  recordings: ExternalRecording[]
  total: number
}

interface IntegrationsStatus {
  fireflies: {
    connected: boolean
    pending_recordings: number
  }
  zoom: {
    connected: boolean
    pending_recordings: number
  }
  teams: {
    connected: boolean
    pending_recordings: number
  }
}

export function RecordingsSidebar() {
  const router = useRouter()
  const { toast } = useToast()
  
  const [recordings, setRecordings] = useState<ExternalRecording[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [hasIntegration, setHasIntegration] = useState(false)
  
  // Import modal state
  const [selectedRecording, setSelectedRecording] = useState<ExternalRecording | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)

  // Load recordings
  const loadRecordings = async () => {
    setLoading(true)
    try {
      // First check if user has any integrations
      const { data: statusData } = await api.get<IntegrationsStatus>('/api/v1/integrations/status')
      
      const hasFireflies = statusData?.fireflies?.connected || false
      const hasZoom = statusData?.zoom?.connected || false
      const hasTeams = statusData?.teams?.connected || false
      
      setHasIntegration(hasFireflies || hasZoom || hasTeams)
      
      if (!hasFireflies && !hasZoom && !hasTeams) {
        setRecordings([])
        setLoading(false)
        return
      }

      const allRecordings: ExternalRecording[] = []

      // Load pending recordings from Fireflies
      if (hasFireflies) {
        const { data, error } = await api.get<RecordingsResponse>(
          '/api/v1/integrations/fireflies/recordings?import_status=pending&limit=10'
        )
        
        if (!error && data) {
          allRecordings.push(...data.recordings)
        }
      }

      // Load pending recordings from Teams
      if (hasTeams) {
        // Teams API returns different field names than Fireflies
        interface TeamsRecording {
          id: string
          external_id: string
          title: string | null
          meeting_time: string | null
          duration: number | null
          participants: Array<{name?: string}> | null
          transcript_available: boolean
          status: string
          imported_followup_id: string | null
        }
        
        const { data, error } = await api.get<{recordings: TeamsRecording[], total: number}>(
          '/api/v1/integrations/teams/recordings?status_filter=pending&limit=10'
        )
        
        if (!error && data) {
          // Map Teams recordings to the ExternalRecording format
          const teamsRecordings: ExternalRecording[] = data.recordings.map(rec => ({
            id: rec.id,
            provider: 'teams',
            external_id: rec.external_id,
            title: rec.title,
            recording_date: rec.meeting_time || '',
            duration_seconds: rec.duration || null,
            participants: rec.participants?.map(p => p.name || 'Unknown') || [],
            transcript_available: rec.transcript_available,
            audio_url: null,
            matched_meeting_id: null,
            matched_prospect_id: null,
            import_status: rec.status || 'pending',
          }))
          allRecordings.push(...teamsRecordings)
        }
      }

      // Sort by date (newest first)
      allRecordings.sort((a, b) => 
        new Date(b.recording_date).getTime() - new Date(a.recording_date).getTime()
      )

      setRecordings(allRecordings)
    } catch (err) {
      console.error('Failed to load recordings:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRecordings()
  }, [])

  // Sync recordings from all providers
  const handleSync = async () => {
    setSyncing(true)
    let totalNew = 0
    const errors: string[] = []
    
    try {
      // Sync Fireflies
      const { data: ffData, error: ffError } = await api.post<{
        success: boolean
        new_recordings: number
      }>('/api/v1/integrations/fireflies/sync', { days_back: 30 })
      
      if (!ffError && ffData) {
        totalNew += ffData.new_recordings || 0
      }
      
      // Sync Teams (if connected via Microsoft 365)
      const { data: teamsData, error: teamsError } = await api.post<{
        success: boolean
        new_recordings: number
      }>('/api/v1/integrations/teams/sync', { days_back: 30 })
      
      if (!teamsError && teamsData) {
        totalNew += teamsData.new_recordings || 0
      }
      // Teams sync might fail if not connected, that's okay - no logging needed
      
      toast({
        title: 'Sync complete',
        description: `${totalNew} new recordings found`,
      })
      
      loadRecordings()
    } catch (err) {
      console.error('Sync failed:', err)
      toast({
        title: 'Sync failed',
        description: err instanceof Error ? err.message : 'Unknown error',
        variant: 'destructive',
      })
    } finally {
      setSyncing(false)
    }
  }

  // Open import modal for a recording
  const handleAnalyze = (recording: ExternalRecording) => {
    setSelectedRecording(recording)
    setIsModalOpen(true)
  }

  // Handle successful import
  const handleImported = (followupId: string) => {
    // Remove from list
    if (selectedRecording) {
      setRecordings(prev => prev.filter(r => r.id !== selectedRecording.id))
    }
    setSelectedRecording(null)
  }

  // Format duration
  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '--'
    const mins = Math.floor(seconds / 60)
    if (mins < 60) return `${mins}m`
    const hours = Math.floor(mins / 60)
    const remainingMins = mins % 60
    return `${hours}h ${remainingMins}m`
  }

  // Format date
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))
    
    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  // Get provider icon and colors
  const getProviderIcon = (provider: string) => {
    switch (provider) {
      case 'fireflies':
        return <Flame className="h-4 w-4 text-white" />
      case 'teams':
        return <span className="text-white text-xs font-bold">T</span>
      default:
        return <Mic className="h-4 w-4 text-white" />
    }
  }

  // Get provider color gradient
  const getProviderGradient = (provider: string) => {
    switch (provider) {
      case 'fireflies':
        return 'from-purple-500 to-pink-500'
      case 'teams':
        return 'from-[#6264A7] to-[#464775]'
      default:
        return 'from-pink-500 to-rose-500'
    }
  }

  // Don't render if no integration
  if (!loading && !hasIntegration) {
    return null
  }

  return (
    <Card className="w-full lg:w-80 shrink-0">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Mic className="h-4 w-4 text-pink-500" />
            New Recordings
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={handleSync}
            disabled={syncing || loading}
          >
            {syncing ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <RefreshCw className="h-3 w-3" />
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
          </div>
        ) : recordings.length === 0 ? (
          <div className="text-center py-6">
            <CheckCircle className="h-8 w-8 text-green-400 mx-auto mb-2" />
            <p className="text-sm text-slate-500">All caught up!</p>
            <p className="text-xs text-slate-400 mt-1">
              No pending recordings to import
            </p>
          </div>
        ) : (
          <>
            {recordings.slice(0, 5).map((recording) => (
              <div
                key={recording.id}
                className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 hover:border-blue-300 dark:hover:border-blue-700 transition-colors"
              >
                <div className="flex items-start gap-3">
                  {/* Provider icon */}
                  <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${getProviderGradient(recording.provider)} flex items-center justify-center shadow-sm shrink-0`}>
                    {getProviderIcon(recording.provider)}
                  </div>
                  
                  {/* Recording info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
                      {recording.title || 'Untitled Recording'}
                    </p>
                    <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
                      <Clock className="h-3 w-3" />
                      <span>{formatDuration(recording.duration_seconds)}</span>
                      <span>•</span>
                      <span>{formatDate(recording.recording_date)}</span>
                    </div>
                    {recording.participants.length > 0 && (
                      <div className="flex items-center gap-1 mt-1 text-xs text-slate-400">
                        <Users className="h-3 w-3" />
                        <span>{recording.participants.slice(0, 2).join(', ')}</span>
                        {recording.participants.length > 2 && (
                          <span>+{recording.participants.length - 2}</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                
                {/* Analyze button - opens import modal */}
                <Button
                  size="sm"
                  className="w-full mt-3 gap-1"
                  onClick={() => handleAnalyze(recording)}
                >
                  Analyze
                  <ArrowRight className="h-3 w-3" />
                </Button>
              </div>
            ))}
            
            {recordings.length > 5 && (
              <p className="text-center text-xs text-slate-400">
                {recordings.length - 5} more recordings available
              </p>
            )}
          </>
        )}
        
        {/* Connect integration prompt */}
        {!loading && !hasIntegration && (
          <div className="text-center py-4">
            <AlertCircle className="h-6 w-6 text-amber-400 mx-auto mb-2" />
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
              Connect Fireflies to import recordings
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => router.push('/dashboard/settings')}
            >
              Connect
            </Button>
          </div>
        )}
      </CardContent>

      {/* Import Recording Modal */}
      <ImportRecordingModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false)
          setSelectedRecording(null)
        }}
        recording={selectedRecording}
        onImported={handleImported}
      />
    </Card>
  )
}

