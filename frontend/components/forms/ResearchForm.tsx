'use client'

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { LanguageSelect } from '@/components/language-select'
import { suggestLanguageFromCountry } from '@/lib/language-utils'
import { useSettings } from '@/lib/settings-context'
import { api } from '@/lib/api'
import { logger } from '@/lib/logger'
import { getErrorMessage } from '@/lib/error-utils'
import type { CompanyOption } from '@/types'

interface ResearchFormProps {
  // Pre-filled values (optional, for Hub context)
  initialCompanyName?: string
  initialCountry?: string
  
  // Callbacks
  onSuccess?: () => void
  onCancel?: () => void
  
  // Mode
  isSheet?: boolean  // Different styling for sheet vs page
}

export function ResearchForm({
  initialCompanyName = '',
  initialCountry = '',
  onSuccess,
  onCancel,
  isSheet = false
}: ResearchFormProps) {
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const t = useTranslations('research')
  const tLang = useTranslations('language')
  const { settings, loaded: settingsLoaded } = useSettings()
  
  // Form state
  const [companyName, setCompanyName] = useState(initialCompanyName)
  const [linkedinUrl, setLinkedinUrl] = useState('')
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [country, setCountry] = useState(initialCountry)
  const [city, setCity] = useState('')
  const [outputLanguage, setOutputLanguage] = useState('en')
  const [languageFromSettings, setLanguageFromSettings] = useState(false)
  
  // Company search state
  const [isSearching, setIsSearching] = useState(false)
  const [companyOptions, setCompanyOptions] = useState<CompanyOption[]>([])
  const [showOptions, setShowOptions] = useState(false)
  const [selectedCompany, setSelectedCompany] = useState<CompanyOption | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [researching, setResearching] = useState(false)
  
  // Set language from settings on load (only once)
  useEffect(() => {
    if (settingsLoaded && !languageFromSettings) {
      setOutputLanguage(settings.output_language)
      setLanguageFromSettings(true)
    }
  }, [settingsLoaded, settings.output_language, languageFromSettings])
  
  // Auto-suggest language when country changes (only if settings not loaded yet)
  useEffect(() => {
    if (country && country.length >= 2 && !languageFromSettings) {
      const suggested = suggestLanguageFromCountry(country)
      setOutputLanguage(suggested)
    }
  }, [country, languageFromSettings])
  
  // Manual search function - CRITICAL FUNCTIONALITY
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
        
        // Auto-select if only one high-confidence match
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
  
  // Select company from search results - auto-fills website, LinkedIn, location
  const selectCompanyOption = (option: CompanyOption) => {
    setSelectedCompany(option)
    setCompanyName(option.company_name)
    if (option.website) setWebsiteUrl(option.website)
    if (option.linkedin_url) setLinkedinUrl(option.linkedin_url)
    
    // Extract city from location
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
  
  // Handle company name change - reset selection if name changes
  const handleCompanyNameChange = (value: string) => {
    setCompanyName(value)
    if (selectedCompany && value !== selectedCompany.company_name) {
      setSelectedCompany(null)
      setWebsiteUrl('')
      setLinkedinUrl('')
      setCompanyOptions([])
    }
  }
  
  // Start research
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
      setOutputLanguage(settings.output_language)
      setSelectedCompany(null)
      setShowAdvanced(false)
      
      toast({
        title: t('toast.started'),
        description: t('toast.startedDesc'),
      })
      
      // Call success callback
      onSuccess?.()
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

  return (
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
        
        {/* Company Options - search results */}
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

        {/* Action buttons */}
        <div className={`flex gap-2 ${isSheet ? 'pt-2' : ''}`}>
          {isSheet && onCancel && (
            <Button 
              type="button" 
              variant="outline" 
              onClick={onCancel}
              disabled={researching}
              className="flex-1"
            >
              {t('form.cancel')}
            </Button>
          )}
          <Button 
            type="submit" 
            disabled={researching || !selectedCompany}
            className={`${isSheet ? 'flex-1' : 'w-full'} ${
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
      </div>
    </form>
  )
}

