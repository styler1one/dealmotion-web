'use client'

import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'

/**
 * Tip of the day structure
 */
export interface TipOfDay {
  id: string
  category: 'research' | 'contacts' | 'preparation' | 'followup' | 'actions' | 'timing' | 'general'
  title: string
  content: string
  icon: string
  is_personalized: boolean
}

/**
 * TASK-038: LocalStorage cache for tips
 * Reduces API calls and token usage
 */
const TIP_CACHE_KEY = 'luna_tip_cache'

interface TipCache {
  date: string  // YYYY-MM-DD
  tip: TipOfDay
}

function getTodayString(): string {
  return new Date().toISOString().split('T')[0]
}

function getCachedTip(): TipOfDay | null {
  if (typeof window === 'undefined') return null
  
  try {
    const cached = localStorage.getItem(TIP_CACHE_KEY)
    if (!cached) return null
    
    const { date, tip } = JSON.parse(cached) as TipCache
    
    // Check if cache is from today
    if (date === getTodayString()) {
      return tip
    }
    
    // Cache expired, remove it
    localStorage.removeItem(TIP_CACHE_KEY)
    return null
  } catch {
    return null
  }
}

function setCachedTip(tip: TipOfDay): void {
  if (typeof window === 'undefined') return
  
  try {
    const cache: TipCache = {
      date: getTodayString(),
      tip
    }
    localStorage.setItem(TIP_CACHE_KEY, JSON.stringify(cache))
  } catch {
    // Ignore localStorage errors
  }
}

/**
 * Pattern analysis structure
 */
export interface PatternAnalysis {
  contacts: {
    total_research: number
    research_with_contacts: number
    contact_rate: number
    avg_contacts_per_research: number
  }
  timing: {
    total_preps: number
    completed_preps: number
    completion_rate: number
  }
  actions: {
    total_followups: number
    followups_with_actions: number
    action_rate: number
    avg_actions_per_followup: number
  }
}

/**
 * Recommendation structure
 */
export interface Recommendation {
  type: 'contacts' | 'actions' | 'timing' | 'general'
  priority: 'high' | 'medium' | 'low'
  message: string
  action: string
}

/**
 * Prediction structure
 */
export interface Prediction {
  type: 'timing' | 'prediction' | 'warning'
  priority: 'high' | 'medium' | 'low'
  title: string
  message: string
  icon: string
  action_route?: string
}

/**
 * Hook for fetching AI insights from the coach
 * 
 * TASK-038: Token optimization
 * - Uses localStorage cache for tips
 * - Only calls API if no cached tip for today
 * - force_ai parameter triggers new AI generation
 */
export function useCoachInsights() {
  const [tip, setTip] = useState<TipOfDay | null>(null)
  const [patterns, setPatterns] = useState<PatternAnalysis | null>(null)
  const [score, setScore] = useState<number>(0)
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  /**
   * Fetch tip of the day
   * 
   * @param forceAI - If true, generates new AI tip (uses tokens)
   */
  const fetchTip = useCallback(async (forceAI: boolean = false) => {
    try {
      // Check localStorage cache first (unless forcing AI)
      if (!forceAI) {
        const cachedTip = getCachedTip()
        if (cachedTip) {
          setTip(cachedTip)
          return
        }
      }
      
      // Fetch from API
      const url = forceAI 
        ? '/api/v1/coach/insights/tip?force_ai=true'
        : '/api/v1/coach/insights/tip'
      
      const { data, error: apiError } = await api.get<TipOfDay>(url)
      if (!apiError && data) {
        setTip(data)
        // Cache the tip for today
        setCachedTip(data)
      }
    } catch (err) {
      console.error('Failed to fetch tip:', err)
    }
  }, [])

  /**
   * Fetch success patterns
   */
  const fetchPatterns = useCallback(async () => {
    try {
      const { data, error: apiError } = await api.get<{
        patterns: PatternAnalysis
        score: number
        recommendations: Recommendation[]
      }>('/api/v1/coach/insights/patterns')
      
      if (!apiError && data) {
        setPatterns(data.patterns)
        setScore(data.score)
        setRecommendations(data.recommendations)
      }
    } catch (err) {
      console.error('Failed to fetch patterns:', err)
    }
  }, [])

  /**
   * Fetch predictions
   */
  const fetchPredictions = useCallback(async () => {
    try {
      const { data, error: apiError } = await api.get<{
        predictions: Prediction[]
        count: number
      }>('/api/v1/coach/insights/predictions')
      
      if (!apiError && data) {
        setPredictions(data.predictions)
      }
    } catch (err) {
      console.error('Failed to fetch predictions:', err)
    }
  }, [])

  /**
   * Refresh all insights (uses cached tip if available)
   */
  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    
    try {
      await Promise.all([
        fetchTip(false),  // Use cache
        fetchPatterns(),
        fetchPredictions(),
      ])
    } catch (err) {
      setError('Failed to load insights')
    } finally {
      setLoading(false)
    }
  }, [fetchTip, fetchPatterns, fetchPredictions])

  /**
   * Generate a new AI tip (uses tokens, ignores cache)
   * TASK-038: Only use when user explicitly requests new tip
   */
  const generateNewAITip = useCallback(async () => {
    setLoading(true)
    try {
      await fetchTip(true)  // Force AI generation
    } finally {
      setLoading(false)
    }
  }, [fetchTip])

  // Initial load
  useEffect(() => {
    refresh()
  }, [refresh])

  return {
    tip,
    patterns,
    score,
    recommendations,
    predictions,
    loading,
    error,
    refresh,
    generateNewAITip,  // TASK-038: New function for AI tips
    fetchTip,
    fetchPatterns,
    fetchPredictions,
  }
}

/**
 * Get a color class based on score
 */
export function getScoreColor(score: number): string {
  if (score >= 80) return 'text-green-600 dark:text-green-400'
  if (score >= 60) return 'text-blue-600 dark:text-blue-400'
  if (score >= 40) return 'text-yellow-600 dark:text-yellow-400'
  return 'text-red-600 dark:text-red-400'
}

/**
 * Get a background color class based on score
 */
export function getScoreBgColor(score: number): string {
  if (score >= 80) return 'bg-green-100 dark:bg-green-900/30'
  if (score >= 60) return 'bg-blue-100 dark:bg-blue-900/30'
  if (score >= 40) return 'bg-yellow-100 dark:bg-yellow-900/30'
  return 'bg-red-100 dark:bg-red-900/30'
}

/**
 * Get label for score
 */
export function getScoreLabel(score: number): string {
  if (score >= 80) return 'Excellent'
  if (score >= 60) return 'Good'
  if (score >= 40) return 'Fair'
  return 'Needs Work'
}


