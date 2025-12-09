'use client'

import { useCallback, useEffect, useRef } from 'react'
import { usePathname } from 'next/navigation'
import { api } from '@/lib/api'

/**
 * Event types that can be tracked by the coach.
 */
export type CoachEventType = 
  | 'page_view'
  | 'suggestion_shown'
  | 'suggestion_clicked'
  | 'suggestion_dismissed'
  | 'suggestion_snoozed'
  | 'suggestion_completed'
  | 'widget_expanded'
  | 'widget_collapsed'
  | 'widget_minimized'
  | 'task_started'
  | 'task_completed'
  | 'research_created'
  | 'research_completed'
  | 'contacts_added'
  | 'prep_created'
  | 'prep_completed'
  | 'followup_created'
  | 'followup_completed'
  | 'action_generated'
  | 'brief_exported'

/**
 * Event data structure
 */
interface CoachEvent {
  event_type: CoachEventType
  event_data?: Record<string, any>
  page_context?: string
}

/**
 * Queue for batching events
 */
const eventQueue: CoachEvent[] = []
let flushTimeout: NodeJS.Timeout | null = null

/**
 * Flush the event queue to the API
 */
async function flushEventQueue() {
  if (eventQueue.length === 0) return
  
  // Copy and clear the queue
  const events = [...eventQueue]
  eventQueue.length = 0
  
  // Send each event (in future: batch endpoint)
  for (const event of events) {
    try {
      await api.post('/api/v1/coach/events', event)
    } catch (error) {
      console.error('[Coach] Failed to track event:', error)
    }
  }
}

/**
 * Schedule a flush of the event queue
 */
function scheduleFlush() {
  if (flushTimeout) return
  
  flushTimeout = setTimeout(() => {
    flushTimeout = null
    flushEventQueue()
  }, 2000) // Debounce 2 seconds
}

/**
 * Hook for tracking user behavior for the AI Coach.
 * 
 * Features:
 * - Auto-tracks page views
 * - Debounces and batches events
 * - Provides trackEvent function for manual tracking
 * 
 * @example
 * ```tsx
 * const { trackEvent } = useCoachTracking()
 * 
 * // Track a custom event
 * trackEvent('task_completed', { taskType: 'research', companyName: 'Acme' })
 * ```
 */
export function useCoachTracking() {
  const pathname = usePathname()
  const lastPageRef = useRef<string>('')
  
  /**
   * Track a single event
   */
  const trackEvent = useCallback((
    eventType: CoachEventType,
    eventData?: Record<string, any>,
    pageContext?: string
  ) => {
    const event: CoachEvent = {
      event_type: eventType,
      event_data: eventData,
      page_context: pageContext || pathname,
    }
    
    eventQueue.push(event)
    scheduleFlush()
  }, [pathname])
  
  /**
   * Auto-track page views
   */
  useEffect(() => {
    // Only track if page changed
    if (pathname && pathname !== lastPageRef.current) {
      lastPageRef.current = pathname
      
      // Extract page type from pathname
      const pageType = extractPageType(pathname)
      
      trackEvent('page_view', { 
        page: pathname,
        pageType,
      })
    }
  }, [pathname, trackEvent])
  
  /**
   * Track research completion
   */
  const trackResearchCompleted = useCallback((data: {
    researchId: string
    companyName: string
  }) => {
    trackEvent('research_completed', data)
  }, [trackEvent])
  
  /**
   * Track contacts added
   */
  const trackContactsAdded = useCallback((data: {
    prospectId: string
    contactCount: number
  }) => {
    trackEvent('contacts_added', data)
  }, [trackEvent])
  
  /**
   * Track prep completion
   */
  const trackPrepCompleted = useCallback((data: {
    prepId: string
    companyName: string
  }) => {
    trackEvent('prep_completed', data)
  }, [trackEvent])
  
  /**
   * Track follow-up completion
   */
  const trackFollowupCompleted = useCallback((data: {
    followupId: string
    companyName: string
  }) => {
    trackEvent('followup_completed', data)
  }, [trackEvent])
  
  /**
   * Track action generation
   */
  const trackActionGenerated = useCallback((data: {
    followupId: string
    actionType: string
  }) => {
    trackEvent('action_generated', data)
  }, [trackEvent])
  
  /**
   * Track brief export
   */
  const trackBriefExported = useCallback((data: {
    briefType: 'research' | 'preparation' | 'followup'
    format: 'pdf' | 'docx' | 'md'
  }) => {
    trackEvent('brief_exported', data)
  }, [trackEvent])
  
  /**
   * Track widget state changes
   */
  const trackWidgetState = useCallback((state: 'expanded' | 'collapsed' | 'minimized') => {
    const eventType: CoachEventType = `widget_${state}` as CoachEventType
    trackEvent(eventType)
  }, [trackEvent])
  
  return {
    trackEvent,
    trackResearchCompleted,
    trackContactsAdded,
    trackPrepCompleted,
    trackFollowupCompleted,
    trackActionGenerated,
    trackBriefExported,
    trackWidgetState,
  }
}

/**
 * Extract a page type from a pathname
 */
function extractPageType(pathname: string): string {
  if (pathname.includes('/research/')) return 'research_detail'
  if (pathname.includes('/research')) return 'research_list'
  if (pathname.includes('/preparation/')) return 'preparation_detail'
  if (pathname.includes('/preparation')) return 'preparation_list'
  if (pathname.includes('/followup/')) return 'followup_detail'
  if (pathname.includes('/followup')) return 'followup_list'
  if (pathname.includes('/prospects/')) return 'prospect_detail'
  if (pathname.includes('/prospects')) return 'prospect_list'
  if (pathname.includes('/deals/')) return 'deal_detail'
  if (pathname.includes('/deals')) return 'deal_list'
  if (pathname.includes('/settings')) return 'settings'
  if (pathname.includes('/dashboard') && pathname.split('/').length <= 3) return 'dashboard'
  if (pathname.includes('/onboarding')) return 'onboarding'
  return 'other'
}

/**
 * Standalone track function for use outside of React components
 */
export function trackCoachEvent(
  eventType: CoachEventType,
  eventData?: Record<string, any>,
  pageContext?: string
) {
  const event: CoachEvent = {
    event_type: eventType,
    event_data: eventData,
    page_context: pageContext || (typeof window !== 'undefined' ? window.location.pathname : ''),
  }
  
  eventQueue.push(event)
  scheduleFlush()
}

