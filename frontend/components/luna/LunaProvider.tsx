'use client'

/**
 * Luna Unified AI Assistant - Context Provider
 * SPEC-046-Luna-Unified-AI-Assistant
 * 
 * Provides Luna state and actions to the application.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import { api } from '@/lib/api'
import { logger } from '@/lib/logger'
import type {
  LunaContextValue,
  LunaSettings,
  LunaSettingsUpdate,
  LunaMessage,
  MessagesResponse,
  MessageCounts,
  LunaStats,
  LunaGreeting,
  TipOfDay,
  UpcomingMeeting,
  FeatureFlagsResponse,
  SnoozeOption,
  Surface,
} from '@/types/luna'

// =============================================================================
// CONTEXT
// =============================================================================

const LunaContext = createContext<LunaContextValue | null>(null)

export function useLuna(): LunaContextValue {
  const context = useContext(LunaContext)
  if (!context) {
    throw new Error('useLuna must be used within a LunaProvider')
  }
  return context
}

// Optional hook that doesn't throw
export function useLunaOptional(): LunaContextValue | null {
  return useContext(LunaContext)
}

// =============================================================================
// PROVIDER
// =============================================================================

interface LunaProviderProps {
  children: ReactNode
}

export function LunaProvider({ children }: LunaProviderProps) {
  // State
  const [isLoading, setIsLoading] = useState(true)
  const [settings, setSettings] = useState<LunaSettings | null>(null)
  const [messages, setMessages] = useState<LunaMessage[]>([])
  const [counts, setCounts] = useState<MessageCounts>({
    pending: 0,
    executing: 0,
    completed: 0,
    dismissed: 0,
    snoozed: 0,
    expired: 0,
    failed: 0,
    urgent: 0,
  })
  const [stats, setStats] = useState<LunaStats | null>(null)
  const [greeting, setGreeting] = useState<LunaGreeting | null>(null)
  const [tip, setTip] = useState<TipOfDay | null>(null)
  const [upcomingMeetings, setUpcomingMeetings] = useState<UpcomingMeeting[]>([])
  const [featureFlags, setFeatureFlags] = useState<FeatureFlagsResponse | null>(null)
  
  // Derived state
  const isEnabled = featureFlags?.lunaEnabled ?? false
  
  // ==========================================================================
  // API CALLS
  // ==========================================================================
  
  const fetchFeatureFlags = useCallback(async () => {
    try {
      const { data, error } = await api.get<FeatureFlagsResponse>('/api/v1/luna/flags')
      if (!error && data) {
        setFeatureFlags(data)
      }
    } catch (err) {
      logger.error('Failed to fetch Luna feature flags', err, { source: 'LunaProvider' })
    }
  }, [])
  
  const fetchSettings = useCallback(async () => {
    try {
      const { data, error } = await api.get<LunaSettings>('/api/v1/luna/settings')
      if (!error && data) {
        setSettings(data)
      }
    } catch (err) {
      logger.error('Failed to fetch Luna settings', err, { source: 'LunaProvider' })
    }
  }, [])
  
  const fetchMessages = useCallback(async () => {
    try {
      const { data, error } = await api.get<MessagesResponse>('/api/v1/luna/messages?limit=20')
      if (!error && data) {
        setMessages(data.messages)
        setCounts(data.counts)
      }
    } catch (err) {
      logger.error('Failed to fetch Luna messages', err, { source: 'LunaProvider' })
    }
  }, [])
  
  const fetchStats = useCallback(async () => {
    try {
      const { data, error } = await api.get<LunaStats>('/api/v1/luna/stats')
      if (!error && data) {
        setStats(data)
      }
    } catch (err) {
      logger.error('Failed to fetch Luna stats', err, { source: 'LunaProvider' })
    }
  }, [])
  
  const fetchGreeting = useCallback(async () => {
    try {
      const { data, error } = await api.get<LunaGreeting>('/api/v1/luna/greeting')
      if (!error && data) {
        setGreeting(data)
      }
    } catch (err) {
      logger.error('Failed to fetch Luna greeting', err, { source: 'LunaProvider' })
    }
  }, [])
  
  const fetchTip = useCallback(async () => {
    // Check localStorage cache first (24h)
    const cached = localStorage.getItem('luna_tip_cache')
    if (cached) {
      try {
        const { tip: cachedTip, timestamp } = JSON.parse(cached)
        const hoursSince = (Date.now() - timestamp) / (1000 * 60 * 60)
        if (hoursSince < 24) {
          setTip(cachedTip)
          return
        }
      } catch {
        // Invalid cache, continue to fetch
      }
    }
    
    try {
      const { data, error } = await api.get<TipOfDay>('/api/v1/luna/tip')
      if (!error && data) {
        setTip(data)
        // Cache for 24h
        localStorage.setItem('luna_tip_cache', JSON.stringify({
          tip: data,
          timestamp: Date.now()
        }))
      }
    } catch (err) {
      logger.error('Failed to fetch Luna tip', err, { source: 'LunaProvider' })
    }
  }, [])
  
  const fetchUpcomingMeetings = useCallback(async () => {
    try {
      const { data, error } = await api.get<UpcomingMeeting[]>('/api/v1/luna/meetings/upcoming?limit=5')
      if (!error && data) {
        setUpcomingMeetings(data)
      }
    } catch (err) {
      logger.error('Failed to fetch upcoming meetings', err, { source: 'LunaProvider' })
    }
  }, [])
  
  // ==========================================================================
  // ACTIONS
  // ==========================================================================
  
  const refreshMessages = useCallback(async () => {
    await fetchMessages()
  }, [fetchMessages])
  
  const refreshStats = useCallback(async () => {
    await fetchStats()
  }, [fetchStats])
  
  const refreshGreeting = useCallback(async () => {
    await fetchGreeting()
  }, [fetchGreeting])
  
  const acceptMessage = useCallback(async (id: string) => {
    try {
      const { data, error } = await api.post<{ success: boolean }>(
        `/api/v1/luna/messages/${id}/accept`,
        { surface: 'home' }
      )
      
      if (!error && data?.success) {
        // Optimistically update local state
        setMessages(prev => prev.filter(m => m.id !== id))
        setCounts(prev => ({
          ...prev,
          pending: Math.max(0, prev.pending - 1),
        }))
        
        // Refresh after a short delay to get updated state
        setTimeout(() => {
          refreshMessages()
          refreshStats()
        }, 500)
      }
    } catch (err) {
      logger.error('Failed to accept message', err, { source: 'LunaProvider' })
      throw err
    }
  }, [refreshMessages, refreshStats])
  
  const dismissMessage = useCallback(async (id: string) => {
    try {
      const { data, error } = await api.post<{ success: boolean }>(
        `/api/v1/luna/messages/${id}/dismiss`,
        { surface: 'home' }
      )
      
      if (!error && data?.success) {
        // Optimistically update local state
        setMessages(prev => prev.filter(m => m.id !== id))
        setCounts(prev => ({
          ...prev,
          pending: Math.max(0, prev.pending - 1),
          dismissed: prev.dismissed + 1,
        }))
      }
    } catch (err) {
      logger.error('Failed to dismiss message', err, { source: 'LunaProvider' })
      throw err
    }
  }, [])
  
  const snoozeMessage = useCallback(async (
    id: string,
    option: SnoozeOption,
    customUntil?: string
  ) => {
    try {
      const { data, error } = await api.post<{ success: boolean }>(
        `/api/v1/luna/messages/${id}/snooze`,
        {
          snoozeOption: option,
          snoozeUntil: customUntil,
          surface: 'home'
        }
      )
      
      if (!error && data?.success) {
        // Optimistically update local state
        setMessages(prev => prev.filter(m => m.id !== id))
        setCounts(prev => ({
          ...prev,
          pending: Math.max(0, prev.pending - 1),
          snoozed: prev.snoozed + 1,
        }))
      }
    } catch (err) {
      logger.error('Failed to snooze message', err, { source: 'LunaProvider' })
      throw err
    }
  }, [])
  
  const markMessageShown = useCallback(async (id: string, surface: Surface) => {
    try {
      await api.post(`/api/v1/luna/messages/${id}/shown`, { surface })
    } catch {
      // Silent fail - don't disrupt UX for analytics
      logger.warn('Failed to mark message shown', { source: 'LunaProvider' })
    }
  }, [])
  
  const updateSettings = useCallback(async (updates: LunaSettingsUpdate) => {
    try {
      const { data, error } = await api.patch<LunaSettings>(
        '/api/v1/luna/settings',
        updates
      )
      
      if (!error && data) {
        setSettings(data)
      }
    } catch (err) {
      logger.error('Failed to update settings', err, { source: 'LunaProvider' })
      throw err
    }
  }, [])
  
  const triggerDetection = useCallback(async () => {
    try {
      await api.post('/api/v1/luna/detect', {})
      // Refresh after detection
      setTimeout(() => {
        refreshMessages()
        refreshStats()
      }, 2000)
    } catch (err) {
      logger.error('Failed to trigger detection', err, { source: 'LunaProvider' })
    }
  }, [refreshMessages, refreshStats])
  
  // ==========================================================================
  // INITIAL LOAD
  // ==========================================================================
  
  useEffect(() => {
    const init = async () => {
      setIsLoading(true)
      try {
        // First check feature flags
        await fetchFeatureFlags()
        
        // Then load everything in parallel
        await Promise.all([
          fetchSettings(),
          fetchMessages(),
          fetchStats(),
          fetchGreeting(),
          fetchTip(),
          fetchUpcomingMeetings(),
        ])
      } finally {
        setIsLoading(false)
      }
    }
    
    init()
  }, [
    fetchFeatureFlags,
    fetchSettings,
    fetchMessages,
    fetchStats,
    fetchGreeting,
    fetchTip,
    fetchUpcomingMeetings,
  ])
  
  // ==========================================================================
  // POLLING
  // ==========================================================================
  
  useEffect(() => {
    // Poll for updates every 30 seconds if Luna is enabled
    if (!isEnabled) return
    
    const interval = setInterval(() => {
      fetchMessages()
    }, 30000)
    
    return () => clearInterval(interval)
  }, [isEnabled, fetchMessages])
  
  // ==========================================================================
  // CONTEXT VALUE
  // ==========================================================================
  
  const value: LunaContextValue = {
    isLoading,
    isEnabled,
    settings,
    messages,
    counts,
    stats,
    greeting,
    tip,
    upcomingMeetings,
    featureFlags,
    refreshMessages,
    refreshStats,
    refreshGreeting,
    acceptMessage,
    dismissMessage,
    snoozeMessage,
    markMessageShown,
    updateSettings,
    triggerDetection,
  }
  
  return (
    <LunaContext.Provider value={value}>
      {children}
    </LunaContext.Provider>
  )
}
