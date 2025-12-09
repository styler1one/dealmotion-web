'use client'

import { useState, useRef, useCallback, useEffect } from 'react'

export type RecordingState = 'idle' | 'recording' | 'paused' | 'stopped'

export interface BrowserRecordingCapabilities {
  isSupported: boolean
  supportedMimeTypes: string[]
  preferredMimeType: string | null
  hasAudioPermission: boolean | null
}

export interface RecordingResult {
  blob: Blob
  mimeType: string
  duration: number
  file: File
}

interface UseBrowserRecordingOptions {
  onDataAvailable?: (blob: Blob) => void
  onError?: (error: Error) => void
  onStateChange?: (state: RecordingState) => void
}

/**
 * Browser Recording Hook
 * Uses MediaRecorder API to record audio in the browser.
 * 
 * Supported formats (in order of preference):
 * - Chrome/Firefox/Edge: audio/webm;codecs=opus
 * - Safari: audio/mp4 or audio/wav
 */
export function useBrowserRecording(options: UseBrowserRecordingOptions = {}) {
  const { onDataAvailable, onError, onStateChange } = options
  
  const [state, setState] = useState<RecordingState>('idle')
  const [duration, setDuration] = useState(0)
  const [capabilities, setCapabilities] = useState<BrowserRecordingCapabilities>({
    isSupported: false,
    supportedMimeTypes: [],
    preferredMimeType: null,
    hasAudioPermission: null,
  })
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startTimeRef = useRef<number>(0)
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  
  // Check browser capabilities on mount
  useEffect(() => {
    checkCapabilities()
  }, [])
  
  // Notify on state change
  useEffect(() => {
    onStateChange?.(state)
  }, [state, onStateChange])
  
  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopRecording()
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [])
  
  /**
   * Check browser recording capabilities
   */
  const checkCapabilities = useCallback(async () => {
    // Check if MediaRecorder is supported
    const isSupported = typeof MediaRecorder !== 'undefined' && 
                        typeof navigator.mediaDevices !== 'undefined'
    
    if (!isSupported) {
      setCapabilities({
        isSupported: false,
        supportedMimeTypes: [],
        preferredMimeType: null,
        hasAudioPermission: null,
      })
      return
    }
    
    // Check supported MIME types (in order of preference)
    // Prefer mp4 (better Deepgram compatibility) then webm
    const mimeTypes = [
      'audio/mp4',               // Best: MP4 (Safari, better Deepgram support)
      'audio/mpeg',              // MP3 (if supported, rare)
      'audio/wav',               // WAV (universally supported by Deepgram)
      'audio/webm;codecs=opus',  // WebM with Opus (Chrome, Firefox, Edge)
      'audio/webm',              // WebM fallback
      'audio/ogg;codecs=opus',   // Ogg with Opus
    ]
    
    const supportedMimeTypes = mimeTypes.filter(type => {
      try {
        return MediaRecorder.isTypeSupported(type)
      } catch {
        return false
      }
    })
    
    // Get the best available MIME type
    const preferredMimeType = supportedMimeTypes[0] || null
    
    // Check for existing permission (without prompting)
    let hasAudioPermission: boolean | null = null
    try {
      const permissionStatus = await navigator.permissions.query({ 
        name: 'microphone' as PermissionName 
      })
      hasAudioPermission = permissionStatus.state === 'granted'
    } catch {
      // Permission API not supported, we'll find out when trying to record
      hasAudioPermission = null
    }
    
    setCapabilities({
      isSupported: true,
      supportedMimeTypes,
      preferredMimeType,
      hasAudioPermission,
    })
  }, [])
  
  /**
   * Request microphone permission
   */
  const requestPermission = useCallback(async (): Promise<boolean> => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 48000,
          channelCount: 1,
          sampleSize: 16,
        }
      })
      
      // Stop the stream immediately, we just wanted permission
      stream.getTracks().forEach(track => track.stop())
      
      setCapabilities(prev => ({
        ...prev,
        hasAudioPermission: true,
      }))
      
      return true
    } catch (error) {
      console.error('Microphone permission denied:', error)
      setCapabilities(prev => ({
        ...prev,
        hasAudioPermission: false,
      }))
      return false
    }
  }, [])
  
  /**
   * Start recording
   */
  const startRecording = useCallback(async (): Promise<boolean> => {
    if (!capabilities.isSupported || !capabilities.preferredMimeType) {
      onError?.(new Error('Browser recording not supported'))
      return false
    }
    
    if (state === 'recording') {
      return false
    }
    
    try {
      // Get microphone stream with high quality settings
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 48000,        // 48kHz for better quality
          channelCount: 1,          // Mono is fine for voice
          sampleSize: 16,           // 16-bit audio
        }
      })
      
      streamRef.current = stream
      chunksRef.current = []
      
      // Create MediaRecorder with high quality settings
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: capabilities.preferredMimeType,
        audioBitsPerSecond: 256000, // 256 kbps for better transcription quality
      })
      
      mediaRecorderRef.current = mediaRecorder
      
      // Handle data available
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data)
          onDataAvailable?.(event.data)
        }
      }
      
      // Handle errors
      mediaRecorder.onerror = (event) => {
        console.error('MediaRecorder error:', event)
        onError?.(new Error('Recording error occurred'))
        stopRecording()
      }
      
      // Start recording with 1 second timeslices for progress
      mediaRecorder.start(1000)
      startTimeRef.current = Date.now()
      setState('recording')
      
      // Start duration timer
      timerRef.current = setInterval(() => {
        setDuration(Math.floor((Date.now() - startTimeRef.current) / 1000))
      }, 1000)
      
      // Update permission status
      setCapabilities(prev => ({
        ...prev,
        hasAudioPermission: true,
      }))
      
      return true
    } catch (error) {
      console.error('Failed to start recording:', error)
      
      if ((error as DOMException).name === 'NotAllowedError') {
        setCapabilities(prev => ({
          ...prev,
          hasAudioPermission: false,
        }))
        onError?.(new Error('Microphone access denied'))
      } else {
        onError?.(error instanceof Error ? error : new Error('Failed to start recording'))
      }
      
      return false
    }
  }, [capabilities, state, onDataAvailable, onError])
  
  /**
   * Pause recording
   */
  const pauseRecording = useCallback(() => {
    if (mediaRecorderRef.current && state === 'recording') {
      mediaRecorderRef.current.pause()
      setState('paused')
      
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
  }, [state])
  
  /**
   * Resume recording
   */
  const resumeRecording = useCallback(() => {
    if (mediaRecorderRef.current && state === 'paused') {
      mediaRecorderRef.current.resume()
      setState('recording')
      
      // Resume timer
      const pausedDuration = duration
      const resumeTime = Date.now()
      timerRef.current = setInterval(() => {
        setDuration(pausedDuration + Math.floor((Date.now() - resumeTime) / 1000))
      }, 1000)
    }
  }, [state, duration])
  
  /**
   * Stop recording and return result
   */
  const stopRecording = useCallback((): Promise<RecordingResult | null> => {
    return new Promise((resolve) => {
      // Stop timer
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
      
      if (!mediaRecorderRef.current || state === 'idle' || state === 'stopped') {
        setState('idle')
        setDuration(0)
        resolve(null)
        return
      }
      
      const mediaRecorder = mediaRecorderRef.current
      
      mediaRecorder.onstop = () => {
        // Stop all tracks
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop())
          streamRef.current = null
        }
        
        // Create final blob
        const mimeType = capabilities.preferredMimeType || 'audio/webm'
        const blob = new Blob(chunksRef.current, { type: mimeType })
        
        // Create File object
        const extension = getExtensionForMimeType(mimeType)
        const filename = `recording_${Date.now()}.${extension}`
        const file = new File([blob], filename, { type: mimeType })
        
        const result: RecordingResult = {
          blob,
          mimeType,
          duration,
          file,
        }
        
        setState('stopped')
        mediaRecorderRef.current = null
        
        resolve(result)
      }
      
      mediaRecorder.stop()
    })
  }, [state, duration, capabilities.preferredMimeType])
  
  /**
   * Cancel recording without saving
   */
  const cancelRecording = useCallback(() => {
    // Stop timer
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    
    // Stop stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }
    
    // Stop recorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
    
    mediaRecorderRef.current = null
    chunksRef.current = []
    setState('idle')
    setDuration(0)
  }, [])
  
  /**
   * Reset to initial state
   */
  const reset = useCallback(() => {
    cancelRecording()
    setDuration(0)
    setState('idle')
  }, [cancelRecording])
  
  return {
    // State
    state,
    duration,
    capabilities,
    isRecording: state === 'recording',
    isPaused: state === 'paused',
    
    // Actions
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    cancelRecording,
    reset,
    requestPermission,
    checkCapabilities,
  }
}

/**
 * Get file extension for MIME type
 */
function getExtensionForMimeType(mimeType: string): string {
  if (mimeType.includes('webm')) return 'webm'
  if (mimeType.includes('ogg')) return 'ogg'
  if (mimeType.includes('mp4')) return 'm4a'
  if (mimeType.includes('wav')) return 'wav'
  if (mimeType.includes('mpeg')) return 'mp3'
  return 'webm'
}

/**
 * Format duration as MM:SS or HH:MM:SS
 */
export function formatRecordingDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

