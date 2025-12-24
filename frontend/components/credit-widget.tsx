'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Coins, AlertTriangle, Infinity, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { useTranslations } from 'next-intl'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

interface CreditBalance {
  subscription_credits_total: number
  subscription_credits_used: number
  subscription_credits_remaining: number
  pack_credits_remaining: number
  total_credits_available: number
  is_unlimited: boolean
  is_free_plan: boolean
  period_end: string | null
}

interface CreditWidgetProps {
  className?: string
}

/**
 * Compact credit balance widget for header.
 * Shows current credit balance with visual indicator.
 * Clicking navigates to settings/subscription.
 */
export function CreditWidget({ className }: CreditWidgetProps) {
  const router = useRouter()
  const t = useTranslations('credits')
  const [balance, setBalance] = useState<CreditBalance | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const fetchBalance = useCallback(async () => {
    try {
      const { data, error: apiError } = await api.get<CreditBalance>('/api/v1/credits/balance')
      if (apiError) {
        setError(true)
        return
      }
      setBalance(data)
      setError(false)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchBalance()
    // Refresh every 5 minutes
    const interval = setInterval(fetchBalance, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [fetchBalance])

  const handleClick = () => {
    router.push('/dashboard/settings')
  }

  if (loading) {
    return (
      <div className={cn("flex items-center gap-1.5 px-2 py-1", className)}>
        <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
      </div>
    )
  }

  if (error || !balance) {
    return null // Hide widget on error
  }

  // Calculate status
  const totalCredits = balance.subscription_credits_total + balance.pack_credits_remaining
  const percentage = balance.is_unlimited ? 0 : totalCredits > 0 
    ? Math.round((balance.subscription_credits_used / totalCredits) * 100) 
    : 100
  const isCritical = !balance.is_unlimited && balance.total_credits_available <= 2
  const isWarning = !balance.is_unlimited && percentage >= 70
  const isExhausted = !balance.is_unlimited && balance.total_credits_available <= 0

  // Format remaining days - only for paid plans (free plan credits don't reset)
  const daysLeft = balance.period_end && !balance.is_free_plan
    ? Math.max(0, Math.ceil((new Date(balance.period_end).getTime() - Date.now()) / (1000 * 60 * 60 * 24)))
    : null

  return (
    <TooltipProvider>
      <Tooltip delayDuration={300}>
        <TooltipTrigger asChild>
          <button
            onClick={handleClick}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition-all",
              "hover:bg-slate-100 dark:hover:bg-slate-800",
              "focus:outline-none focus:ring-2 focus:ring-blue-500/20",
              isExhausted && "bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/30",
              isCritical && !isExhausted && "bg-amber-50 dark:bg-amber-900/20 hover:bg-amber-100 dark:hover:bg-amber-900/30",
              className
            )}
          >
            {/* Icon */}
            {isExhausted ? (
              <AlertTriangle className="h-4 w-4 text-red-500" />
            ) : balance.is_unlimited ? (
              <Infinity className="h-4 w-4 text-emerald-500" />
            ) : (
              <Coins className={cn(
                "h-4 w-4",
                isCritical ? "text-amber-500" : "text-emerald-500"
              )} />
            )}

            {/* Balance Display */}
            <span className={cn(
              "text-sm font-medium tabular-nums",
              isExhausted ? "text-red-600 dark:text-red-400" :
              isCritical ? "text-amber-600 dark:text-amber-400" :
              balance.is_unlimited ? "text-emerald-600 dark:text-emerald-400" :
              "text-slate-700 dark:text-slate-200"
            )}>
              {balance.is_unlimited ? '∞' : balance.total_credits_available.toFixed(1)}
            </span>

            {/* Mini progress bar - only for non-unlimited */}
            {!balance.is_unlimited && (
              <div className="hidden sm:block w-12 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    isExhausted ? "bg-red-500" :
                    isCritical ? "bg-amber-500" :
                    isWarning ? "bg-amber-400" :
                    "bg-emerald-500"
                  )}
                  style={{ width: `${Math.max(5, 100 - percentage)}%` }}
                />
              </div>
            )}
          </button>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-[200px]">
          <div className="space-y-1">
            <p className="font-medium">
              {balance.is_unlimited ? t('unlimited') : t('creditsAvailable', { credits: balance.total_credits_available.toFixed(1) })}
            </p>
            {!balance.is_unlimited && (
              <>
                <p className="text-xs text-slate-500">
                  {balance.subscription_credits_remaining.toFixed(1)} {t('subscription')}
                  {balance.pack_credits_remaining > 0 && ` + ${balance.pack_credits_remaining.toFixed(1)} ${t('extra')}`}
                </p>
                {daysLeft !== null && (
                  <p className="text-xs text-slate-400">
                    {daysLeft === 1 ? t('resetInDays', { days: daysLeft }) : t('resetInDaysPlural', { days: daysLeft })}
                  </p>
                )}
                {isExhausted && (
                  <p className="text-xs text-red-500 font-medium">
                    {t('clickToBuyMore')}
                  </p>
                )}
              </>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

