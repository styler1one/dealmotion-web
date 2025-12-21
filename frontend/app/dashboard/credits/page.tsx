'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { DashboardLayout } from '@/components/layout'
import { 
  ArrowLeft, 
  Coins, 
  TrendingUp, 
  Filter,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RefreshCw,
  Search,
  Calendar,
  ArrowDownRight,
  ArrowUpRight,
  Package,
  Sparkles,
  FileText,
  Users,
  Mic,
  Target,
  MessageSquare,
  Brain,
  Clock
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { CreditPacksModal } from '@/components/credit-packs-modal'
import { useTranslations } from 'next-intl'
import type { User } from '@supabase/supabase-js'

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

interface CreditTransaction {
  id: string
  transaction_type: string
  credits_amount: number
  balance_after: number
  description: string | null
  reference_type: string | null
  user_id: string | null
  metadata: Record<string, unknown> | null
  created_at: string
}

interface PeriodStats {
  total_consumed: number
  total_added: number
  transaction_count: number
  by_action: Array<{
    action: string
    label: string
    credits: number
  }>
}

interface DetailedUsageResponse {
  transactions: CreditTransaction[]
  total_count: number
  page: number
  page_size: number
  total_pages: number
  period_stats: PeriodStats
}

// Action icons mapping
const ACTION_ICONS: Record<string, React.ReactNode> = {
  research_flow: <Search className="h-4 w-4" />,
  prospect_discovery: <Target className="h-4 w-4" />,
  preparation: <FileText className="h-4 w-4" />,
  followup: <MessageSquare className="h-4 w-4" />,
  followup_action: <Sparkles className="h-4 w-4" />,
  transcription_minute: <Mic className="h-4 w-4" />,
  contact_search: <Users className="h-4 w-4" />,
  contact_analysis: <Users className="h-4 w-4" />,
  embedding_chunk: <Brain className="h-4 w-4" />,
  subscription_reset: <Calendar className="h-4 w-4" />,
  pack_purchase: <Package className="h-4 w-4" />,
  subscription: <Coins className="h-4 w-4" />,
}

// Action colors
const ACTION_COLORS: Record<string, string> = {
  research_flow: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  prospect_discovery: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  preparation: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  followup: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  followup_action: 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400',
  transcription_minute: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400',
  contact_search: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
  contact_analysis: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
  subscription_reset: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  pack_purchase: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400',
}

export default function CreditsPage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const t = useTranslations('credits')
  
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  
  // Data states
  const [balance, setBalance] = useState<CreditBalance | null>(null)
  const [usageData, setUsageData] = useState<DetailedUsageResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  
  // Filter states
  const [page, setPage] = useState(1)
  const [filterType, setFilterType] = useState<string>('all')
  const [filterAction, setFilterAction] = useState<string>('all')
  
  const pageSize = 20
  
  // Fetch user
  useEffect(() => {
    const getUser = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) {
        router.push('/login')
        return
      }
      setUser(user)
    }
    getUser()
  }, [supabase, router])
  
  // Fetch data
  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)
    
    try {
      // Build query params
      const params = new URLSearchParams()
      params.set('page', page.toString())
      params.set('page_size', pageSize.toString())
      if (filterType !== 'all') params.set('filter_type', filterType)
      if (filterAction !== 'all') params.set('filter_action', filterAction)
      
      const [balanceRes, usageRes] = await Promise.all([
        api.get<CreditBalance>('/api/v1/credits/balance'),
        api.get<DetailedUsageResponse>(`/api/v1/credits/history/detailed?${params.toString()}`)
      ])
      
      if (balanceRes.error) throw new Error(balanceRes.error.message)
      if (usageRes.error) throw new Error(usageRes.error.message)
      
      setBalance(balanceRes.data)
      setUsageData(usageRes.data)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('errorLoading'))
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [page, filterType, filterAction, t])
  
  useEffect(() => {
    if (user) {
      fetchData()
    }
  }, [user, fetchData])
  
  // Reset page when filters change
  useEffect(() => {
    setPage(1)
  }, [filterType, filterAction])
  
  // Format date
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return new Intl.DateTimeFormat('en-US', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date)
  }
  
  // Format relative time
  const formatRelativeTime = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)
    
    if (diffMins < 1) return t('justNow')
    if (diffMins < 60) return t('minutesAgo', { minutes: diffMins })
    if (diffHours < 24) return t('hoursAgo', { hours: diffHours })
    if (diffDays < 7) return t('daysAgo', { days: diffDays })
    return formatDate(dateStr)
  }
  
  // Get icon for transaction
  const getTransactionIcon = (tx: CreditTransaction) => {
    const refType = tx.reference_type || tx.transaction_type
    return ACTION_ICONS[refType] || <Coins className="h-4 w-4" />
  }
  
  // Get color for transaction
  const getTransactionColor = (tx: CreditTransaction) => {
    const refType = tx.reference_type || tx.transaction_type
    return ACTION_COLORS[refType] || 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
  }
  
  // Calculate usage percentage
  const getUsagePercentage = () => {
    if (!balance || balance.is_unlimited) return 0
    const total = balance.subscription_credits_total + balance.pack_credits_remaining
    if (total <= 0) return 100
    return Math.min(100, Math.round((balance.subscription_credits_used / total) * 100))
  }
  
  if (loading && !usageData) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-slate-900">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <DashboardLayout user={user}>
      <div className="p-6 max-w-6xl">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => router.push('/dashboard/settings')}
            className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white mb-4 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            {t('backToSettings')}
          </button>
          
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600">
                <Coins className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                  {t('title')}
                </h1>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t('subtitle')}
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => fetchData(true)}
                disabled={refreshing}
                className="gap-2"
              >
                <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
                {t('refresh')}
              </Button>
              <CreditPacksModal />
            </div>
          </div>
        </div>
        
        {error && (
          <div className="mb-6 p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}
        
        {/* Balance Overview */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {/* Current Balance */}
          <Card className="md:col-span-1">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <span className="text-sm font-medium text-slate-500">{t('available')}</span>
                {balance?.is_unlimited ? (
                  <Badge className="bg-emerald-500 text-white">Unlimited</Badge>
                ) : null}
              </div>
              
              {balance?.is_unlimited ? (
                <div className="text-center">
                  <span className="text-5xl font-bold text-emerald-600 dark:text-emerald-400">∞</span>
                  <p className="text-sm text-slate-500 mt-1">{t('unlimited')}</p>
                </div>
              ) : (
                <>
                  <div className="flex items-baseline gap-1 mb-4">
                    <span className="text-4xl font-bold tabular-nums text-slate-900 dark:text-white">
                      {balance?.total_credits_available?.toFixed(1) || '0'}
                    </span>
                    <span className="text-sm text-slate-500">credits</span>
                  </div>
                  
                  {/* Progress bar */}
                  <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden mb-3">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all duration-300",
                        getUsagePercentage() >= 90 ? "bg-red-500" :
                        getUsagePercentage() >= 70 ? "bg-amber-500" :
                        "bg-emerald-500"
                      )}
                      style={{ width: `${100 - getUsagePercentage()}%` }}
                    />
                  </div>
                  
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>{balance?.subscription_credits_remaining?.toFixed(1) || 0} {t('subscription')}</span>
                    <span>{balance?.pack_credits_remaining?.toFixed(1) || 0} {t('packs')}</span>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
          
          {/* Period Stats */}
          <Card className="md:col-span-2">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <span className="text-sm font-medium text-slate-500">{t('thisPeriod')}</span>
                {balance?.period_end && (
                  <span className="text-xs text-slate-400 flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {t('expires')} {new Date(balance.period_end).toLocaleDateString('en-US', { day: 'numeric', month: 'short' })}
                  </span>
                )}
              </div>
              
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <div className="flex items-center gap-1 text-red-600 dark:text-red-400 mb-1">
                    <ArrowDownRight className="h-4 w-4" />
                    <span className="text-sm font-medium">{t('consumed')}</span>
                  </div>
                  <span className="text-2xl font-bold tabular-nums text-slate-900 dark:text-white">
                    {usageData?.period_stats?.total_consumed?.toFixed(1) || '0'}
                  </span>
                </div>
                
                <div>
                  <div className="flex items-center gap-1 text-green-600 dark:text-green-400 mb-1">
                    <ArrowUpRight className="h-4 w-4" />
                    <span className="text-sm font-medium">{t('added')}</span>
                  </div>
                  <span className="text-2xl font-bold tabular-nums text-slate-900 dark:text-white">
                    {usageData?.period_stats?.total_added?.toFixed(0) || '0'}
                  </span>
                </div>
                
                <div>
                  <div className="flex items-center gap-1 text-slate-600 dark:text-slate-400 mb-1">
                    <TrendingUp className="h-4 w-4" />
                    <span className="text-sm font-medium">{t('transactions')}</span>
                  </div>
                  <span className="text-2xl font-bold tabular-nums text-slate-900 dark:text-white">
                    {usageData?.period_stats?.transaction_count || 0}
                  </span>
                </div>
              </div>
              
              {/* Usage breakdown */}
              {usageData?.period_stats?.by_action && usageData.period_stats.by_action.length > 0 && (
                <div className="pt-4 border-t border-slate-200 dark:border-slate-700">
                  <span className="text-xs font-medium text-slate-500 mb-2 block">{t('usageByFunction')}</span>
                  <div className="flex flex-wrap gap-2">
                    {usageData.period_stats.by_action.slice(0, 6).map((item) => (
                      <div 
                        key={item.action}
                        className={cn(
                          "flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium",
                          ACTION_COLORS[item.action] || 'bg-slate-100 text-slate-700'
                        )}
                      >
                        {ACTION_ICONS[item.action]}
                        <span>{item.label}</span>
                        <span className="font-bold">{item.credits}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
        
        {/* Transaction History */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-slate-400" />
                  {t('transactionHistory')}
                </CardTitle>
                <CardDescription>
                  {t('allTransactionsDetails')}
                </CardDescription>
              </div>
              
              {/* Filters */}
              <div className="flex items-center gap-2">
                <Select value={filterType} onValueChange={setFilterType}>
                  <SelectTrigger className="w-[140px]">
                    <Filter className="h-4 w-4 mr-2" />
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('allTypes')}</SelectItem>
                    <SelectItem value="consumption">{t('consumption')}</SelectItem>
                    <SelectItem value="subscription_reset">{t('subscriptionType')}</SelectItem>
                    <SelectItem value="pack_purchase">{t('creditPacks')}</SelectItem>
                  </SelectContent>
                </Select>
                
                <Select value={filterAction} onValueChange={setFilterAction}>
                  <SelectTrigger className="w-[160px]">
                    <SelectValue placeholder="Function" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('allFunctions')}</SelectItem>
                    <SelectItem value="research_flow">Research</SelectItem>
                    <SelectItem value="preparation">Meeting Prep</SelectItem>
                    <SelectItem value="followup">Follow-up</SelectItem>
                    <SelectItem value="followup_action">Follow-up Actions</SelectItem>
                    <SelectItem value="transcription_minute">Transcription</SelectItem>
                    <SelectItem value="prospect_discovery">Discovery</SelectItem>
                    <SelectItem value="contact_search">Contacts</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
          
          <CardContent>
            {/* Transaction List */}
            <div className="space-y-2">
              {usageData?.transactions?.length === 0 ? (
                <div className="text-center py-12">
                  <Coins className="h-12 w-12 text-slate-300 mx-auto mb-4" />
                  <p className="text-slate-500">{t('noTransactionsYet')}</p>
                  <p className="text-sm text-slate-400 mt-1">
                    {filterType !== 'all' || filterAction !== 'all' 
                      ? t('tryOtherFilters') 
                      : t('startUsingDealMotion')}
                  </p>
                </div>
              ) : (
                usageData?.transactions?.map((tx) => (
                  <div
                    key={tx.id}
                    className="flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors border border-transparent hover:border-slate-200 dark:hover:border-slate-700"
                  >
                    <div className="flex items-center gap-3">
                      {/* Icon */}
                      <div className={cn(
                        "p-2 rounded-lg",
                        getTransactionColor(tx)
                      )}>
                        {getTransactionIcon(tx)}
                      </div>
                      
                      {/* Description */}
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">
                          {tx.description || tx.reference_type?.replace(/_/g, ' ') || tx.transaction_type}
                        </p>
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                          <span>{formatRelativeTime(tx.created_at)}</span>
                          {tx.metadata && Object.keys(tx.metadata).length > 0 && (
                            <>
                              <span>•</span>
                              <span className="text-slate-400">
                                {String(tx.metadata.company_name || tx.metadata.prospect_company || tx.metadata.contact_name || '')}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    {/* Amount */}
                    <div className="text-right">
                      <span className={cn(
                        "text-lg font-semibold tabular-nums",
                        tx.credits_amount < 0 
                          ? "text-red-600 dark:text-red-400" 
                          : "text-green-600 dark:text-green-400"
                      )}>
                        {tx.credits_amount > 0 ? '+' : ''}{tx.credits_amount.toFixed(2)}
                      </span>
                      <p className="text-xs text-slate-400">
                        {t('balance')}: {tx.balance_after >= 0 ? tx.balance_after.toFixed(1) : '∞'}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
            
            {/* Pagination */}
            {usageData && usageData.total_pages > 1 && (
              <div className="flex items-center justify-between mt-6 pt-4 border-t border-slate-200 dark:border-slate-700">
                <p className="text-sm text-slate-500">
                  {t('pageOf', { page: usageData.page, total: usageData.total_pages, count: usageData.total_count })}
                </p>
                
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page <= 1 || loading}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    {t('previous')}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(p => p + 1)}
                    disabled={page >= usageData.total_pages || loading}
                  >
                    {t('next')}
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
        
        {/* Info Box */}
        <div className="mt-6 p-4 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
          <div className="flex items-start gap-3">
            <Coins className="h-5 w-5 text-blue-500 mt-0.5" />
            <div>
              <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-1">
                {t('howCreditsWork')}
              </h4>
              <p className="text-sm text-blue-700 dark:text-blue-300">
                {t('howCreditsWorkDescription')}
              </p>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}

