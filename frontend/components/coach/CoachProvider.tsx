'use client'

/**
 * AI Sales Coach "Luna" - Context Provider
 * TASK-029 / SPEC-028
 * 
 * Provides coach state and actions to the entire application.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react'
import { usePathname } from 'next/navigation'
import { api } from '@/lib/api'
import { logger } from '@/lib/logger'
import type {
  CoachContextValue,
  CoachSettings,
  CoachSettingsUpdate,
  Suggestion,
  SuggestionsResponse,
  CoachStatsResponse,
  WidgetState,
  EventType,
  BehaviorEventCreate,
} from '@/types/coach'

// =============================================================================
// CONTEXT
// =============================================================================

const CoachContext = createContext<CoachContextValue | null>(null)

export function useCoach(): CoachContextValue {
  const context = useContext(CoachContext)
  if (!context) {
    throw new Error('useCoach must be used within a CoachProvider')
  }
  return context
}

// Optional hook that doesn't throw (for components that might render outside provider)
export function useCoachOptional(): CoachContextValue | null {
  return useContext(CoachContext)
}


// =============================================================================
// PROVIDER
// =============================================================================

interface CoachProviderProps {
  children: ReactNode
}

export function CoachProvider({ children }: CoachProviderProps) {
  const pathname = usePathname()
  
  // State
  const [isLoading, setIsLoading] = useState(true)
  const [settings, setSettings] = useState<CoachSettings | null>(null)
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [stats, setStats] = useState<CoachStatsResponse | null>(null)
  const [widgetState, setWidgetStateInternal] = useState<WidgetState>('minimized')
  
  // Derived state
  const isEnabled = settings?.is_enabled ?? true
  
  // ==========================================================================
  // API CALLS
  // ==========================================================================
  
  const fetchSettings = useCallback(async () => {
    try {
      const { data, error } = await api.get<CoachSettings>('/api/v1/coach/settings')
      if (!error && data) {
        setSettings(data)
        setWidgetStateInternal(data.widget_state || 'minimized')
      }
    } catch (err) {
      logger.error('Failed to fetch coach settings', err, { source: 'CoachProvider' })
    }
  }, [])
  
  const fetchSuggestions = useCallback(async () => {
    try {
      const { data, error } = await api.get<SuggestionsResponse>('/api/v1/coach/suggestions?limit=10')
      if (!error && data) {
        // Filter out snoozed suggestions on client side as well
        const now = new Date()
        const activeSuggestions = data.suggestions.filter(s => {
          if (s.snooze_until) {
            const snoozeUntil = new Date(s.snooze_until)
            if (snoozeUntil > now) {
              return false // Still snoozed
            }
          }
          return true
        })
        setSuggestions(activeSuggestions)
      }
    } catch (err) {
      logger.error('Failed to fetch suggestions', err, { source: 'CoachProvider' })
    }
  }, [])
  
  const fetchStats = useCallback(async () => {
    try {
      const { data, error } = await api.get<CoachStatsResponse>('/api/v1/coach/stats')
      if (!error && data) {
        setStats(data)
      }
    } catch (err) {
      logger.error('Failed to fetch coach stats', err, { source: 'CoachProvider' })
    }
  }, [])
  
  // ==========================================================================
  // ACTIONS
  // ==========================================================================
  
  const refreshSuggestions = useCallback(async () => {
    await fetchSuggestions()
  }, [fetchSuggestions])
  
  const dismissSuggestion = useCallback(async (id: string) => {
    try {
      await api.post(`/api/v1/coach/suggestions/${id}/action`, { action: 'dismissed' })
      setSuggestions(prev => prev.filter(s => s.id !== id))
    } catch (err) {
      logger.error('Failed to dismiss suggestion', err, { source: 'CoachProvider' })
    }
  }, [])
  
  const snoozeSuggestion = useCallback(async (id: string, until: Date) => {
    try {
      // Immediately remove from local state for responsive UI
      setSuggestions(prev => prev.filter(s => s.id !== id))
      
      await api.post(`/api/v1/coach/suggestions/${id}/action`, {
        action: 'snoozed',
        snooze_until: until.toISOString(),
      })
      setSuggestions(prev => prev.filter(s => s.id !== id))
    } catch (err) {
      logger.error('Failed to snooze suggestion', err, { source: 'CoachProvider' })
    }
  }, [])
  
  const clickSuggestion = useCallback(async (id: string) => {
    try {
      await api.post(`/api/v1/coach/suggestions/${id}/action`, { action: 'clicked' })
      // Don't remove from list - user might want to see it again
    } catch (err) {
      logger.error('Failed to record suggestion click', err, { source: 'CoachProvider' })
    }
  }, [])
  
  // Use ref to avoid re-creating this callback on every pathname change
  const pathnameRef = useRef(pathname)
  pathnameRef.current = pathname
  
  const trackEvent = useCallback(async (type: EventType, data?: Record<string, unknown>) => {
    try {
      const event: BehaviorEventCreate = {
        event_type: type,
        event_data: data || {},
        page_context: pathnameRef.current,
      }
      await api.post('/api/v1/coach/events', event)
    } catch (err) {
      // Silently fail - tracking shouldn't break the app
      console.debug('Failed to track event:', err)
    }
  }, [])
  
  const updateSettings = useCallback(async (updates: CoachSettingsUpdate) => {
    try {
      const { data, error } = await api.patch<CoachSettings>('/api/v1/coach/settings', updates)
      if (!error && data) {
        setSettings(data)
        if (updates.widget_state) {
          setWidgetStateInternal(updates.widget_state)
        }
      }
    } catch (err) {
      logger.error('Failed to update coach settings', err, { source: 'CoachProvider' })
    }
  }, [])
  
  const setWidgetState = useCallback((state: WidgetState) => {
    setWidgetStateInternal(state)
    // Persist to server
    updateSettings({ widget_state: state })
    // Track event
    if (state === 'expanded') {
      trackEvent('widget_expanded')
    } else if (state === 'minimized') {
      trackEvent('widget_collapsed')
    }
  }, [updateSettings, trackEvent])
  
  // Inline tip dismissal
  const dismissTipId = useCallback(async (tipId: string) => {
    if (!settings) return
    
    const currentDismissed = settings.dismissed_tip_ids || []
    if (currentDismissed.includes(tipId)) return
    
    const newDismissed = [...currentDismissed, tipId]
    await updateSettings({ dismissed_tip_ids: newDismissed })
  }, [settings, updateSettings])
  
  const isDismissed = useCallback((tipId: string): boolean => {
    const dismissed = settings?.dismissed_tip_ids || []
    return dismissed.includes(tipId)
  }, [settings])
  
  // ==========================================================================
  // EFFECTS
  // ==========================================================================
  
  // Track if initial load has happened
  const hasLoadedRef = useRef(false)
  const hasLoadedSuggestionsRef = useRef(false)
  
  // Delay coach loading to let main page content load first
  // This improves perceived performance - users see their data faster
  useEffect(() => {
    if (hasLoadedRef.current) return
    hasLoadedRef.current = true
    
    // Wait 1 second before loading coach data
    // This gives the main page time to load first
    const timer = setTimeout(() => {
      setIsLoading(true)
      fetchSettings().finally(() => {
        setIsLoading(false)
      })
    }, 1000)
    
    return () => clearTimeout(timer)
  }, [fetchSettings])
  
  // Step 2: Only fetch suggestions/stats if coach is enabled
  // Additional 500ms delay after settings load
  useEffect(() => {
    // Wait for settings to load first
    if (settings === null) return
    // Only run once
    if (hasLoadedSuggestionsRef.current) return
    // Skip if disabled
    if (settings.is_enabled === false) return
    
    hasLoadedSuggestionsRef.current = true
    
    // Small delay to let other page operations complete
    const timer = setTimeout(() => {
      fetchSuggestions()
      fetchStats()
    }, 500)
    
    return () => clearTimeout(timer)
  }, [settings, fetchSuggestions, fetchStats])
  
  // Track page views - only when pathname changes AND coach is enabled
  // Delay tracking to not interfere with page load
  const lastTrackedPathRef = useRef<string | null>(null)
  
  useEffect(() => {
    // Skip if disabled or settings not loaded
    if (!settings || settings.is_enabled === false) return
    // Only track if pathname changed
    if (pathname && pathname !== lastTrackedPathRef.current) {
      lastTrackedPathRef.current = pathname
      // Delay tracking to not interfere with page load
      const timer = setTimeout(() => {
        trackEvent('page_view', { page: pathname })
      }, 2000)
      return () => clearTimeout(timer)
    }
  }, [pathname, settings, trackEvent])
  
  // Refresh suggestions periodically (every 5 minutes) - only if enabled
  useEffect(() => {
    if (!settings || settings.is_enabled === false) return
    
    const interval = setInterval(() => {
      fetchSuggestions()
    }, 5 * 60 * 1000)
    
    return () => clearInterval(interval)
  }, [settings, fetchSuggestions])
  
  // ==========================================================================
  // CONTEXT VALUE
  // ==========================================================================
  
  const value: CoachContextValue = {
    isEnabled,
    isLoading,
    widgetState,
    suggestions,
    stats,
    settings,
    setWidgetState,
    refreshSuggestions,
    dismissSuggestion,
    snoozeSuggestion,
    clickSuggestion,
    trackEvent,
    updateSettings,
    dismissTipId,
    isDismissed,
  }
  
  return (
    <CoachContext.Provider value={value}>
      {children}
    </CoachContext.Provider>
  )
}

