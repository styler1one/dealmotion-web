'use client'

import { useState, useEffect, useCallback } from 'react'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { Toaster } from '@/components/ui/toaster'
import { DashboardLayout } from '@/components/layout'
import { LanguageSelect } from '@/components/language-select'
import { suggestLanguageFromCountry } from '@/lib/language-utils'
import { formatDate } from '@/lib/date-utils'
import { useTranslations } from 'next-intl'
import { useSettings } from '@/lib/settings-context'
import { api } from '@/lib/api'
import { useConfirmDialog } from '@/components/confirm-dialog'
import { logger } from '@/lib/logger'
import { getErrorMessage } from '@/lib/error-utils'
import type { User } from '@supabase/supabase-js'
import type { ResearchBrief, CompanyOption } from '@/types'

export default function ResearchPage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const { confirm } = useConfirmDialog()
  const t = useTranslations('research')
  const tLang = useTranslations('language')
  const { settings, loaded: settingsLoaded } = useSettings()
  
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [researching, setResearching] = useState(false)
  const [briefs, setBriefs] = useState<ResearchBrief[]>([])
  
  // Form state
  const [companyName, setCompanyName] = useState('')
  const [linkedinUrl, setLinkedinUrl] = useState('')
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [outputLanguage, setOutputLanguage] = useState('en') // Will be updated from settings
  const [languageFromSettings, setLanguageFromSettings] = useState(false) // Track if set from settings
  
  // Set language from settings on load (only once)
  useEffect(() => {
    if (settingsLoaded && !languageFromSettings) {
      setOutputLanguage(settings.output_language)
      setLanguageFromSettings(true)
    }
  }, [settingsLoaded, settings.output_language, languageFromSettings])
  
  // Company search state
  const [isSearching, setIsSearching] = useState(false)
  const [companyOptions, setCompanyOptions] = useState<CompanyOption[]>([])
  const [showOptions, setShowOptions] = useState(false)
  const [selectedCompany, setSelectedCompany] = useState<CompanyOption | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Get user for display purposes (non-blocking)
  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      setUser(user)
    })
  }, [supabase])

  // Auto-suggest language when country changes (only if settings not loaded yet)
  // If user has settings, we respect those. Country suggestion is just a fallback.
  useEffect(() => {
    // Only auto-suggest if settings haven't been loaded yet
    if (country && country.length >= 2 && !languageFromSettings) {
      const suggested = suggestLanguageFromCountry(country)
      setOutputLanguage(suggested)
    }
  }, [country, languageFromSettings])
  
  // Manual search function
  const searchCompanies = async () => {
    if (!companyName || companyName.length < 3) {
      toast({
        title: t('validation.companyNameTooShort'),
        description: t('validation.companyNameTooShortDesc'),
        variant: "destructive"
      })
      return
    }
    
    if (!country || country.length < 2) {
      toast({
        title: t('validation.countryRequired'),
        description: t('validation.countryRequiredDesc'),
        variant: "destructive"
      })
      return
    }
    
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) return
      
      setIsSearching(true)
      setCompanyOptions([])
      setShowOptions(false)
      
      const { data, error } = await api.post<{ options: CompanyOption[] }>(
        '/api/v1/research/search-company',
        { company_name: companyName, country }
      )
      
      if (!error && data?.options && data.options.length > 0) {
        setCompanyOptions(data.options)
        
        if (data.options.length === 1 && data.options[0].confidence >= 90) {
          selectCompanyOption(data.options[0])
        } else {
          setShowOptions(true)
        }
      } else {
        setCompanyOptions([])
        toast({
          title: t('search.noResults'),
          description: t('search.noResultsDesc', { company: companyName, country }),
          variant: "destructive"
        })
      }
    } catch (error) {
      logger.error('Company search failed', error)
      toast({
        title: t('search.failed'),
        description: t('search.failedDesc'),
        variant: "destructive"
      })
    } finally {
      setIsSearching(false)
    }
  }
  
  const selectCompanyOption = (option: CompanyOption) => {
    setSelectedCompany(option)
    setCompanyName(option.company_name)
    if (option.website) setWebsiteUrl(option.website)
    if (option.linkedin_url) setLinkedinUrl(option.linkedin_url)
    
    if (option.location) {
      const locationParts = option.location.split(',')
      if (locationParts.length > 0) {
        const extractedCity = locationParts[0].trim()
        if (extractedCity.toLowerCase() !== country.toLowerCase()) {
          setCity(extractedCity)
        }
      }
    }
    
    setShowOptions(false)
    
    toast({
      title: t('search.selected'),
      description: t('search.selectedDesc', { company: option.company_name }),
    })
  }
  
  const handleCompanyNameChange = (value: string) => {
    setCompanyName(value)
    if (selectedCompany && value !== selectedCompany.company_name) {
      setSelectedCompany(null)
      setWebsiteUrl('')
      setLinkedinUrl('')
      setCompanyOptions([])
    }
  }

  const fetchBriefs = useCallback(async () => {
    try {
      // Note: api client handles authentication automatically
      const { data, error } = await api.get<{ briefs: ResearchBrief[] }>('/api/v1/research/briefs')

      if (!error && data) {
        setBriefs(data.briefs || [])
      }
    } catch (error) {
      logger.error('Failed to fetch briefs', error)
    }
  }, [])

  // Fetch briefs on mount
  useEffect(() => {
    fetchBriefs().finally(() => {
      setLoading(false)
    })
  }, [fetchBriefs])

  const handleStartResearch = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!companyName.trim()) {
      toast({
        variant: "destructive",
        title: t('validation.companyNameRequired'),
        description: t('validation.companyNameRequiredDesc'),
      })
      return
    }

    setResearching(true)
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        throw new Error('Not authenticated')
      }

      const { error } = await api.post('/api/v1/research/start', {
        company_name: companyName,
        company_linkedin_url: linkedinUrl || null,
        company_website_url: websiteUrl || null,
        country: country || null,
        city: city || null,
        language: outputLanguage
      })

      if (error) {
        throw new Error(error.message || 'Research failed')
      }

      // Clear form
      setCompanyName('')
      setLinkedinUrl('')
      setWebsiteUrl('')
      setCountry('')
      setCity('')
      setOutputLanguage(settings.output_language) // Reset to settings default, not hardcoded 'nl'
      setSelectedCompany(null)
      setShowAdvanced(false)
      
      await fetchBriefs()
      
      toast({
        title: t('toast.started'),
        description: t('toast.startedDesc'),
      })
      
      setTimeout(() => fetchBriefs(), 3000)
    } catch (error) {
      logger.error('Research failed', error)
      toast({
        variant: "destructive",
        title: t('toast.failed'),
        description: getErrorMessage(error) || t('toast.failedDesc'),
      })
    } finally {
      setResearching(false)
    }
  }

  const handleDeleteBrief = async (briefId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    
    const confirmed = await confirm({
      title: t('confirm.deleteTitle'),
      description: t('confirm.deleteDescription'),
      confirmLabel: t('confirm.deleteButton'),
      cancelLabel: t('confirm.cancelButton'),
      variant: 'danger'
    })
    
    if (!confirmed) return
    
    try {
      // Note: api client handles authentication automatically
      const { error } = await api.delete(`/api/v1/research/${briefId}`)

      if (!error) {
        await fetchBriefs()
        toast({
          title: t('toast.deleted'),
          description: t('toast.deletedDesc'),
        })
      } else {
        throw new Error('Delete failed')
      }
    } catch (error) {
      logger.error('Delete failed', error)
      toast({
        variant: "destructive",
        title: t('toast.deleteFailed'),
        description: t('toast.deleteFailedDesc'),
      })
    }
  }

  // Auto-refresh for processing briefs
  useEffect(() => {
    const hasProcessingBriefs = briefs.some(b => 
      b.status === 'pending' || b.status === 'researching'
    )

    if (hasProcessingBriefs) {
      const interval = setInterval(() => {
        fetchBriefs()
      }, 5000)

      return () => clearInterval(interval)
    }
  }, [briefs, fetchBriefs])

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

  const completedBriefs = briefs.filter(b => b.status === 'completed').length
  const processingBriefs = briefs.filter(b => b.status === 'researching' || b.status === 'pending').length

  return (
    <DashboardLayout user={user}>
      <div className="p-4 lg:p-6">
        {/* Page Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">
            {t('title')}
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            {t('subtitle')}
          </p>
        </div>

        {/* Two Column Layout */}
        <div className="flex gap-6">
          
          {/* Left Column - Research History */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                <Icons.fileText className="h-5 w-5 text-slate-400" />
                {t('history.title')}
                <span className="text-sm font-normal text-slate-400">({briefs.length})</span>
              </h2>
              <Button variant="ghost" size="sm" onClick={fetchBriefs}>
                <Icons.refresh className="h-4 w-4" />
              </Button>
            </div>

            {briefs.length === 0 ? (
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-12 text-center">
                <Icons.search className="h-16 w-16 text-slate-200 dark:text-slate-700 mx-auto mb-4" />
                <h3 className="font-semibold text-slate-700 dark:text-slate-200 mb-2">{t('history.empty')}</h3>
                <p className="text-slate-500 dark:text-slate-400 text-sm mb-4">
                  {t('history.emptyDesc')}
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {briefs.map((brief) => (
                  <div
                    key={brief.id}
                    className={`bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 hover:shadow-md dark:hover:shadow-slate-800/50 transition-all cursor-pointer group ${
                      brief.status === 'completed' ? 'hover:border-blue-300 dark:hover:border-blue-700' : ''
                    }`}
                    onClick={() => brief.status === 'completed' && router.push(`/dashboard/research/${brief.id}`)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-semibold text-slate-900 dark:text-white truncate">{brief.company_name}</h4>
                          
                          {brief.status === 'completed' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 dark:bg-green-900/50 text-green-700 dark:text-green-400 flex-shrink-0">
                              <Icons.check className="h-3 w-3" />
                              {t('stats.completed')}
                            </span>
                          )}
                          {brief.status === 'researching' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400 flex-shrink-0">
                              <Icons.spinner className="h-3 w-3 animate-spin" />
                              {t('stats.researching')}
                            </span>
                          )}
                          {brief.status === 'pending' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-50 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-400 flex-shrink-0">
                              <Icons.clock className="h-3 w-3" />
                              {t('stats.researching')}
                            </span>
                          )}
                          {brief.status === 'failed' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 dark:bg-red-900/50 text-red-700 dark:text-red-400 flex-shrink-0">
                              <Icons.alertCircle className="h-3 w-3" />
                              {t('stats.failed')}
                            </span>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                          {(brief.city || brief.country) && (
                            <span>📍 {[brief.city, brief.country].filter(Boolean).join(', ')}</span>
                          )}
                          <span>{formatDate(brief.created_at, settings.output_language)}</span>
                        </div>
                        
                        {brief.error_message && (
                          <p className="text-xs text-red-600 dark:text-red-400 mt-2 truncate">
                            {brief.error_message}
                          </p>
                        )}
                      </div>
                      
                      <div className="flex items-center gap-1 ml-4">
                        {brief.status === 'completed' && (
                          <>
                            <Button
                              variant="default"
                              size="sm"
                              className="h-8 text-xs bg-blue-600 hover:bg-blue-700"
                              onClick={(e) => {
                                e.stopPropagation()
                                router.push(`/dashboard/research/${brief.id}`)
                              }}
                            >
                              <Icons.arrowRight className="h-3 w-3 mr-1" />
                              {t('brief.view')}
                            </Button>
                          </>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-slate-400 hover:text-red-600 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => handleDeleteBrief(brief.id, e)}
                        >
                          <Icons.trash className="h-4 w-4" />
                        </Button>
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
                  <Icons.barChart className="h-4 w-4 text-slate-400" />
                  {t('stats.title')}
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-green-50 dark:bg-green-900/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-green-600 dark:text-green-400">{completedBriefs}</p>
                    <p className="text-xs text-green-700 dark:text-green-300">{t('stats.completed')}</p>
                  </div>
                  <div className="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{processingBriefs}</p>
                    <p className="text-xs text-blue-700 dark:text-blue-300">{t('stats.researching')}</p>
                  </div>
                </div>
              </div>

              {/* New Research Form */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                  <Icons.search className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                  {t('form.title')}
                </h3>
                
                <form onSubmit={handleStartResearch} className="space-y-4">
                  
                  {/* ===== STEP 1: Find Company ===== */}
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="flex items-center justify-center w-5 h-5 rounded-full bg-blue-600 text-white text-xs font-bold">1</span>
                      <span className="text-sm font-medium text-slate-900 dark:text-white">{t('form.step1Title')}</span>
                    </div>
                    
                    <div>
                      <Label htmlFor="companyName" className="text-xs text-slate-700 dark:text-slate-300">{t('form.companyName')} *</Label>
                      <Input
                        id="companyName"
                        value={companyName}
                        onChange={(e) => handleCompanyNameChange(e.target.value)}
                        placeholder={t('form.companyNamePlaceholder')}
                        className={`mt-1 h-9 text-sm ${selectedCompany ? 'border-green-300 dark:border-green-700 bg-green-50 dark:bg-green-900/30' : ''}`}
                        required
                      />
                    </div>

                    <div>
                      <Label htmlFor="country" className="text-xs text-slate-700 dark:text-slate-300">{t('form.country')} *</Label>
                      <Input
                        id="country"
                        value={country}
                        onChange={(e) => { setCountry(e.target.value); setSelectedCompany(null) }}
                        placeholder={t('form.countryPlaceholder')}
                        className="mt-1 h-9 text-sm"
                        required
                      />
                    </div>
                    
                    {/* Search button - prominent blue */}
                    {!selectedCompany && (
                      <Button
                        type="button"
                        onClick={searchCompanies}
                        disabled={isSearching || companyName.length < 3 || country.length < 2}
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                      >
                        {isSearching ? (
                          <>
                            <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
                            {t('form.searching')}
                          </>
                        ) : (
                          <>
                            <Icons.search className="mr-2 h-4 w-4" />
                            {t('form.searchCompany')}
                          </>
                        )}
                      </Button>
                    )}
                    
                    {/* Company Options */}
                    {showOptions && companyOptions.length > 0 && (
                      <div className="border border-blue-200 dark:border-blue-800 rounded-lg p-2 bg-blue-50 dark:bg-blue-900/30 space-y-2 max-h-48 overflow-y-auto">
                        <p className="text-xs font-medium text-blue-800 dark:text-blue-200">{t('form.selectCompany')}</p>
                        {companyOptions.map((option, index) => (
                          <button
                            key={index}
                            type="button"
                            onClick={() => selectCompanyOption(option)}
                            className="w-full text-left p-2 bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 text-xs hover:border-blue-500 dark:hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
                          >
                            <p className="font-medium text-slate-900 dark:text-white truncate">{option.company_name}</p>
                            {option.location && (
                              <p className="text-slate-500 dark:text-slate-400 truncate">📍 {option.location}</p>
                            )}
                          </button>
                        ))}
                      </div>
                    )}
                    
                    {/* Selected company indicator */}
                    {selectedCompany && (
                      <div className="p-3 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 rounded-lg">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Icons.check className="h-4 w-4 text-green-600 dark:text-green-400" />
                            <p className="text-sm font-medium text-green-800 dark:text-green-200 truncate">{selectedCompany.company_name}</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => { setSelectedCompany(null); setWebsiteUrl(''); setLinkedinUrl('') }}
                            className="text-xs text-green-700 dark:text-green-300 hover:text-green-900 dark:hover:text-green-100 p-1"
                          >
                            <Icons.x className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* ===== Separator ===== */}
                  <div className="relative">
                    <div className="absolute inset-0 flex items-center">
                      <div className="w-full border-t border-slate-200 dark:border-slate-700"></div>
                    </div>
                  </div>

                  {/* ===== STEP 2: Start Research ===== */}
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <span className={`flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold ${
                        selectedCompany 
                          ? 'bg-green-600 text-white' 
                          : 'bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-400'
                      }`}>2</span>
                      <span className={`text-sm font-medium ${
                        selectedCompany 
                          ? 'text-slate-900 dark:text-white' 
                          : 'text-slate-400 dark:text-slate-500'
                      }`}>{t('form.step2Title')}</span>
                    </div>
                    
                    {/* Hint when no company selected */}
                    {!selectedCompany && (
                      <div className="flex items-center gap-2 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-dashed border-slate-300 dark:border-slate-600">
                        <Icons.info className="h-4 w-4 text-slate-400 flex-shrink-0" />
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          {t('form.step2Hint')}
                        </p>
                      </div>
                    )}

                    {/* Advanced options toggle - only show when company selected */}
                    {selectedCompany && (
                      <button
                        type="button"
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 flex items-center gap-1"
                      >
                        {showAdvanced ? <Icons.chevronDown className="h-3 w-3" /> : <Icons.chevronRight className="h-3 w-3" />}
                        {t('form.extraOptions')}
                      </button>
                    )}

                    {showAdvanced && selectedCompany && (
                      <div className="space-y-3 pt-2 border-t border-slate-200 dark:border-slate-700">
                        <div>
                          <Label htmlFor="websiteUrl" className="text-xs text-slate-700 dark:text-slate-300">{t('form.website')}</Label>
                          <Input
                            id="websiteUrl"
                            value={websiteUrl}
                            onChange={(e) => setWebsiteUrl(e.target.value)}
                            placeholder={t('form.websitePlaceholder')}
                            className="mt-1 h-9 text-sm"
                          />
                        </div>
                        <div>
                          <Label htmlFor="linkedinUrl" className="text-xs text-slate-700 dark:text-slate-300">{t('form.linkedin')}</Label>
                          <Input
                            id="linkedinUrl"
                            value={linkedinUrl}
                            onChange={(e) => setLinkedinUrl(e.target.value)}
                            placeholder={t('form.linkedinPlaceholder')}
                            className="mt-1 h-9 text-sm"
                          />
                        </div>
                        <div>
                          <Label htmlFor="city" className="text-xs text-slate-700 dark:text-slate-300">{t('form.city')}</Label>
                          <Input
                            id="city"
                            value={city}
                            onChange={(e) => setCity(e.target.value)}
                            placeholder={t('form.cityPlaceholder')}
                            className="mt-1 h-9 text-sm"
                          />
                        </div>
                        
                        {/* Output Language Selector */}
                        <LanguageSelect
                          value={outputLanguage}
                          onChange={setOutputLanguage}
                          label={tLang('outputLanguage')}
                          description={tLang('outputLanguageDesc')}
                          showSuggestion={!!country}
                          suggestionSource={country}
                        />
                      </div>
                    )}

                    <Button 
                      type="submit" 
                      disabled={researching || !selectedCompany}
                      className={`w-full ${
                        selectedCompany 
                          ? 'bg-green-600 hover:bg-green-700' 
                          : 'bg-slate-300 dark:bg-slate-700 cursor-not-allowed'
                      }`}
                    >
                      {researching ? (
                        <>
                          <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
                          {t('form.researching')}
                        </>
                      ) : (
                        <>
                          <Icons.zap className="mr-2 h-4 w-4" />
                          {t('form.startResearch')}
                        </>
                      )}
                    </Button>
                  </div>
                </form>
              </div>

              {/* How it works Panel */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-gradient-to-br from-indigo-50 to-blue-50 dark:from-indigo-950 dark:to-blue-950 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <Icons.sparkles className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                  {t('howItWorks.title')}
                </h3>
                <div className="space-y-3">
                  <div className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center flex-shrink-0 font-bold">1</div>
                    <div>
                      <p className="text-sm font-medium text-slate-800 dark:text-slate-100">{t('howItWorks.step1')}</p>
                      <p className="text-xs text-slate-600 dark:text-slate-400">{t('howItWorks.step1Desc')}</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center flex-shrink-0 font-bold">2</div>
                    <div>
                      <p className="text-sm font-medium text-slate-800 dark:text-slate-100">{t('howItWorks.step2')}</p>
                      <p className="text-xs text-slate-600 dark:text-slate-400">{t('howItWorks.step2Desc')}</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-green-600 text-white text-xs flex items-center justify-center flex-shrink-0 font-bold">3</div>
                    <div>
                      <p className="text-sm font-medium text-slate-800 dark:text-slate-100">{t('howItWorks.step3')}</p>
                      <p className="text-xs text-slate-600 dark:text-slate-400">{t('howItWorks.step3Desc')}</p>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>

        {/* Mobile: Floating New Research Button */}
        <div className="lg:hidden fixed bottom-6 right-6">
          <Button 
            className="rounded-full h-14 w-14 shadow-lg bg-blue-600 hover:bg-blue-700"
            onClick={() => {
              // Scroll to top where form is visible on mobile
              window.scrollTo({ top: 0, behavior: 'smooth' })
            }}
          >
            <Icons.plus className="h-6 w-6" />
          </Button>
        </div>

        <Toaster />
      </div>
    </DashboardLayout>
  )
}
