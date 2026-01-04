'use client'

/**
 * AI Sales Coach "Luna" - Main Widget Component
 * TASK-029 / SPEC-028
 * 
 * Floating widget that provides suggestions and guidance.
 * Phase 4: Added animations, transitions, and accessibility.
 * 
 * NOTE: This widget is deprecated in favor of the new Luna Widget (SPEC-046).
 * When Luna is enabled, this widget is hidden.
 */

import React from 'react'
import { useCoachOptional } from './CoachProvider'
import { useLunaOptional } from '@/components/luna'
import { CoachMinimized } from './CoachMinimized'
import { CoachCompact } from './CoachCompact'
import { CoachExpanded } from './CoachExpanded'

export function CoachWidget() {
  const coach = useCoachOptional()
  const luna = useLunaOptional()
  
  // Don't render if coach context isn't available
  if (!coach) {
    return null
  }
  
  // Don't render if new Luna is enabled (SPEC-046 replaces this widget)
  if (luna?.isEnabled && luna?.featureFlags?.lunaWidgetEnabled) {
    return null
  }
  
  // Don't render if disabled or hidden
  if (!coach.isEnabled || coach.widgetState === 'hidden') {
    return null
  }
  
  // Don't render while loading initial data
  if (coach.isLoading) {
    return null
  }
  
  return (
    <div 
      className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-50 animate-in slide-in-from-bottom-4 duration-300"
      role="complementary"
      aria-label="AI Sales Coach"
    >
      {coach.widgetState === 'minimized' && <CoachMinimized />}
      {coach.widgetState === 'compact' && <CoachCompact />}
      {coach.widgetState === 'expanded' && <CoachExpanded />}
    </div>
  )
}

