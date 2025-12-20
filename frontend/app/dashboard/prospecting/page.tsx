'use client'

import { useState, useEffect, useCallback } from 'react'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { Toaster } from '@/components/ui/toaster'
import { DashboardLayout } from '@/components/layout'
import { useTranslations } from 'next-intl'
import { api } from '@/lib/api'
import { logger } from '@/lib/logger'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import type { User } from '@supabase/supabase-js'

interface DiscoveredProspect {
  id?: string
  company_name: string
  website?: string
  linkedin_url?: string
  inferred_sector?: string
  inferred_region?: string
  inferred_size?: string
  fit_score: number
  proposition_fit: number
  seller_fit: number
  intent_score: number
  recency_score: number
  fit_reason?: string
  key_signal?: string
  source_url?: string
  source_title?: string
  source_published_date?: string
  prospect_id?: string
  imported_at?: string
}

interface SearchResult {
  search_id: string
  status: string
  generated_queries: string[]
  prospects: DiscoveredProspect[]
  total_count: number
  reference_context?: string
  execution_time_seconds?: number
  error_message?: string
}

interface SearchHistoryItem {
  id: string
  region?: string
  sector?: string
  company_size?: string
  proposition?: string
  status: string
  results_count: number
  created_at: string
}

interface ServiceCheck {
  available: boolean
  has_sales_profile: boolean
  sales_profile_completeness: number
  has_company_profile: boolean
  company_profile_completeness: number
  ready: boolean
  recommendations: string[]
}

