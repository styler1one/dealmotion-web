'use client'

import posthog from 'posthog-js'
import { PostHogProvider as PHProvider } from 'posthog-js/react'
import { useEffect, ReactNode } from 'react'
import { usePathname, useSearchParams } from 'next/navigation'

// Initialize PostHog
if (typeof window !== 'undefined' && process.env.NEXT_PUBLIC_POSTHOG_KEY) {
  posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://eu.i.posthog.com',
    person_profiles: 'identified_only',
    capture_pageview: false, // We capture manually for better control
    capture_pageleave: true,
    // Respect user privacy settings
    persistence: 'localStorage+cookie',
    // Disable in development
    loaded: (posthog) => {
      if (process.env.NODE_ENV === 'development') {
        posthog.opt_out_capturing()
      }
    },
  })
}

// Page view tracking component
function PostHogPageView() {
  const pathname = usePathname()
  const searchParams = useSearchParams()

  useEffect(() => {
    if (pathname && posthog) {
      let url = window.origin + pathname
      if (searchParams && searchParams.toString()) {
        url = url + `?${searchParams.toString()}`
      }
      posthog.capture('$pageview', {
        $current_url: url,
      })
    }
  }, [pathname, searchParams])

  return null
}

// PostHog Provider component
interface PostHogProviderProps {
  children: ReactNode
}

export function PostHogProvider({ children }: PostHogProviderProps) {
  if (!process.env.NEXT_PUBLIC_POSTHOG_KEY) {
    // PostHog not configured, render children without tracking
    return <>{children}</>
  }

  return (
    <PHProvider client={posthog}>
      <PostHogPageView />
      {children}
    </PHProvider>
  )
}

// Export posthog instance for direct usage
export { posthog }

// ============================================
// TRACKING EVENTS
// ============================================
// Call these functions to track user actions

/**
 * Identify a user after login
 */
export function identifyUser(userId: string, properties?: Record<string, unknown>) {
  if (posthog) {
    posthog.identify(userId, properties)
  }
}

/**
 * Reset user on logout
 */
export function resetUser() {
  if (posthog) {
    posthog.reset()
  }
}

/**
 * Track a custom event
 */
export function trackEvent(eventName: string, properties?: Record<string, unknown>) {
  if (posthog) {
    posthog.capture(eventName, properties)
  }
}

// ============================================
// PREDEFINED EVENTS
// ============================================

export const analytics = {
  // Research events
  researchStarted: (prospectName: string) => 
    trackEvent('research_started', { prospect_name: prospectName }),
  
  researchCompleted: (prospectName: string, durationMs: number) => 
    trackEvent('research_completed', { prospect_name: prospectName, duration_ms: durationMs }),

  // Preparation events
  prepStarted: (prospectName: string, meetingType: string) => 
    trackEvent('prep_started', { prospect_name: prospectName, meeting_type: meetingType }),
  
  prepCompleted: (prospectName: string, meetingType: string) => 
    trackEvent('prep_completed', { prospect_name: prospectName, meeting_type: meetingType }),

  // Follow-up events
  followupUploaded: (type: 'audio' | 'transcript') => 
    trackEvent('followup_uploaded', { upload_type: type }),
  
  followupCompleted: (prospectName: string) => 
    trackEvent('followup_completed', { prospect_name: prospectName }),

  actionGenerated: (actionType: string) => 
    trackEvent('action_generated', { action_type: actionType }),

  // Contact events
  contactAdded: (prospectName: string) => 
    trackEvent('contact_added', { prospect_name: prospectName }),
  
  contactAnalyzed: (prospectName: string) => 
    trackEvent('contact_analyzed', { prospect_name: prospectName }),

  // Knowledge base events
  documentUploaded: (fileType: string) => 
    trackEvent('document_uploaded', { file_type: fileType }),

  // Subscription events
  subscriptionStarted: (plan: string) => 
    trackEvent('subscription_started', { plan }),
  
  subscriptionCancelled: (plan: string) => 
    trackEvent('subscription_cancelled', { plan }),

  // Export events
  exportGenerated: (format: 'pdf' | 'docx' | 'md', type: string) => 
    trackEvent('export_generated', { format, export_type: type }),

  // Coach events
  coachSuggestionClicked: (suggestionType: string) => 
    trackEvent('coach_suggestion_clicked', { suggestion_type: suggestionType }),
  
  coachDismissed: () => 
    trackEvent('coach_dismissed'),

  // Onboarding events
  onboardingStarted: () => 
    trackEvent('onboarding_started'),
  
  onboardingCompleted: (step: string) => 
    trackEvent('onboarding_completed', { completed_step: step }),

  // Feature usage
  featureUsed: (featureName: string) => 
    trackEvent('feature_used', { feature: featureName }),
}

