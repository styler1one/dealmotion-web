'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { User } from '@supabase/supabase-js'
import { 
  Building2, 
  Search, 
  Plus,
  ChevronRight,
  MapPin,
  Users,
  Target,
  FileText,
  Calendar,
  Mail,
  RefreshCw,
  TrendingUp,
  ArrowUpDown,
  Filter,
  BarChart3,
  Trash2
} from 'lucide-react'
import { DashboardLayout } from '@/components/layout/dashboard-layout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/use-toast'
import { useConfirmDialog } from '@/components/confirm-dialog'
import { Icons } from '@/components/icons'
import { api } from '@/lib/api'
import { Prospect } from '@/types'
import { getProspectStatusColor } from '@/lib/constants/activity'
import { smartDate } from '@/lib/date-utils'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { ResearchForm } from '@/components/forms'

// Status configurations
const STATUS_ORDER = ['new', 'researching', 'qualified', 'meeting_scheduled', 'proposal_sent', 'won', 'lost', 'inactive']
const STATUS_COLORS: Record<string, string> = {
  new: 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800',
  researching: 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800',
  qualified: 'bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
  meeting_scheduled: 'bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800',
  proposal_sent: 'bg-cyan-100 dark:bg-cyan-900/50 text-cyan-700 dark:text-cyan-300 border-cyan-200 dark:border-cyan-800',
  won: 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 border-green-200 dark:border-green-800',
  lost: 'bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800',
  inactive: 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-slate-700'
}

interface ProspectWithCounts extends Prospect {
  research_count?: number
  prep_count?: number
  followup_count?: number
  contact_count?: number
}

interface ProspectStats {
  total: number
  by_status: Record<string, number>
}

