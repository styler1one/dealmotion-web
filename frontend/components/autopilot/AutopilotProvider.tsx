'use client'

/**
 * DealMotion Autopilot - Context Provider
 * SPEC-045 / TASK-048
 * 
 * Provides autopilot state and actions to the application.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react'
import { api } from '@/lib/api'
import { logger } from '@/lib/logger'
import type {
  AutopilotContextValue,
  AutopilotSettings,
  AutopilotSettingsUpdate,
  AutopilotProposal,
  ProposalsResponse,
  ProposalCounts,
  AutopilotStats,
  OutcomeRequest,
  PrepViewedRequest,
} from '@/types/autopilot'

// =============================================================================
// CONTEXT
// =============================================================================

const AutopilotContext = createContext<AutopilotContextValue | null>(null)

export function useAutopilot(): AutopilotContextValue {
  const context = useContext(AutopilotContext)
  if (!context) {
    throw new Error('useAutopilot must be used within an AutopilotProvider')
  }
  return context
}

// Optional hook that doesn't throw
export function useAutopilotOptional(): AutopilotContextValue | null {
  return useContext(AutopilotContext)
}


// =============================================================================
// PROVIDER
// =============================================================================

interface AutopilotProviderProps {
  children: ReactNode
}

export function AutopilotProvider({ children }: AutopilotProviderProps) {
  // State
  const [isLoading, setIsLoading] = useState(true)
  const [settings, setSettings] = useState<AutopilotSettings | null>(null)
  const [proposals, setProposals] = useState<AutopilotProposal[]>([])
  const [counts, setCounts] = useState<ProposalCounts>({
    proposed: 0,
    executing: 0,
    completed: 0,
    declined: 0,
    snoozed: 0,
    expired: 0,
    failed: 0,
  })
  const [stats, setStats] = useState<AutopilotStats | null>(null)
  
  // Derived state
  const isEnabled = settings?.enabled ?? true
  
  // ==========================================================================
  // API CALLS
  // ==========================================================================
  
  const fetchSettings = useCallback(async () => {
    try {
      const { data, error } = await api.get<AutopilotSettings>('/api/v1/autopilot/settings')
      if (!error && data) {
        setSettings(data)
      }
    } catch (err) {
      logger.error('Failed to fetch autopilot settings', err, { source: 'AutopilotProvider' })
    }
  }, [])
  
  const fetchProposals = useCallback(async () => {
    try {
      const { data, error } = await api.get<ProposalsResponse>('/api/v1/autopilot/proposals?limit=20')
      if (!error && data) {
        setProposals(data.proposals)
        setCounts(data.counts)
      }
    } catch (err) {
      logger.error('Failed to fetch proposals', err, { source: 'AutopilotProvider' })
    }
  }, [])
  
  const fetchStats = useCallback(async () => {
    try {
      const { data, error } = await api.get<AutopilotStats>('/api/v1/autopilot/stats')
      if (!error && data) {
        setStats(data)
      }
    } catch (err) {
      logger.error('Failed to fetch autopilot stats', err, { source: 'AutopilotProvider' })
    }
  }, [])
  
  // ==========================================================================
  // ACTIONS
  // ==========================================================================
  
  const refreshProposals = useCallback(async () => {
    await fetchProposals()
  }, [fetchProposals])
  
  const refreshStats = useCallback(async () => {
    await fetchStats()
  }, [fetchStats])
  
  const acceptProposal = useCallback(async (id: string, reason?: string) => {
    try {
      const { data, error } = await api.post<AutopilotProposal>(
        `/api/v1/autopilot/proposals/${id}/accept`,
        reason ? { reason } : {}
      )
      
      if (!error && data) {
        // Update local state
        setProposals(prev => prev.map(p => p.id === id ? data : p))
        setCounts(prev => ({
          ...prev,
          proposed: prev.proposed - 1,
          executing: prev.executing + 1,
        }))
      }
    } catch (err) {
      logger.error('Failed to accept proposal', err, { source: 'AutopilotProvider' })
      throw err
    }
  }, [])
  
  // Complete a proposal directly (for inline actions that skip Inngest)
  const completeProposal = useCallback(async (id: string) => {
    try {
      const { data, error } = await api.post<AutopilotProposal>(
        `/api/v1/autopilot/proposals/${id}/complete`,
        {}
      )
      
      if (!error && data) {
        // Update local state - mark as completed
        setProposals(prev => prev.map(p => p.id === id ? data : p))
        setCounts(prev => ({
          ...prev,
          proposed: Math.max(0, prev.proposed - 1),
          completed: prev.completed + 1,
        }))
      }
    } catch (err) {
      logger.error('Failed to complete proposal', err, { source: 'AutopilotProvider' })
      throw err
    }
  }, [])
  
  const declineProposal = useCallback(async (id: string, reason?: string) => {
    try {
      const { data, error } = await api.post<AutopilotProposal>(
        `/api/v1/autopilot/proposals/${id}/decline`,
        reason ? { reason } : {}
      )
      
      if (!error && data) {
        // Remove from local state
        setProposals(prev => prev.filter(p => p.id !== id))
        setCounts(prev => ({
          ...prev,
          proposed: prev.proposed - 1,
          declined: prev.declined + 1,
        }))
      }
    } catch (err) {
      logger.error('Failed to decline proposal', err, { source: 'AutopilotProvider' })
      throw err
    }
  }, [])
  
  const snoozeProposal = useCallback(async (id: string, until: Date, reason?: string) => {
    try {
      const { data, error } = await api.post<AutopilotProposal>(
        `/api/v1/autopilot/proposals/${id}/snooze`,
        { snooze_until: until.toISOString(), reason }
      )
      
      if (!error && data) {
        // Remove from local state (will reappear when unsnoozes)
        setProposals(prev => prev.filter(p => p.id !== id))
        setCounts(prev => ({
          ...prev,
          proposed: prev.proposed - 1,
          snoozed: prev.snoozed + 1,
        }))
      }
    } catch (err) {
      logger.error('Failed to snooze proposal', err, { source: 'AutopilotProvider' })
      throw err
    }
  }, [])
  
  const retryProposal = useCallback(async (id: string) => {
    try {
      const { data, error } = await api.post<AutopilotProposal>(
        `/api/v1/autopilot/proposals/${id}/retry`,
        {}
      )
      
      if (!error && data) {
        // Update local state
        setProposals(prev => prev.map(p => p.id === id ? data : p))
        setCounts(prev => ({
          ...prev,
          failed: prev.failed - 1,
          executing: prev.executing + 1,
        }))
      }
    } catch (err) {
      logger.error('Failed to retry proposal', err, { source: 'AutopilotProvider' })
      throw err
    }
  }, [])
  
  const updateSettings = useCallback(async (updates: AutopilotSettingsUpdate) => {
    try {
      const { data, error } = await api.patch<AutopilotSettings>('/api/v1/autopilot/settings', updates)
      if (!error && data) {
        setSettings(data)
      }
    } catch (err) {
      logger.error('Failed to update autopilot settings', err, { source: 'AutopilotProvider' })
      throw err
    }
  }, [])
  
  const recordOutcome = useCallback(async (outcome: OutcomeRequest) => {
    try {
      await api.post('/api/v1/autopilot/outcomes', outcome)
    } catch (err) {
      logger.error('Failed to record outcome', err, { source: 'AutopilotProvider' })
      // Don't throw - this is non-critical
    }
  }, [])
  
  const recordPrepViewed = useCallback(async (data: PrepViewedRequest) => {
    try {
      await api.post('/api/v1/autopilot/prep-viewed', data)
    } catch (err) {
      // Silently fail - this is non-critical tracking
      console.debug('Failed to record prep viewed:', err)
    }
  }, [])
  
  // ==========================================================================
  // EFFECTS
  // ==========================================================================
  
  const hasLoadedRef = useRef(false)
  
  // Initial load
  useEffect(() => {
    if (hasLoadedRef.current) return
    hasLoadedRef.current = true
    
    const loadData = async () => {
      setIsLoading(true)
      try {
        await Promise.all([
          fetchSettings(),
          fetchProposals(),
          fetchStats(),
        ])
      } finally {
        setIsLoading(false)
      }
    }
    
    loadData()
  }, [fetchSettings, fetchProposals, fetchStats])
  
  // Refresh proposals periodically (every 30 seconds)
  useEffect(() => {
    if (!isEnabled) return
    
    const interval = setInterval(() => {
      fetchProposals()
    }, 30 * 1000)
    
    return () => clearInterval(interval)
  }, [isEnabled, fetchProposals])
  
  // Refresh stats periodically (every 2 minutes)
  useEffect(() => {
    if (!isEnabled) return
    
    const interval = setInterval(() => {
      fetchStats()
    }, 2 * 60 * 1000)
    
    return () => clearInterval(interval)
  }, [isEnabled, fetchStats])
  
  // ==========================================================================
  // CONTEXT VALUE
  // ==========================================================================
  
  const value: AutopilotContextValue = {
    isLoading,
    isEnabled,
    proposals,
    counts,
    stats,
    settings,
    refreshProposals,
    acceptProposal,
    completeProposal,
    declineProposal,
    snoozeProposal,
    retryProposal,
    refreshStats,
    updateSettings,
    recordOutcome,
    recordPrepViewed,
  }
  
  return (
    <AutopilotContext.Provider value={value}>
      {children}
    </AutopilotContext.Provider>
  )
}
