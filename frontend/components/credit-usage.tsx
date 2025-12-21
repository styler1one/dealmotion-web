'use client'

import { useState, useEffect, useCallback } from 'react'
import { Coins, AlertTriangle, Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'

// Types matching backend API
interface CreditBalance {
  subscription_credits_total: number
  subscription_credits_used: number
  subscription_credits_remaining: number
  pack_credits_remaining: number
  total_credits_available: number
  is_unlimited: boolean
  period_start: string | null
  period_end: string | null
}

interface CreditUsageProps {
  className?: string
}

export function CreditUsage({ className }: CreditUsageProps) {
  const router = useRouter()
  const t = useTranslations('credits')
  const [balance, setBalance] = useState<CreditBalance | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const balanceRes = await api.get<CreditBalance>('/api/v1/credits/balance')
      
      if (balanceRes.error) throw new Error(balanceRes.error.message)
      
      setBalance(balanceRes.data)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('errorLoading'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  if (loading) {
    return (
      <div className={cn("p-4 flex items-center justify-center", className)}>
        <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
      </div>
    )
  }

  if (error) {
    return (
      <div className={cn("p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800", className)}>
        <div className="flex items-center justify-between">
          <span className="text-sm text-red-600 dark:text-red-400">{error}</span>
          <Button variant="ghost" size="sm" onClick={fetchData}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>
    )
  }

  if (!balance) return null

  // Calculate usage percentage
  const totalCredits = balance.subscription_credits_total + balance.pack_credits_remaining
  const usedCredits = balance.subscription_credits_used
  const percentage = balance.is_unlimited ? 0 : totalCredits > 0 ? Math.min(100, Math.round((usedCredits / totalCredits) * 100)) : 100
  const isWarning = !balance.is_unlimited && percentage >= 70
  const isCritical = !balance.is_unlimited && percentage >= 90
  const isExhausted = !balance.is_unlimited && balance.total_credits_available <= 0

  // Format period end date
  const periodEnd = balance.period_end ? new Date(balance.period_end).toLocaleDateString('nl-NL', { 
    day: 'numeric', 
    month: 'short' 
  }) : null

  return (
    <div className={cn("space-y-4", className)}>
      {/* Main Balance Card */}
      <div className={cn(
        "p-4 rounded-lg border",
        isExhausted ? "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800" :
        isCritical ? "bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800" :
        "bg-slate-50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700"
      )}>
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Coins className={cn(
              "h-5 w-5",
              isExhausted ? "text-red-500" :
              isCritical ? "text-amber-500" :
              "text-emerald-500"
            )} />
            <span className="font-medium text-slate-900 dark:text-white">Credits</span>
          </div>
          {balance.is_unlimited ? (
            <Badge className="bg-emerald-500 text-white">Unlimited</Badge>
          ) : (
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={fetchData}
              className="h-7 w-7 p-0"
            >
              <RefreshCw className="h-3 w-3" />
            </Button>
          )}
        </div>

        {/* Balance Display */}
        {balance.is_unlimited ? (
          <div className="text-center py-2">
            <span className="text-3xl font-bold text-emerald-600 dark:text-emerald-400">∞</span>
            <p className="text-sm text-slate-500 mt-1">{t('unlimited')}</p>
          </div>
        ) : (
          <>
            <div className="flex items-baseline justify-between mb-2">
              <div>
                <span className={cn(
                  "text-3xl font-bold tabular-nums",
                  isExhausted ? "text-red-600 dark:text-red-400" :
                  isCritical ? "text-amber-600 dark:text-amber-400" :
                  "text-slate-900 dark:text-white"
                )}>
                  {balance.total_credits_available.toFixed(1)}
                </span>
                <span className="text-sm text-slate-500 ml-1">{t('available')}</span>
              </div>
              {periodEnd && (
                <span className="text-xs text-slate-400">
                  {t('until')} {periodEnd}
                </span>
              )}
            </div>

            {/* Progress Bar */}
            <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-300",
                  isExhausted ? "bg-red-500" :
                  isCritical ? "bg-amber-500" :
                  isWarning ? "bg-amber-400" :
                  "bg-emerald-500"
                )}
                style={{ width: `${100 - percentage}%` }}
              />
            </div>

            {/* Breakdown */}
            <div className="flex items-center justify-between mt-2 text-xs text-slate-500">
              <span>
                {balance.subscription_credits_remaining.toFixed(1)} {t('subscription')}
                {balance.pack_credits_remaining > 0 && (
                  <> + {balance.pack_credits_remaining.toFixed(1)} {t('packs')}</>
                )}
              </span>
              <span>{balance.subscription_credits_used.toFixed(1)} {t('used')}</span>
            </div>
          </>
        )}

        {/* Warning/Action */}
        {isExhausted && (
          <div className="mt-3 pt-3 border-t border-red-200 dark:border-red-800">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-4 w-4 text-red-500" />
              <span className="text-sm font-medium text-red-600 dark:text-red-400">
                {t('exhausted')}
              </span>
            </div>
            <Button
              size="sm"
              onClick={() => router.push('/dashboard/settings')}
              className="w-full bg-red-600 hover:bg-red-700"
            >
              {t('buyCredits')}
            </Button>
          </div>
        )}

        {isCritical && !isExhausted && (
          <div className="mt-3 pt-3 border-t border-amber-200 dark:border-amber-800">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              <span className="text-sm text-amber-600 dark:text-amber-400">
                {t('almostEmpty', { credits: balance.total_credits_available.toFixed(1) })}
              </span>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => router.push('/dashboard/settings')}
              className="w-full border-amber-300 text-amber-700 hover:bg-amber-50"
            >
              {t('buyCredits')}
            </Button>
          </div>
        )}
      </div>

    </div>
  )
}