export default function ProspectsPage() {
  const router = useRouter()
  const t = useTranslations('prospects')
  const tCommon = useTranslations('common')
  const { toast } = useToast()
  const { confirm } = useConfirmDialog()
  
  const supabase = createClientComponentClient()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [prospects, setProspects] = useState<ProspectWithCounts[]>([])
  const [stats, setStats] = useState<ProspectStats>({ total: 0, by_status: {} })
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<'last_activity_at' | 'company_name' | 'created_at'>('last_activity_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  
  // Research Sheet state - for adding new prospects
  const [researchSheetOpen, setResearchSheetOpen] = useState(false)
  
  // Fetch prospects
  const fetchProspects = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        sort_by: sortBy,
        sort_order: sortOrder,
        limit: '50'
      })
      if (statusFilter) params.append('status', statusFilter)
      if (searchQuery && searchQuery.length >= 2) params.append('search', searchQuery)
      
      const { data, error } = await api.get<{ prospects: ProspectWithCounts[], total: number }>(
        `/api/v1/prospects?${params.toString()}`
      )
      
      if (error) {
        throw new Error(error.message)
      }
      
      setProspects(data?.prospects || [])
    } catch (error) {
      console.error('Error loading prospects:', error)
      toast({ variant: "destructive", title: t('errors.loadFailed') })
    }
  }, [sortBy, sortOrder, statusFilter, searchQuery, t, toast])
  
  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const { data, error } = await api.get<ProspectStats>('/api/v1/prospects/stats')
      if (!error && data) {
        setStats(data)
      }
    } catch (error) {
      console.error('Error loading stats:', error)
    }
  }, [])
  
  // Initial load
  useEffect(() => {
    async function init() {
      try {
        const { data: { user } } = await supabase.auth.getUser()
        setUser(user)
        
        if (user) {
          await Promise.all([fetchProspects(), fetchStats()])
        }
      } catch (error) {
        console.error('Error initializing:', error)
      } finally {
        setLoading(false)
      }
    }
    
    init()
  }, [supabase])
  
  // Refetch when filters change
  useEffect(() => {
    if (user && !loading) {
      fetchProspects()
    }
  }, [sortBy, sortOrder, statusFilter, searchQuery, user, loading, fetchProspects])
  
  // Delete prospect
  const handleDeleteProspect = async (prospectId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    
    const confirmed = await confirm({
      title: t('confirm.deleteTitle'),
      description: t('confirm.deleteDescription'),
      confirmLabel: t('confirm.deleteButton'),
      cancelLabel: tCommon('cancel'),
      variant: 'danger'
    })
    
    if (!confirmed) return
    
    try {
      const { error } = await api.delete(`/api/v1/prospects/${prospectId}`)
      
      if (!error) {
        await Promise.all([fetchProspects(), fetchStats()])
        toast({
          title: t('toast.deleted'),
          description: t('toast.deletedDesc'),
        })
      } else {
        throw new Error('Delete failed')
      }
    } catch (error) {
      console.error('Delete failed:', error)
      toast({
        variant: "destructive",
        title: t('toast.deleteFailed'),
        description: t('toast.deleteFailedDesc'),
      })
    }
  }
  
  // Toggle sort
  const handleSort = (field: typeof sortBy) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('desc')
    }
  }

  if (loading) {
    return (
      <DashboardLayout user={user}>
        <div className="flex items-center justify-center h-full">
          <div className="text-center space-y-4">
            <Icons.spinner className="h-8 w-8 animate-spin text-purple-600 mx-auto" />
            <p className="text-slate-500 dark:text-slate-400">{tCommon('loading')}</p>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  if (!user) {
    router.push('/login')
    return null
  }

  // Calculate quick stats
  const activeProspects = prospects.filter(p => !['won', 'lost', 'inactive'].includes(p.status)).length
  const qualifiedProspects = prospects.filter(p => p.status === 'qualified').length
  
  return (
    <DashboardLayout user={user}>
      <div className="p-4 lg:p-6">
        {/* Page Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-1 flex items-center gap-2">
            <Building2 className="w-7 h-7 text-purple-600" />
            {t('title')}
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            {t('subtitle')}
          </p>
        </div>

        {/* Two Column Layout */}
        <div className="flex gap-6">
          
          {/* Left Column - Prospects List */}
          <div className="flex-1 min-w-0">
            {/* Search & Sort Bar */}
            <div className="flex items-center gap-3 mb-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input
                  placeholder={t('search.placeholder')}
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              
              <Button variant="ghost" size="sm" onClick={() => { fetchProspects(); fetchStats() }}>
                <RefreshCw className="h-4 w-4" />
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleSort('company_name')}
                className={sortBy === 'company_name' ? 'border-purple-300 dark:border-purple-700' : ''}
              >
                A-Z
                {sortBy === 'company_name' && (
                  <ArrowUpDown className="h-3 w-3 ml-1" />
                )}
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleSort('last_activity_at')}
                className={sortBy === 'last_activity_at' ? 'border-purple-300 dark:border-purple-700' : ''}
              >
                {t('sort.activity')}
                {sortBy === 'last_activity_at' && (
                  <ArrowUpDown className="h-3 w-3 ml-1" />
                )}
              </Button>
            </div>

            {/* Prospects Grid */}
            {prospects.length === 0 ? (
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-12 text-center">
                <Building2 className="h-16 w-16 text-slate-200 dark:text-slate-700 mx-auto mb-4" />
                <h3 className="font-semibold text-slate-700 dark:text-slate-200 mb-2">{t('empty.title')}</h3>
                <p className="text-slate-500 dark:text-slate-400 text-sm mb-4">
                  {t('empty.description')}
                </p>
                <Button onClick={() => setResearchSheetOpen(true)} className="bg-purple-600 hover:bg-purple-700">
                  <Search className="w-4 h-4 mr-2" />
                  {t('actions.startResearch')}
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {prospects.map(prospect => (
                  <div
                    key={prospect.id}
                    className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 hover:shadow-md dark:hover:shadow-slate-800/50 hover:border-purple-300 dark:hover:border-purple-700 transition-all cursor-pointer group"
                    onClick={() => router.push(`/dashboard/prospects/${prospect.id}`)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        {/* Company Name & Status */}
                        <div className="flex items-center gap-2 mb-2">
                          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                            <Building2 className="w-5 h-5 text-white" />
                          </div>
                          <div className="min-w-0">
                            <h4 className="font-semibold text-slate-900 dark:text-white truncate group-hover:text-purple-600 dark:group-hover:text-purple-400 transition">
                              {prospect.company_name}
                            </h4>
                            <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                              {prospect.industry && <span>{prospect.industry}</span>}
                              {(prospect.city || prospect.country) && (
                                <span className="flex items-center gap-1">
                                  <MapPin className="w-3 h-3" />
                                  {[prospect.city, prospect.country].filter(Boolean).join(', ')}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                        
                        {/* Activity Indicators */}
                        <div className="flex items-center gap-4 mt-3">
                          <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                            <FileText className="w-3.5 h-3.5" />
                            <span>{prospect.research_count || 0}</span>
                          </div>
                          <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                            <Calendar className="w-3.5 h-3.5" />
                            <span>{prospect.prep_count || 0}</span>
                          </div>
                          <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                            <Mail className="w-3.5 h-3.5" />
                            <span>{prospect.followup_count || 0}</span>
                          </div>
                          <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                            <Users className="w-3.5 h-3.5" />
                            <span>{prospect.contact_count || 0}</span>
                          </div>
                          
                          <span className="text-xs text-slate-400 ml-auto">
                            {prospect.last_activity_at && smartDate(prospect.last_activity_at)}
                          </span>
                        </div>
                      </div>
                      
                      {/* Actions */}
                      <div className="flex items-center gap-2 ml-4">
                        <Badge className={`${STATUS_COLORS[prospect.status] || STATUS_COLORS.new} border text-xs`}>
                          {t(`status.${prospect.status}`)}
                        </Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-slate-400 hover:text-red-600 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => handleDeleteProspect(prospect.id, e)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                        <ChevronRight className="w-5 h-5 text-slate-300 dark:text-slate-600 group-hover:text-purple-500 transition" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right Column - Sticky Sidebar */}
          <div className="w-80 flex-shrink-0 hidden lg:block">
            <div className="sticky top-4 space-y-4">
              
              {/* Stats Panel */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-purple-500" />
                  {t('stats.title')}
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-purple-50 dark:bg-purple-900/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">{stats.total}</p>
                    <p className="text-xs text-purple-700 dark:text-purple-300">{t('stats.total')}</p>
                  </div>
                  <div className="bg-emerald-50 dark:bg-emerald-900/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{activeProspects}</p>
                    <p className="text-xs text-emerald-700 dark:text-emerald-300">{t('stats.active')}</p>
                  </div>
                </div>
                
                {/* New Prospect Button - directly under stats */}
                <Button 
                  className="w-full mt-4 bg-purple-600 hover:bg-purple-700" 
                  onClick={() => setResearchSheetOpen(true)}
                >
                  <Plus className="w-4 h-4 mr-2" />
                  {t('actions.newProspect')}
                </Button>
              </div>

              {/* Quick Filters */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <Filter className="h-4 w-4 text-slate-400" />
                  {t('filters.title')}
                </h3>
                <div className="space-y-2">
                  <button
                    onClick={() => setStatusFilter(null)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition ${
                      !statusFilter 
                        ? 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300' 
                        : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400'
                    }`}
                  >
                    {t('filters.all')} ({stats.total})
                  </button>
                  {STATUS_ORDER.slice(0, 6).map(status => (
                    <button
                      key={status}
                      onClick={() => setStatusFilter(status === statusFilter ? null : status)}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition flex items-center justify-between ${
                        statusFilter === status 
                          ? 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300' 
                          : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400'
                      }`}
                    >
                      <span>{t(`status.${status}`)}</span>
                      <span className="text-xs opacity-60">{stats.by_status[status] || 0}</span>
                    </button>
                  ))}
                </div>
              </div>

            </div>
          </div>
        </div>
        
        {/* Research Sheet - Opens when clicking "New Prospect" */}
        <Sheet open={researchSheetOpen} onOpenChange={setResearchSheetOpen}>
          <SheetContent side="right" className="sm:max-w-md overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Search className="w-5 h-5 text-blue-600" />
                {t('sheet.newProspect')}
              </SheetTitle>
              <SheetDescription>
                {t('sheet.newProspectDesc')}
              </SheetDescription>
            </SheetHeader>
            <div className="mt-6">
              <ResearchForm
                onSuccess={(result) => {
                  setResearchSheetOpen(false)
                  toast({ title: t('toast.researchStarted') })
                  // Navigate directly to the new prospect's hub
                  router.push(`/dashboard/prospects/${result.prospect_id}`)
                }}
                onCancel={() => setResearchSheetOpen(false)}
                isSheet={true}
              />
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </DashboardLayout>
  )
}
