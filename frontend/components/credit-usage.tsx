'use client'

import { useState, useEffect, useCallback } from 'react'
import { Coins, TrendingUp, AlertTriangle, Loader2, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { useRouter } from 'next/navigation'

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

interface UsageSummary {
  by_service: Record<string, { credits: number; cost_cents: number; calls: number }>
  totals: { credits: number; cost_cents: number; api_calls: number }
  period_start: string
  period_end: string
}

interface CreditUsageProps {
  className?: string
  onBuyCredits?: () => void
}

export function CreditUsage({ className, onBuyCredits }: CreditUsageProps) {
  const router = useRouter()
  const [balance, setBalance] = useState<CreditBalance | null>(null)
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [showDetails, setShowDetails] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [balanceRes, usageRes] = await Promise.all([
        api.get<CreditBalance>('/api/v1/credits/balance'),
        api.get<UsageSummary>('/api/v1/credits/usage/summary')
      ])
      
      if (balanceRes.error) throw new Error(balanceRes.error.message)
      if (usageRes.error) throw new Error(usageRes.error.message)
      
      setBalance(balanceRes.data)
      setUsage(usageRes.data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load credits')
    } finally {
      setLoading(false)
    }
  }, [])

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
            <p className="text-sm text-slate-500 mt-1">Onbeperkte credits</p>
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
                <span className="text-sm text-slate-500 ml-1">beschikbaar</span>
              </div>
              {periodEnd && (
                <span className="text-xs text-slate-400">
                  tot {periodEnd}
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
                {balance.subscription_credits_remaining.toFixed(1)} abonnement
                {balance.pack_credits_remaining > 0 && (
                  <> + {balance.pack_credits_remaining.toFixed(1)} packs</>
                )}
              </span>
              <span>{balance.subscription_credits_used.toFixed(1)} gebruikt</span>
            </div>
          </>
        )}

        {/* Warning/Action */}
        {isExhausted && (
          <div className="mt-3 pt-3 border-t border-red-200 dark:border-red-800">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-4 w-4 text-red-500" />
              <span className="text-sm font-medium text-red-600 dark:text-red-400">
                Credits op!
              </span>
            </div>
            <Button
              size="sm"
              onClick={onBuyCredits || (() => router.push('/pricing'))}
              className="w-full bg-red-600 hover:bg-red-700"
            >
              Credits Bijkopen
            </Button>
          </div>
        )}

        {isCritical && !isExhausted && (
          <div className="mt-3 pt-3 border-t border-amber-200 dark:border-amber-800">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              <span className="text-sm text-amber-600 dark:text-amber-400">
                Bijna op! Nog {balance.total_credits_available.toFixed(1)} credits
              </span>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={onBuyCredits || (() => router.push('/pricing'))}
              className="w-full border-amber-300 text-amber-700 hover:bg-amber-50"
            >
              Credits Bijkopen
            </Button>
          </div>
        )}
      </div>

      {/* Usage Breakdown (Collapsible) */}
      {usage && !balance.is_unlimited && (
        <div className="rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="w-full flex items-center justify-between p-3 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-slate-400" />
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Verbruik deze maand
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-500">
                {usage.totals.credits?.toFixed(1) || '0'} credits
              </span>
              {showDetails ? (
                <ChevronUp className="h-4 w-4 text-slate-400" />
              ) : (
                <ChevronDown className="h-4 w-4 text-slate-400" />
              )}
            </div>
          </button>

          {showDetails && (
            <div className="p-3 pt-0 border-t border-slate-100 dark:border-slate-800">
              <div className="space-y-2 mt-3">
                {Object.entries(usage.by_service).map(([service, data]) => (
                  <div key={service} className="flex items-center justify-between text-sm">
                    <span className="text-slate-600 dark:text-slate-400 capitalize">
                      {formatServiceName(service)}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="text-slate-500 text-xs">
                        {data.calls}x
                      </span>
                      <span className="tabular-nums font-medium text-slate-700 dark:text-slate-300">
                        {data.credits?.toFixed(2) || '0'} cr
                      </span>
                    </div>
                  </div>
                ))}
              </div>
              {Object.keys(usage.by_service).length === 0 && (
                <p className="text-sm text-slate-400 text-center py-2">
                  Nog geen verbruik deze maand
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Helper to format service names nicely
function formatServiceName(service: string): string {
  const names: Record<string, string> = {
    'research_analysis': 'Research',
    'discovery': 'Prospect Discovery',
    'preparation': 'Meeting Prep',
    'followup': 'Follow-up',
    'followup_summary': 'Follow-up Summary',
    'followup_action_commercial_analysis': 'Deal Analysis',
    'followup_action_sales_coaching': 'Sales Coaching',
    'followup_action_customer_report': 'Klantverslag',
    'followup_action_action_items': 'Action Items',
    'followup_action_internal_report': 'CRM Notes',
    'followup_action_share_email': 'Follow-up Email',
    'transcription': 'Transcriptie',
    'contact_search': 'Contact Search',
  }
  return names[service] || service.replace(/_/g, ' ')
}

