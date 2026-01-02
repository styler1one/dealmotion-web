'use client'

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { api } from '@/lib/api'
import { logger } from '@/lib/logger'

interface UsageMetric {
  used: number
  limit: number
  unlimited: boolean
  remaining?: number
  percentage?: number
}

interface TranscriptionUsage extends UsageMetric {
  used_hours?: number
  limit_hours?: number
}

interface Usage {
  period_start: string | null  // null for free plan (no monthly reset)
  period_end?: string | null
  // v2: Primary metric
  flow?: UsageMetric
  // v1 compatibility
  research: UsageMetric
  preparation: UsageMetric
  followup: UsageMetric
  transcription_seconds: TranscriptionUsage
  kb_documents: UsageMetric
}

interface PlanFeatures {
  flow_limit?: number
  user_limit?: number
  crm_integration?: boolean
  priority_support?: boolean
  pdf_watermark?: boolean
  kb_document_limit?: number
  transcription_seconds_limit?: number
  [key: string]: unknown  // Allow additional features
}

interface Subscription {
  id: string | null
  organization_id: string
  plan_id: string
  plan_name: string
  status: string
  features: PlanFeatures
  price_cents: number | null
  billing_interval: string | null
  current_period_start: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
  trial_start: string | null
  trial_end: string | null
  is_trialing: boolean
  is_active: boolean
  is_paid: boolean
}

interface BillingContextType {
  subscription: Subscription | null
  usage: Usage | null
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
  checkLimit: (metric: string) => Promise<{ allowed: boolean; current: number; limit: number; upgrade_required: boolean }>
  createCheckoutSession: (planId: string) => Promise<string>
  openBillingPortal: () => Promise<string>
  getUsagePercentage: (metric: keyof Usage) => number
  isFeatureAvailable: (feature: string) => boolean
}

const BillingContext = createContext<BillingContextType | undefined>(undefined)

export function BillingProvider({ children }: { children: React.ReactNode }) {
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [usage, setUsage] = useState<Usage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const hasLoadedRef = useRef(false)

  const fetchBillingData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch subscription and usage in parallel - api client handles auth
      const [subResult, usageResult] = await Promise.all([
        api.get<Subscription>('/api/v1/billing/subscription'),
        api.get<Usage>('/api/v1/billing/usage'),
      ])

      if (!subResult.error && subResult.data) {
        setSubscription(subResult.data)
      }

      if (!usageResult.error && usageResult.data) {
        setUsage(usageResult.data)
      }

    } catch (err) {
      logger.error('Error fetching billing data', err, { source: 'BillingContext' })
      setError('Failed to load billing data')
    } finally {
      setLoading(false)
    }
  }, [])

  // Load only once on mount
  useEffect(() => {
    if (hasLoadedRef.current) return
    hasLoadedRef.current = true
    fetchBillingData()
  }, [fetchBillingData])

  const checkLimit = async (metric: string) => {
    try {
      // api client handles auth
      const { data, error } = await api.post<{ allowed: boolean; current: number; limit: number; upgrade_required: boolean }>(
        '/api/v1/billing/check-limit',
        { metric }
      )

      if (!error && data) {
        return data
      }

      return { allowed: false, current: 0, limit: 0, upgrade_required: true }
    } catch (err) {
      logger.error('Error checking limit', err, { source: 'BillingContext' })
      return { allowed: false, current: 0, limit: 0, upgrade_required: true }
    }
  }

  const createCheckoutSession = async (planId: string): Promise<string> => {
    try {
      // api client handles auth
      const { data, error } = await api.post<{ checkout_url: string }>(
        '/api/v1/billing/checkout',
        { 
          plan_id: planId,
          success_url: `${window.location.origin}/billing/success`,
          cancel_url: `${window.location.origin}/pricing`,
        }
      )

      if (error) {
        logger.error('Checkout API error', error, { source: 'BillingContext' })
        throw new Error(error.message || 'Checkout failed')
      }

      if (!data?.checkout_url) {
        logger.error('No checkout_url in response', data, { source: 'BillingContext' })
        throw new Error('No checkout URL returned from server')
      }
      return data.checkout_url
    } catch (err) {
      logger.error('Error creating checkout', err, { source: 'BillingContext' })
      throw err
    }
  }

  const openBillingPortal = async (): Promise<string> => {
    try {
      // api client handles auth
      const { data, error } = await api.post<{ portal_url: string }>(
        '/api/v1/billing/portal',
        { return_url: `${window.location.origin}/dashboard/settings` }
      )

      if (error || !data?.portal_url) {
        throw new Error('Failed to create portal session')
      }

      return data.portal_url
    } catch (err) {
      logger.error('Error opening portal', err, { source: 'BillingContext' })
      throw err
    }
  }

  const getUsagePercentage = (metric: keyof Usage): number => {
    if (!usage || !usage[metric]) return 0
    
    const data = usage[metric] as UsageMetric
    if (data.unlimited) return 0
    if (data.limit === 0) return data.used > 0 ? 100 : 0
    
    return Math.min(100, Math.round((data.used / data.limit) * 100))
  }

  const isFeatureAvailable = (feature: string): boolean => {
    if (!subscription?.features) return false
    return !!subscription.features[feature]
  }

  return (
    <BillingContext.Provider
      value={{
        subscription,
        usage,
        loading,
        error,
        refetch: fetchBillingData,
        checkLimit,
        createCheckoutSession,
        openBillingPortal,
        getUsagePercentage,
        isFeatureAvailable,
      }}
    >
      {children}
    </BillingContext.Provider>
  )
}

export function useBilling() {
  const context = useContext(BillingContext)
  if (context === undefined) {
    throw new Error('useBilling must be used within a BillingProvider')
  }
  return context
}

