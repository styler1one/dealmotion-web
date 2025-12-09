'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { 
  Mic, 
  Square, 
  Pause, 
  Play,
  Loader2,
  AlertCircle,
  Upload,
  X,
  CheckCircle
} from 'lucide-react'
import { useToast } from '@/components/ui/use-toast'
import { useBrowserRecording, formatRecordingDuration, RecordingResult } from '@/hooks/use-browser-recording'
import { uploadFile } from '@/lib/api'

interface BrowserRecordingProps {
  meetingId?: string
  meetingTitle?: string
  prospectId?: string
  onRecordingComplete?: (followupId: string) => void
}

/**
 * Browser Recording Component
 * Allows users to record audio directly in the browser and upload for analysis.
 * 
 * Shows on meeting cards when the meeting is happening now (is_now).
 */
export function BrowserRecording({ 
  meetingId,
  meetingTitle,
  prospectId,
  onRecordingComplete 
}: BrowserRecordingProps) {
  const router = useRouter()
  const { toast } = useToast()
  const t = useTranslations('meetings.recording')
  
  const [showDialog, setShowDialog] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [recordingResult, setRecordingResult] = useState<RecordingResult | null>(null)
  
  const {
    state,
    duration,
    capabilities,
    isRecording,
    isPaused,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    cancelRecording,
    reset,
    requestPermission,
  } = useBrowserRecording({
    onError: (error) => {
      toast({
        title: t('error'),
        description: error.message,
        variant: 'destructive',
      })
    }
  })
  
  // Handle start recording
  const handleStartRecording = async () => {
    setShowDialog(true)
    setRecordingResult(null)
    
    // Check permission first
    if (capabilities.hasAudioPermission === false) {
      const granted = await requestPermission()
      if (!granted) {
        toast({
          title: t('accessRequired'),
          description: t('accessRequiredDesc'),
          variant: 'destructive',
        })
        return
      }
    }
    
    const started = await startRecording()
    if (!started) {
      toast({
        title: t('startFailed'),
        description: t('startFailedDesc'),
        variant: 'destructive',
      })
    }
  }
  
  // Handle stop recording
  const handleStopRecording = async () => {
    const result = await stopRecording()
    if (result) {
      setRecordingResult(result)
    }
  }
  
  // Handle cancel
  const handleCancel = () => {
    cancelRecording()
    setShowDialog(false)
    setRecordingResult(null)
  }
  
  // Handle upload
  const handleUpload = async () => {
    if (!recordingResult) return
    
    setUploading(true)
    setUploadProgress(10)
    
    try {
      const additionalFields: Record<string, string> = {
        include_coaching: 'false',
      }
      
      if (meetingTitle) {
        additionalFields.meeting_subject = meetingTitle
      }
      
      if (prospectId) {
        additionalFields.prospect_id = prospectId
      }
      
      // Link to calendar meeting (SPEC-038)
      if (meetingId) {
        additionalFields.calendar_meeting_id = meetingId
      }
      
      setUploadProgress(30)
      
      const { data, error } = await uploadFile<{
        followup_id: string
        status: string
      }>('/api/v1/followup/upload', recordingResult.file, additionalFields)
      
      setUploadProgress(100)
      
      if (error) {
        throw new Error(error.message || t('uploadFailed'))
      }
      
      toast({
        title: t('uploaded'),
        description: t('uploadedDesc'),
      })
      
      setShowDialog(false)
      reset()
      setRecordingResult(null)
      
      if (data?.followup_id) {
        onRecordingComplete?.(data.followup_id)
        router.push(`/dashboard/followup/${data.followup_id}`)
      }
      
    } catch (err) {
      console.error('Upload failed:', err)
      toast({
        title: t('uploadFailed'),
        description: err instanceof Error ? err.message : '',
        variant: 'destructive',
      })
    } finally {
      setUploading(false)
      setUploadProgress(0)
    }
  }
  
  // Check if browser supports recording
  if (!capabilities.isSupported) {
    return null // Don't show if not supported
  }
  
  return (
    <>
      {/* Record Button - shows on meeting cards */}
      <Button
        size="sm"
        variant="outline"
        className="gap-1 text-red-600 border-red-300 hover:bg-red-50 hover:text-red-700 dark:text-red-400 dark:border-red-800 dark:hover:bg-red-900/20"
        onClick={handleStartRecording}
      >
        <Mic className="h-3 w-3" />
        {t('record')}
      </Button>
      
      {/* Recording Dialog */}
      <Dialog open={showDialog} onOpenChange={(open) => {
        if (!open && !isRecording && !isPaused) {
          handleCancel()
        }
      }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Mic className="h-5 w-5 text-red-500" />
              {recordingResult ? t('titleComplete') : t('title')}
            </DialogTitle>
            <DialogDescription>
              {meetingTitle || t('description')}
            </DialogDescription>
          </DialogHeader>
          
          <div className="py-6">
            {/* Recording in progress */}
            {(isRecording || isPaused) && !recordingResult && (
              <div className="text-center space-y-6">
                {/* Pulsing indicator */}
                <div className="relative inline-flex">
                  <div className={`w-24 h-24 rounded-full ${isRecording ? 'bg-red-100 dark:bg-red-900/30' : 'bg-amber-100 dark:bg-amber-900/30'} flex items-center justify-center`}>
                    <div className={`w-16 h-16 rounded-full ${isRecording ? 'bg-red-500 animate-pulse' : 'bg-amber-500'} flex items-center justify-center`}>
                      {isRecording ? (
                        <Mic className="h-8 w-8 text-white" />
                      ) : (
                        <Pause className="h-8 w-8 text-white" />
                      )}
                    </div>
                  </div>
                </div>
                
                {/* Duration */}
                <div className="text-3xl font-mono font-bold text-slate-900 dark:text-white">
                  {formatRecordingDuration(duration)}
                </div>
                
                {/* Status */}
                <Badge variant={isRecording ? 'destructive' : 'secondary'}>
                  {isRecording ? t('recordingInProgress') : t('paused')}
                </Badge>
                
                {/* Controls */}
                <div className="flex items-center justify-center gap-3">
                  {isRecording ? (
                    <Button
                      variant="outline"
                      size="lg"
                      onClick={pauseRecording}
                      className="gap-2"
                    >
                      <Pause className="h-4 w-4" />
                      {t('pause')}
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      size="lg"
                      onClick={resumeRecording}
                      className="gap-2"
                    >
                      <Play className="h-4 w-4" />
                      {t('resume')}
                    </Button>
                  )}
                  
                  <Button
                    variant="default"
                    size="lg"
                    onClick={handleStopRecording}
                    className="gap-2 bg-red-600 hover:bg-red-700"
                  >
                    <Square className="h-4 w-4" />
                    {t('stop')}
                  </Button>
                </div>
                
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCancel}
                  className="text-slate-500"
                >
                  <X className="h-4 w-4 mr-1" />
                  {t('cancel')}
                </Button>
              </div>
            )}
            
            {/* Recording complete - ready to upload */}
            {recordingResult && !uploading && (
              <div className="text-center space-y-6">
                <div className="w-24 h-24 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto">
                  <CheckCircle className="h-12 w-12 text-green-500" />
                </div>
                
                <div>
                  <p className="text-lg font-medium text-slate-900 dark:text-white">
                    {t('recordingSaved')}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">
                    {t('duration')}: {formatRecordingDuration(recordingResult.duration)}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    {t('format')}: {recordingResult.mimeType}
                  </p>
                </div>
                
                <div className="flex items-center justify-center gap-3">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setRecordingResult(null)
                      reset()
                    }}
                  >
                    {t('recordAgain')}
                  </Button>
                  
                  <Button
                    onClick={handleUpload}
                    className="gap-2"
                  >
                    <Upload className="h-4 w-4" />
                    {t('uploadAnalyze')}
                  </Button>
                </div>
              </div>
            )}
            
            {/* Uploading */}
            {uploading && (
              <div className="text-center space-y-6">
                <div className="w-24 h-24 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mx-auto">
                  <Loader2 className="h-12 w-12 text-blue-500 animate-spin" />
                </div>
                
                <div>
                  <p className="text-lg font-medium text-slate-900 dark:text-white">
                    {t('uploading')}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">
                    {uploadProgress}% {t('complete')}
                  </p>
                </div>
                
                {/* Progress bar */}
                <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
                  <div 
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            )}
            
            {/* Initial state - starting */}
            {state === 'idle' && !recordingResult && (
              <div className="text-center space-y-6">
                <div className="w-24 h-24 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto">
                  <Loader2 className="h-12 w-12 text-slate-400 animate-spin" />
                </div>
                <p className="text-sm text-slate-500">
                  {t('requestingAccess')}
                </p>
              </div>
            )}
          </div>
          
          {/* Permission denied warning */}
          {capabilities.hasAudioPermission === false && (
            <Card className="bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800">
              <CardContent className="py-3">
                <div className="flex items-center gap-2 text-amber-700 dark:text-amber-400">
                  <AlertCircle className="h-4 w-4" />
                  <p className="text-sm">
                    {t('accessDenied')}
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}

/**
 * Minimal recording indicator for meeting cards
 */
export function RecordingIndicator({ duration }: { duration: number }) {
  return (
    <div className="flex items-center gap-2 text-red-500">
      <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
      <span className="text-xs font-mono">
        {formatRecordingDuration(duration)}
      </span>
    </div>
  )
}