export default function ProspectingPage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const t = useTranslations('prospecting')
  
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [serviceCheck, setServiceCheck] = useState<ServiceCheck | null>(null)
  
  // Search form state
  const [region, setRegion] = useState('')
  const [sector, setSector] = useState('')
  const [companySize, setCompanySize] = useState('')
  const [proposition, setProposition] = useState('')
  const [targetRole, setTargetRole] = useState('')
  const [painPoint, setPainPoint] = useState('')
  const [referenceCustomers, setReferenceCustomers] = useState('')  // Comma-separated
  const [maxResults, setMaxResults] = useState(25)  // Default 25 results
  
  // Results state
  const [results, setResults] = useState<SearchResult | null>(null)
  const [history, setHistory] = useState<SearchHistoryItem[]>([])
  const [importingId, setImportingId] = useState<string | null>(null)
  const [rejectingId, setRejectingId] = useState<string | null>(null)
  
  // Delete dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [searchToDelete, setSearchToDelete] = useState<SearchHistoryItem | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Get user
  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      setUser(user)
    })
  }, [supabase])

  // Check service availability
  const checkService = useCallback(async () => {
    try {
      const { data, error } = await api.get<ServiceCheck>('/api/v1/prospecting/check')
      if (!error && data) {
        setServiceCheck(data)
      }
    } catch (error) {
      logger.error('Failed to check prospecting service', error)
    }
  }, [])

  // Fetch search history
  const fetchHistory = useCallback(async () => {
    try {
      const { data, error } = await api.get<{ searches: SearchHistoryItem[] }>('/api/v1/prospecting/searches')
      if (!error && data) {
        setHistory(data.searches || [])
      }
    } catch (error) {
      logger.error('Failed to fetch search history', error)
    }
  }, [])

  // Initial load
  useEffect(() => {
    Promise.all([checkService(), fetchHistory()]).finally(() => {
      setLoading(false)
    })
  }, [checkService, fetchHistory])

  // Poll for search results
  const pollSearchResults = async (searchId: string): Promise<SearchResult | null> => {
    const maxAttempts = 120 // 4 minutes max (2s intervals)
    let attempts = 0
    
    while (attempts < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, 2000)) // Wait 2 seconds
      
      const { data, error } = await api.get<SearchResult>(`/api/v1/prospecting/searches/${searchId}`)
      
      if (error) {
        logger.error('Failed to poll search', error)
        return null
      }
      
      if (data?.status === 'completed') {
        return data
      }
      
      if (data?.status === 'failed') {
        throw new Error(data.error_message || 'Search failed')
      }
      
      attempts++
    }
    
    throw new Error('Search timed out')
  }

  // Start prospecting search (async via Inngest)
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!proposition && !sector) {
      toast({
        variant: "destructive",
        title: t('errors.missingFields'),
        description: t('errors.missingFieldsDesc'),
      })
      return
    }
    
    setSearching(true)
    setResults(null)
    
    try {
      // Step 1: Start the search (returns search_id)
      const { data: startData, error: startError } = await api.post<{ search_id: string; status: string }>('/api/v1/prospecting/search', {
        region: region || undefined,
        sector: sector || undefined,
        company_size: companySize || undefined,
        proposition: proposition || undefined,
        target_role: targetRole || undefined,
        pain_point: painPoint || undefined,
        reference_customers: referenceCustomers 
          ? referenceCustomers.split(',').map(c => c.trim()).filter(c => c)
          : undefined,
        max_results: maxResults,
      })
      
      if (startError) {
        throw new Error(startError.message || String(startError))
      }
      
      if (!startData?.search_id) {
        throw new Error('No search ID returned')
      }
      
      // Step 2: Poll for results
      const result = await pollSearchResults(startData.search_id)
      
      if (result) {
        setResults(result)
        fetchHistory() // Refresh history
        
        toast({
          title: t('toast.searchComplete'),
          description: t('toast.searchCompleteDesc', { count: result.total_count }),
        })
      }
    } catch (error: any) {
      logger.error('Prospecting search failed', error)
      toast({
        variant: "destructive",
        title: t('toast.searchFailed'),
        description: error.message || t('toast.searchFailedDesc'),
      })
    } finally {
      setSearching(false)
    }
  }

  // Import a prospect
  const handleImport = async (resultId: string) => {
    setImportingId(resultId)
    
    try {
      const { data, error } = await api.post<{ success: boolean; prospect_id?: string; message: string }>('/api/v1/prospecting/import', {
        result_id: resultId,
      })
      
      if (error) {
        throw new Error(error.message || String(error))
      }
      
      if (data?.success && data.prospect_id) {
        // Update local state
        setResults(prev => {
          if (!prev) return prev
          return {
            ...prev,
            prospects: prev.prospects.map(p => 
              p.id === resultId 
                ? { ...p, prospect_id: data.prospect_id, imported_at: new Date().toISOString() }
                : p
            )
          }
        })
        
        toast({
          title: t('toast.imported'),
          description: t('toast.importedDesc'),
        })
      } else {
        throw new Error(data?.message || 'Import failed')
      }
    } catch (error: any) {
      logger.error('Import failed', error)
      toast({
        variant: "destructive",
        title: t('toast.importFailed'),
        description: error.message,
      })
    } finally {
      setImportingId(null)
    }
  }

  // Reject a prospect (mark as not relevant)
  const handleReject = async (resultId: string) => {
    setRejectingId(resultId)
    
    try {
      const { data, error } = await api.post<{ success: boolean; message: string }>('/api/v1/prospecting/reject', {
        result_id: resultId,
      })
      
      if (error) {
        throw new Error(error.message || String(error))
      }
      
      if (data?.success) {
        // Remove from local state
        setResults(prev => {
          if (!prev) return prev
          return {
            ...prev,
            prospects: prev.prospects.filter(p => p.id !== resultId),
            total_count: prev.total_count - 1
          }
        })
        
        toast({
          title: t('toast.rejected'),
          description: t('toast.rejectedDesc'),
        })
      } else {
        throw new Error(data?.message || 'Reject failed')
      }
    } catch (error: any) {
      logger.error('Reject failed', error)
      toast({
        variant: "destructive",
        title: t('toast.rejectFailed'),
        description: error.message,
      })
    } finally {
      setRejectingId(null)
    }
  }

  // Load a previous search
  const loadSearch = async (searchId: string) => {
    setLoading(true)
    
    try {
      const { data, error } = await api.get<SearchResult>(`/api/v1/prospecting/searches/${searchId}`)
      if (!error && data) {
        setResults(data)
      }
    } catch (error) {
      logger.error('Failed to load search', error)
    } finally {
      setLoading(false)
    }
  }

  // Delete a search
  const handleDeleteSearch = async () => {
    if (!searchToDelete) return
    
    setDeleting(true)
    
    try {
      const { error } = await api.delete(`/api/v1/prospecting/searches/${searchToDelete.id}`)
      
      if (error) {
        throw new Error(error.message || String(error))
      }
      
      // Remove from history
      setHistory(prev => prev.filter(h => h.id !== searchToDelete.id))
      
      // Clear results if we just deleted the currently viewed search
      if (results?.search_id === searchToDelete.id) {
        setResults(null)
      }
      
      toast({
        title: t('history.deleteSuccess'),
        description: t('history.deleteSuccessDesc'),
      })
    } catch (error: any) {
      logger.error('Failed to delete search', error)
      toast({
        variant: "destructive",
        title: t('history.deleteFailed'),
        description: error.message,
      })
    } finally {
      setDeleting(false)
      setDeleteDialogOpen(false)
      setSearchToDelete(null)
    }
  }

  // Open delete confirmation
  const confirmDeleteSearch = (item: SearchHistoryItem, e: React.MouseEvent) => {
    e.stopPropagation() // Prevent loading the search
    setSearchToDelete(item)
    setDeleteDialogOpen(true)
  }

  // Get fit score color
  const getFitScoreColor = (score: number) => {
    if (score >= 75) return 'text-emerald-600 dark:text-emerald-400'
    if (score >= 50) return 'text-amber-600 dark:text-amber-400'
    return 'text-slate-500 dark:text-slate-400'
  }

  const getFitScoreBg = (score: number) => {
    if (score >= 75) return 'bg-emerald-100 dark:bg-emerald-900/30'
    if (score >= 50) return 'bg-amber-100 dark:bg-amber-900/30'
    return 'bg-slate-100 dark:bg-slate-800'
  }

  if (loading) {
    return (
      <DashboardLayout user={user}>
        <div className="flex items-center justify-center h-full">
          <div className="text-center space-y-4">
            <Icons.spinner className="h-8 w-8 animate-spin text-blue-600 mx-auto" />
            <p className="text-slate-500 dark:text-slate-400">{t('loading')}</p>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  if (!user) {
    router.push('/login')
    return null
  }

  return (
    <DashboardLayout user={user}>
      <div className="p-4 lg:p-6">
        <Toaster />
        
        {/* Page Header */}
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-1">
            <Icons.search className="h-6 w-6 text-violet-600" />
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
              {t('title')}
            </h1>
            <Badge variant="outline" className="ml-2">Beta</Badge>
          </div>
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            {t('subtitle')}
          </p>
        </div>

        {/* Service Check Warnings */}
        {serviceCheck && !serviceCheck.ready && (
          <div className="mb-6 p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
            <div className="flex items-start gap-3">
              <Icons.alertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
              <div>
                <h3 className="font-medium text-amber-900 dark:text-amber-100">
                  {t('setup.title')}
                </h3>
                <ul className="mt-1 text-sm text-amber-800 dark:text-amber-200 space-y-1">
                  {serviceCheck.recommendations.map((rec, i) => (
                    <li key={i}>• {rec}</li>
                  ))}
                </ul>
                <div className="mt-3 flex gap-2">
                  {!serviceCheck.has_sales_profile && (
                    <Button size="sm" variant="outline" onClick={() => router.push('/onboarding')}>
                      {t('setup.createProfile')}
                    </Button>
                  )}
                  {!serviceCheck.has_company_profile && (
                    <Button size="sm" variant="outline" onClick={() => router.push('/onboarding/company')}>
                      {t('setup.addCompany')}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Search Form */}
          <div className="lg:col-span-1">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">{t('form.title')}</CardTitle>
                <CardDescription>{t('form.description')}</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSearch} className="space-y-4">
                  <div>
                    <Label htmlFor="region">{t('form.region')}</Label>
                    <Input
                      id="region"
                      placeholder={t('form.regionPlaceholder')}
                      value={region}
                      onChange={(e) => setRegion(e.target.value)}
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="sector">{t('form.sector')}</Label>
                    <Input
                      id="sector"
                      placeholder={t('form.sectorPlaceholder')}
                      value={sector}
                      onChange={(e) => setSector(e.target.value)}
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="companySize">{t('form.companySize')}</Label>
                    <Input
                      id="companySize"
                      placeholder={t('form.companySizePlaceholder')}
                      value={companySize}
                      onChange={(e) => setCompanySize(e.target.value)}
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="proposition">{t('form.proposition')}</Label>
                    <Textarea
                      id="proposition"
                      placeholder={t('form.propositionPlaceholder')}
                      value={proposition}
                      onChange={(e) => setProposition(e.target.value)}
                      rows={2}
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="targetRole">{t('form.targetRole')}</Label>
                    <Input
                      id="targetRole"
                      placeholder={t('form.targetRolePlaceholder')}
                      value={targetRole}
                      onChange={(e) => setTargetRole(e.target.value)}
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="painPoint">{t('form.painPoint')}</Label>
                    <Textarea
                      id="painPoint"
                      placeholder={t('form.painPointPlaceholder')}
                      value={painPoint}
                      onChange={(e) => setPainPoint(e.target.value)}
                      rows={2}
                    />
                  </div>
                  
                  {/* Reference Customers - Context Enrichment */}
                  <div className="pt-4 border-t">
                    <Label htmlFor="referenceCustomers" className="flex items-center gap-2">
                      {t('form.referenceCustomers')}
                      <Badge variant="outline" className="text-xs">{t('form.optional')}</Badge>
                    </Label>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">
                      {t('form.referenceCustomersHelp')}
                    </p>
                    <Input
                      id="referenceCustomers"
                      placeholder={t('form.referenceCustomersPlaceholder')}
                      value={referenceCustomers}
                      onChange={(e) => setReferenceCustomers(e.target.value)}
                    />
                  </div>
                  
                  {/* Max Results Selector */}
                  <div className="flex items-center justify-between pt-2">
                    <Label htmlFor="maxResults" className="text-sm text-slate-600 dark:text-slate-400">
                      {t('form.maxResults')}
                    </Label>
                    <select
                      id="maxResults"
                      value={maxResults}
                      onChange={(e) => setMaxResults(Number(e.target.value))}
                      className="text-sm border rounded-md px-2 py-1 bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700"
                    >
                      <option value={25}>25</option>
                      <option value={50}>50</option>
                      <option value={100}>100</option>
                    </select>
                  </div>
                  
                  <Button 
                    type="submit" 
                    className="w-full"
                    disabled={searching || loading}
                  >
                    {searching ? (
                      <>
                        <Icons.spinner className="h-4 w-4 animate-spin mr-2" />
                        {t('form.searching')}
                      </>
                    ) : (
                      <>
                        <Icons.sparkles className="h-4 w-4 mr-2" />
                        {t('form.searchButton')}
                      </>
                    )}
                  </Button>
                </form>
                
                {/* Search History */}
                {history.length > 0 && (
                  <div className="mt-6 pt-6 border-t">
                    <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
                      {t('history.title')}
                    </h4>
                    <div className="space-y-2">
                      {history.slice(0, 5).map((item) => (
                        <div
                          key={item.id}
                          className="group flex items-center gap-2"
                        >
                          <button
                            onClick={() => loadSearch(item.id)}
                            className="flex-1 text-left p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-medium text-slate-700 dark:text-slate-300 truncate">
                                {item.sector || item.proposition?.slice(0, 30) || 'Search'}
                              </span>
                              <Badge variant="secondary" className="text-xs flex-shrink-0">
                                {item.results_count} {t('history.results')}
                              </Badge>
                            </div>
                            <span className="text-xs text-slate-500">
                              {new Date(item.created_at).toLocaleDateString()}
                            </span>
                          </button>
                          <button
                            onClick={(e) => confirmDeleteSearch(item, e)}
                            className="p-1.5 rounded-md opacity-0 group-hover:opacity-100 hover:bg-red-100 dark:hover:bg-red-900/30 text-slate-400 hover:text-red-600 transition-all"
                            title={t('history.delete')}
                          >
                            <Icons.trash className="h-4 w-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
          
          {/* Results */}
          <div className="lg:col-span-2">
            {searching ? (
              <Card>
                <CardContent className="py-12">
                  <div className="text-center space-y-4">
                    <Icons.spinner className="h-10 w-10 animate-spin text-violet-600 mx-auto" />
                    <div>
                      <h3 className="font-medium text-slate-900 dark:text-white">
                        {t('searching.title')}
                      </h3>
                      <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        {t('searching.description')}
                      </p>
                    </div>
                    <div className="max-w-xs mx-auto space-y-2">
                      <Progress value={33} className="h-1" />
                      <p className="text-xs text-slate-400">{t('searching.step1')}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ) : results ? (
              <div className="space-y-4">
                {/* Results Header */}
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium text-slate-900 dark:text-white">
                      {t('results.found', { count: results.total_count })}
                    </h3>
                    {results.execution_time_seconds && (
                      <p className="text-xs text-slate-500">
                        {t('results.time', { seconds: results.execution_time_seconds.toFixed(1) })}
                      </p>
                    )}
                  </div>
                  
                  {/* Generated Queries (collapsible) */}
                  {results.generated_queries.length > 0 && (
                    <details className="text-sm">
                      <summary className="cursor-pointer text-violet-600 hover:text-violet-700">
                        {t('results.showQueries')}
                      </summary>
                      <div className="mt-2 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                        <ul className="space-y-1 text-xs text-slate-600 dark:text-slate-400">
                          {results.generated_queries.map((q, i) => (
                            <li key={i}>• {q}</li>
                          ))}
                        </ul>
                      </div>
                    </details>
                  )}
                </div>
                
                {/* Reference Context (if used) */}
                {results.reference_context && (
                  <div className="p-3 bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800 rounded-lg">
                    <div className="flex items-start gap-2">
                      <Icons.sparkles className="h-4 w-4 text-violet-600 mt-0.5" />
                      <div>
                        <p className="text-sm font-medium text-violet-900 dark:text-violet-100">
                          {t('results.referenceContext')}
                        </p>
                        <p className="text-sm text-violet-700 dark:text-violet-300 mt-1">
                          {results.reference_context}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
                
                {/* Prospect Cards */}
                <div className="space-y-3">
                  {results.prospects.map((prospect, index) => (
                    <Card key={prospect.id || index} className="overflow-hidden">
                      <div className="flex">
                        {/* Fit Score Sidebar */}
                        <div className={`w-20 flex-shrink-0 flex flex-col items-center justify-center ${getFitScoreBg(prospect.fit_score)}`}>
                          <span className={`text-2xl font-bold ${getFitScoreColor(prospect.fit_score)}`}>
                            {prospect.fit_score}
                          </span>
                          <span className="text-xs text-slate-500 dark:text-slate-400">
                            {t('results.fitScore')}
                          </span>
                        </div>
                        
                        {/* Content */}
                        <div className="flex-1 p-4">
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <h4 className="font-semibold text-slate-900 dark:text-white">
                                  {prospect.company_name}
                                </h4>
                                {prospect.prospect_id && (
                                  <Badge variant="outline" className="text-xs">
                                    <Icons.check className="h-3 w-3 mr-1" />
                                    {t('results.imported')}
                                  </Badge>
                                )}
                              </div>
                              
                              {/* Meta tags */}
                              <div className="flex items-center gap-2 mt-1 flex-wrap">
                                {prospect.inferred_sector && (
                                  <Badge variant="secondary" className="text-xs">
                                    {prospect.inferred_sector}
                                  </Badge>
                                )}
                                {prospect.inferred_region && (
                                  <Badge variant="secondary" className="text-xs">
                                    {prospect.inferred_region}
                                  </Badge>
                                )}
                                {prospect.inferred_size && (
                                  <Badge variant="secondary" className="text-xs">
                                    {prospect.inferred_size}
                                  </Badge>
                                )}
                              </div>
                              
                              {/* Fit Reason */}
                              {prospect.fit_reason && (
                                <p className="text-sm text-slate-600 dark:text-slate-400 mt-2">
                                  <Icons.lightbulb className="h-4 w-4 inline-block mr-1 text-amber-500" />
                                  {prospect.fit_reason}
                                </p>
                              )}
                              
                              {/* Key Signal */}
                              {prospect.key_signal && (
                                <p className="text-sm text-slate-500 dark:text-slate-500 mt-1">
                                  <Icons.target className="h-4 w-4 inline-block mr-1 text-violet-500" />
                                  {prospect.key_signal}
                                </p>
                              )}
                              
                              {/* Source */}
                              {prospect.source_url && (
                                <a 
                                  href={prospect.source_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs text-blue-600 hover:underline mt-2 inline-flex items-center gap-1"
                                >
                                  <Icons.externalLink className="h-3 w-3" />
                                  {prospect.source_title || t('results.viewSource')}
                                </a>
                              )}
                            </div>
                            
                            {/* Actions */}
                            <div className="flex flex-col gap-2">
                              {prospect.prospect_id ? (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => router.push(`/dashboard/prospects/${prospect.prospect_id}`)}
                                >
                                  <Icons.eye className="h-4 w-4 mr-1" />
                                  {t('results.view')}
                                </Button>
                              ) : (
                                <Button
                                  size="sm"
                                  onClick={() => prospect.id && handleImport(prospect.id)}
                                  disabled={importingId === prospect.id}
                                >
                                  {importingId === prospect.id ? (
                                    <Icons.spinner className="h-4 w-4 animate-spin" />
                                  ) : (
                                    <>
                                      <Icons.plus className="h-4 w-4 mr-1" />
                                      {t('results.import')}
                                    </>
                                  )}
                                </Button>
                              )}
                              
                              {/* Research button */}
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  const params = new URLSearchParams()
                                  params.set('company', prospect.company_name)
                                  if (prospect.website) params.set('website', prospect.website)
                                  router.push(`/dashboard/research?${params.toString()}`)
                                }}
                              >
                                <Icons.search className="h-4 w-4 mr-1" />
                                {t('results.research')}
                              </Button>
                              
                              {/* Reject button - only show if not imported */}
                              {!prospect.prospect_id && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => prospect.id && handleReject(prospect.id)}
                                  disabled={rejectingId === prospect.id}
                                  className="text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
                                  title={t('results.reject')}
                                >
                                  {rejectingId === prospect.id ? (
                                    <Icons.spinner className="h-4 w-4 animate-spin" />
                                  ) : (
                                    <Icons.x className="h-4 w-4" />
                                  )}
                                </Button>
                              )}
                              
                              {prospect.website && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  asChild
                                >
                                  <a href={prospect.website} target="_blank" rel="noopener noreferrer">
                                    <Icons.globe className="h-4 w-4" />
                                  </a>
                                </Button>
                              )}
                            </div>
                          </div>
                          
                          {/* Score breakdown (collapsed by default) */}
                          <details className="mt-3">
                            <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-700">
                              {t('results.scoreBreakdown')}
                            </summary>
                            <div className="grid grid-cols-4 gap-2 mt-2">
                              <div className="text-center p-2 bg-slate-50 dark:bg-slate-800 rounded">
                                <div className="text-sm font-medium">{prospect.proposition_fit}</div>
                                <div className="text-xs text-slate-500">{t('results.propFit')}</div>
                              </div>
                              <div className="text-center p-2 bg-slate-50 dark:bg-slate-800 rounded">
                                <div className="text-sm font-medium">{prospect.seller_fit}</div>
                                <div className="text-xs text-slate-500">{t('results.sellerFit')}</div>
                              </div>
                              <div className="text-center p-2 bg-slate-50 dark:bg-slate-800 rounded">
                                <div className="text-sm font-medium">{prospect.intent_score}</div>
                                <div className="text-xs text-slate-500">{t('results.intent')}</div>
                              </div>
                              <div className="text-center p-2 bg-slate-50 dark:bg-slate-800 rounded">
                                <div className="text-sm font-medium">{prospect.recency_score}</div>
                                <div className="text-xs text-slate-500">{t('results.recency')}</div>
                              </div>
                            </div>
                          </details>
                        </div>
                      </div>
                    </Card>
                  ))}
                  
                  {results.prospects.length === 0 && (
                    <Card>
                      <CardContent className="py-12 text-center">
                        <Icons.searchX className="h-12 w-12 text-slate-300 dark:text-slate-600 mx-auto mb-4" />
                        <h3 className="font-medium text-slate-900 dark:text-white">
                          {t('results.noResults')}
                        </h3>
                        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                          {t('results.noResultsDesc')}
                        </p>
                      </CardContent>
                    </Card>
                  )}
                </div>
              </div>
            ) : (
              /* Empty State */
              <Card>
                <CardContent className="py-12 text-center">
                  <div className="w-16 h-16 rounded-full bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center mx-auto mb-4">
                    <Icons.radar className="h-8 w-8 text-violet-600" />
                  </div>
                  <h3 className="font-semibold text-slate-900 dark:text-white text-lg">
                    {t('empty.title')}
                  </h3>
                  <p className="text-slate-500 dark:text-slate-400 mt-2 max-w-md mx-auto">
                    {t('empty.description')}
                  </p>
                  <div className="mt-6 p-4 bg-slate-50 dark:bg-slate-800 rounded-lg max-w-md mx-auto text-left">
                    <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      {t('empty.howItWorks')}
                    </h4>
                    <ol className="text-sm text-slate-600 dark:text-slate-400 space-y-2">
                      <li className="flex items-start gap-2">
                        <span className="flex-shrink-0 w-5 h-5 rounded-full bg-violet-100 dark:bg-violet-900 text-violet-600 text-xs flex items-center justify-center">1</span>
                        {t('empty.step1')}
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="flex-shrink-0 w-5 h-5 rounded-full bg-violet-100 dark:bg-violet-900 text-violet-600 text-xs flex items-center justify-center">2</span>
                        {t('empty.step2')}
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="flex-shrink-0 w-5 h-5 rounded-full bg-violet-100 dark:bg-violet-900 text-violet-600 text-xs flex items-center justify-center">3</span>
                        {t('empty.step3')}
                      </li>
                    </ol>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('history.deleteConfirmTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('history.deleteConfirmDescription')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>
              {t('history.deleteCancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteSearch}
              disabled={deleting}
              className="bg-red-600 hover:bg-red-700"
            >
              {deleting ? (
                <Icons.spinner className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Icons.trash className="h-4 w-4 mr-2" />
              )}
              {t('history.deleteConfirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </DashboardLayout>
  )
}

