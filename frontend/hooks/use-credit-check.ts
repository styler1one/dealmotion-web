'use client'

import { useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'
import { useInsufficientCredits } from '@/components/insufficient-credits-modal'

interface CreditCheckResult {
  allowed: boolean
  action: string
  required_credits: number
  available_credits: number
  is_unlimited: boolean
}

/**
 * Hook for checking credits before expensive operations.
 * 
 * Usage:
 * ```tsx
 * const { checkCredits, handleCreditError } = useCreditCheck()
 * 
 * // Pre-check before starting
 * const allowed = await checkCredits('research_flow')
 * if (!allowed) return
 * 
 * // Or handle errors from API responses
 * const { error, status } = await api.post('/api/v1/research/start', ...)
 * if (error && status === 402) {
 *   handleCreditError(error)
 *   return
 * }
 * ```
 */
export function useCreditCheck() {
  const { toast } = useToast()
  const { showInsufficientCredits } = useInsufficientCredits()
  const router = useRouter()

  /**
   * Check if user has enough credits for an action.
   * Shows modal automatically if insufficient.
   */
  const checkCredits = useCallback(async (action: string, quantity = 1): Promise<boolean> => {
    try {
      const { data, error, status } = await api.get<CreditCheckResult>(
        `/api/v1/credits/check/${action}?quantity=${quantity}`
      )
      
      if (error) {
        console.error('Credit check failed:', error)
        toast({
          title: 'Credit check failed',
          description: error.message,
          variant: 'destructive',
        })
        return false
      }

      if (!data?.allowed) {
        showInsufficientCredits({
          action,
          requiredCredits: data?.required_credits,
          availableCredits: data?.available_credits,
        })
        return false
      }

      return true
    } catch (err) {
      console.error('Credit check error:', err)
      return false
    }
  }, [toast, showInsufficientCredits])

  /**
   * Handle a 402 insufficient credits error from an API response.
   * Call this when you get a 402 status back from the API.
   */
  const handleCreditError = useCallback((error: {
    message: string
    code?: string
    details?: {
      error?: string
      required?: number
      available?: number
      action?: string
    }
  }) => {
    if (error.code === 'insufficient_credits' || error.details?.error === 'insufficient_credits') {
      showInsufficientCredits({
        action: error.details?.action,
        requiredCredits: error.details?.required,
        availableCredits: error.details?.available,
      })
    } else {
      // Generic 402 - still show upgrade option
      toast({
        title: 'Upgrade Required',
        description: error.message || 'You need to upgrade or buy credits to continue.',
        variant: 'destructive',
      })
    }
  }, [toast, showInsufficientCredits])

  /**
   * Navigate to settings subscription section.
   */
  const goToSubscription = useCallback(() => {
    router.push('/dashboard/settings')
  }, [router])

  return {
    checkCredits,
    handleCreditError,
    goToSubscription,
  }
}

