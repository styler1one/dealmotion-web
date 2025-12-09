'use client'

import { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { Toaster } from '@/components/ui/toaster'
import { DashboardLayout } from '@/components/layout'
import { ProspectAutocomplete } from '@/components/prospect-autocomplete'
import { LanguageSelect } from '@/components/language-select'
import { useTranslations } from 'next-intl'
import { useSettings } from '@/lib/settings-context'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/date-utils'
import { useConfirmDialog } from '@/components/confirm-dialog'
import type { User } from '@supabase/supabase-js'
import type { ProspectContact, Deal } from '@/types'

interface MeetingPrep {
  id: string
  prospect_company_name: string
  meeting_type: string
  status: string
  custom_notes?: string
  brief_content?: string
  talking_points?: { topic: string; points: string[] }[]
  questions?: string[]
  strategy?: string
  pdf_url?: string
  created_at: string
  completed_at?: string
  error_message?: string
}

export default function PreparationPage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const { confirm } = useConfirmDialog()
  const t = useTranslations('preparation')
  const tLang = useTranslations('language')
  const { settings, loaded: settingsLoaded } = useSettings()

  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(false)
  const [preps, setPreps] = useState<MeetingPrep[]>([])
  const [initialLoading, setInitialLoading] = useState(true)

  // Form state
  const [companyName, setCompanyName] = useState('')
  const [meetingType, setMeetingType] = useState('discovery')
  const [customNotes, setCustomNotes] = useState('')
  const [outputLanguage, setOutputLanguage] = useState('en')
  const [showAdvanced, setShowAdvanced] = useState(false)
  
  // Set language from settings on load
  useEffect(() => {
    if (settingsLoaded) {
      setOutputLanguage(settings.output_language)
    }
  }, [settingsLoaded, settings.output_language])
  
  // Contact persons state
  const [availableContacts, setAvailableContacts] = useState<ProspectContact[]>([])
  const [selectedContactIds, setSelectedContactIds] = useState<string[]>([])
  const [contactsLoading, setContactsLoading] = useState(false)
  
  // Deal linking state
  const [availableDeals, setAvailableDeals] = useState<Deal[]>([])
  const [selectedDealId, setSelectedDealId] = useState<string>('')
  const [dealsLoading, setDealsLoading] = useState(false)
  
  // Calendar meeting linking state (SPEC-038)
  const [calendarMeetingId, setCalendarMeetingId] = useState<string | null>(null)

  // Get user for display (non-blocking) and load preps in parallel
  useEffect(() => {
    // Load user and preps in parallel
    Promise.all([
      supabase.auth.getUser().then(({ data: { user } }) => setUser(user)),
      loadPreps()
    ])

    // Check for pre-selected company from Research or Meetings page
    const prepareFor = sessionStorage.getItem('prepareForCompany')
    if (prepareFor) {
      setCompanyName(prepareFor)
      sessionStorage.removeItem('prepareForCompany')
    }
    
    // Check for calendar meeting link from Meetings page (SPEC-038)
    const meetingId = sessionStorage.getItem('prepareForMeetingId')
    if (meetingId) {
      setCalendarMeetingId(meetingId)
      sessionStorage.removeItem('prepareForMeetingId')
    }
    
    // Clean up prospect ID as well
    sessionStorage.removeItem('prepareForProspectId')
  }, [])
  
  // Poll for status updates
  useEffect(() => {
    const hasProcessingPreps = preps.some(p => p.status === 'pending' || p.status === 'generating')
    
    if (hasProcessingPreps) {
      const interval = setInterval(() => {
        loadPreps()
      }, 5000)
      return () => clearInterval(interval)
    }
  }, [preps])

  const loadPreps = async () => {
    try {
      // Note: api client handles authentication automatically
      const { data, error } = await api.get<{ preps: MeetingPrep[] }>('/api/v1/prep/briefs')

      if (!error && data) {
        setPreps(data.preps || [])
      }
    } catch (error) {
      console.error('Failed to load preps:', error)
    } finally {
      setInitialLoading(false)
    }
  }

  // Load contacts AND deals together when company name changes (single prospect search)
  const loadContactsAndDealsForProspect = async (prospectName: string) => {
    if (!prospectName || prospectName.length < 2) {
      setAvailableContacts([])
      setSelectedContactIds([])
      setAvailableDeals([])
      setSelectedDealId('')
      return
    }

    setContactsLoading(true)
    setDealsLoading(true)
    
    try {
      // Single prospect search for both contacts and deals
      const { data: prospects, error: prospectError } = await api.get<Array<{ id: string; company_name: string }>>(
        `/api/v1/prospects/search?q=${encodeURIComponent(prospectName)}`
      )

      if (prospectError || !prospects) {
        setAvailableContacts([])
        setAvailableDeals([])
        return
      }

      const exactMatch = prospects.find(
        (p) => p.company_name.toLowerCase() === prospectName.toLowerCase()
      )

      if (exactMatch) {
        // Fetch contacts and deals in PARALLEL
        const [contactsResult, dealsResult] = await Promise.all([
          api.get<{ contacts: ProspectContact[] }>(`/api/v1/prospects/${exactMatch.id}/contacts`),
          supabase
            .from('deals')
            .select('*')
            .eq('prospect_id', exactMatch.id)
            .eq('is_active', true)
            .order('created_at', { ascending: false })
        ])

        // Set contacts
        if (!contactsResult.error && contactsResult.data) {
          setAvailableContacts(contactsResult.data.contacts || [])
        } else {
          setAvailableContacts([])
        }

        // Set deals
        if (!dealsResult.error && dealsResult.data) {
          setAvailableDeals(dealsResult.data || [])
        } else {
          setAvailableDeals([])
        }
      } else {
        setAvailableContacts([])
        setAvailableDeals([])
      }
    } catch (error) {
      console.error('Failed to load contacts/deals:', error)
      setAvailableContacts([])
      setAvailableDeals([])
    } finally {
      setContactsLoading(false)
      setDealsLoading(false)
    }
  }

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      loadContactsAndDealsForProspect(companyName)
    }, 500)

    return () => clearTimeout(timeoutId)
  }, [companyName])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        toast({ title: t('toast.failed'), description: t('toast.failedDesc'), variant: 'destructive' })
        return
      }

      const { error } = await api.post('/api/v1/prep/start', {
        prospect_company_name: companyName,
        meeting_type: meetingType,
        custom_notes: customNotes || null,
        contact_ids: selectedContactIds.length > 0 ? selectedContactIds : null,
        deal_id: selectedDealId || null,
        calendar_meeting_id: calendarMeetingId || null,
        language: outputLanguage
      })

      if (!error) {
        toast({ title: t('toast.started'), description: t('toast.startedDesc') })
        setCompanyName('')
        setCustomNotes('')
        setOutputLanguage(settings.output_language) // Reset to settings default
        setSelectedContactIds([])
        setAvailableContacts([])
        setSelectedDealId('')
        setAvailableDeals([])
        setCalendarMeetingId(null)
        setShowAdvanced(false)
        loadPreps()
      } else {
        toast({ title: t('toast.failed'), description: error.message || t('toast.failedDesc'), variant: 'destructive' })
      }
    } catch (error) {
      toast({ title: t('toast.failed'), description: t('toast.failedDesc'), variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }

  const viewPrep = (prepId: string) => {
    router.push(`/dashboard/preparation/${prepId}`)
  }

  const deletePrep = async (prepId: string, e: React.MouseEvent) => {
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
      const { error } = await api.delete(`/api/v1/prep/${prepId}`)

      if (!error) {
        toast({ title: t('toast.deleted') })
        loadPreps()
      }
    } catch (error) {
      toast({ title: t('toast.deleteFailed'), description: t('toast.deleteFailedDesc'), variant: 'destructive' })
    }
  }

  const getMeetingTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      discovery: '🔍 Discovery Call',
      demo: '🖥️ Product Demo',
      closing: '🤝 Closing Call',
      follow_up: '📞 Follow-up',
      other: '📋 Anders'
    }
    return labels[type] || type
  }

  const completedPreps = preps.filter(p => p.status === 'completed').length
  const processingPreps = preps.filter(p => p.status === 'pending' || p.status === 'generating').length

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
          
          {/* Left Column - Preparations History */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                <Icons.fileText className="h-5 w-5 text-slate-400" />
                {t('history.title')}
                <span className="text-sm font-normal text-slate-400">({preps.length})</span>
              </h2>
              <Button variant="ghost" size="sm" onClick={loadPreps}>
                <Icons.refresh className="h-4 w-4" />
              </Button>
            </div>

            {preps.length === 0 ? (
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-12 text-center">
                <Icons.fileText className="h-16 w-16 text-slate-200 dark:text-slate-700 mx-auto mb-4" />
                <h3 className="font-semibold text-slate-700 dark:text-slate-200 mb-2">{t('history.empty')}</h3>
                <p className="text-slate-500 dark:text-slate-400 text-sm mb-4">
                  {t('history.emptyDesc')}
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {preps.map((prep) => (
                  <div
                    key={prep.id}
                    className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 hover:shadow-md dark:hover:shadow-slate-800/50 transition-all cursor-pointer group hover:border-green-300 dark:hover:border-green-700"
                    onClick={() => prep.status === 'completed' && viewPrep(prep.id)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-semibold text-slate-900 dark:text-white truncate">{prep.prospect_company_name}</h4>
                          
                          {prep.status === 'completed' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 dark:bg-green-900/50 text-green-700 dark:text-green-400 flex-shrink-0">
                              <Icons.check className="h-3 w-3" />
                              {t('stats.completed')}
                            </span>
                          )}
                          {(prep.status === 'generating' || prep.status === 'pending') && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400 flex-shrink-0">
                              <Icons.spinner className="h-3 w-3 animate-spin" />
                              {t('stats.generating')}
                            </span>
                          )}
                          {prep.status === 'failed' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 dark:bg-red-900/50 text-red-700 dark:text-red-400 flex-shrink-0">
                              <Icons.alertCircle className="h-3 w-3" />
                              {t('toast.failed')}
                            </span>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                          <span>{getMeetingTypeLabel(prep.meeting_type)}</span>
                          <span>•</span>
                          <span>{formatDate(prep.created_at, settings.output_language)}</span>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-1 ml-4">
                        {prep.status === 'completed' && (
                          <>
                            <Button
                              variant="default"
                              size="sm"
                              className="h-8 text-xs bg-green-600 hover:bg-green-700 opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => {
                                e.stopPropagation()
                                viewPrep(prep.id)
                              }}
                            >
                              <Icons.eye className="h-3 w-3 mr-1" />
                              {t('brief.view')}
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-8 text-xs border-orange-300 dark:border-orange-700 text-orange-600 dark:text-orange-400 hover:bg-orange-50 dark:hover:bg-orange-900/30 opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => {
                                e.stopPropagation()
                                sessionStorage.setItem('followupForCompany', prep.prospect_company_name)
                                router.push('/dashboard/followup')
                              }}
                            >
                              <Icons.mic className="h-3 w-3 mr-1" />
                              {t('history.toFollowup')}
                            </Button>
                          </>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-slate-400 hover:text-red-600 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => deletePrep(prep.id, e)}
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
                    <p className="text-2xl font-bold text-green-600 dark:text-green-400">{completedPreps}</p>
                    <p className="text-xs text-green-700 dark:text-green-300">{t('stats.completed')}</p>
                  </div>
                  <div className="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{processingPreps}</p>
                    <p className="text-xs text-blue-700 dark:text-blue-300">{t('stats.generating')}</p>
                  </div>
                </div>
              </div>

              {/* New Preparation Form */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <Icons.fileText className="h-4 w-4 text-green-600 dark:text-green-400" />
                  {t('form.title')}
                </h3>
                
                <form onSubmit={handleSubmit} className="space-y-3">
                  <div>
                    <Label htmlFor="company" className="text-xs text-slate-700 dark:text-slate-300">{t('form.selectProspect')} *</Label>
                    <ProspectAutocomplete
                      value={companyName}
                      onChange={setCompanyName}
                      placeholder={t('form.selectProspectPlaceholder')}
                    />
                  </div>

                  <div>
                    <Label className="text-xs text-slate-700 dark:text-slate-300">Meeting Type *</Label>
                    <Select value={meetingType} onValueChange={setMeetingType}>
                      <SelectTrigger className="h-9 text-sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="discovery">🔍 Discovery</SelectItem>
                        <SelectItem value="demo">🖥️ Demo</SelectItem>
                        <SelectItem value="closing">🤝 Closing</SelectItem>
                        <SelectItem value="follow_up">📞 Follow-up</SelectItem>
                        <SelectItem value="other">📋 Anders</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Contact Persons */}
                  {availableContacts.length > 0 && (
                    <div>
                      <Label className="text-xs text-slate-700 dark:text-slate-300 flex items-center gap-1">
                        👥 {t('form.selectContacts')}
                      </Label>
                      <div className="mt-1 space-y-1 max-h-32 overflow-y-auto p-2 border border-slate-200 dark:border-slate-700 rounded-md bg-slate-50 dark:bg-slate-800">
                        {availableContacts.map((contact) => {
                          const isSelected = selectedContactIds.includes(contact.id)
                          return (
                            <label
                              key={contact.id}
                              className={`flex items-center gap-2 p-1.5 rounded cursor-pointer text-xs ${
                                isSelected ? 'bg-green-100 dark:bg-green-900/50' : 'hover:bg-slate-100 dark:hover:bg-slate-700'
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setSelectedContactIds(prev => [...prev, contact.id])
                                  } else {
                                    setSelectedContactIds(prev => prev.filter(id => id !== contact.id))
                                  }
                                }}
                                className="rounded border-gray-300 dark:border-gray-600"
                              />
                              <span className="truncate text-slate-900 dark:text-white">{contact.name}</span>
                              {contact.decision_authority === 'decision_maker' && (
                                <span className="text-xs bg-green-200 dark:bg-green-800 text-green-700 dark:text-green-300 px-1 rounded">DM</span>
                              )}
                            </label>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Deal Selector */}
                  {availableDeals.length > 0 && (
                    <div>
                      <Label className="text-xs text-slate-700 dark:text-slate-300 flex items-center gap-1">
                        🎯 {t('form.selectDeal')}
                      </Label>
                      <Select 
                        value={selectedDealId || 'none'} 
                        onValueChange={(val) => setSelectedDealId(val === 'none' ? '' : val)}
                      >
                        <SelectTrigger className="h-9 text-sm mt-1">
                          <SelectValue placeholder={t('form.selectDealPlaceholder')} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">— {t('form.noDeal')} —</SelectItem>
                          {availableDeals.map((deal) => (
                            <SelectItem key={deal.id} value={deal.id}>
                              🎯 {deal.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  {(contactsLoading || dealsLoading) && (
                    <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
                      <Icons.spinner className="h-3 w-3 animate-spin" />
                      {t('loading')}
                    </div>
                  )}

                  {/* Advanced toggle */}
                  <button
                    type="button"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 flex items-center gap-1"
                  >
                    {showAdvanced ? <Icons.chevronDown className="h-3 w-3" /> : <Icons.chevronRight className="h-3 w-3" />}
                    {t('form.customNotes')}
                  </button>

                  {showAdvanced && (
                    <div className="space-y-3">
                      <div>
                        <Label htmlFor="notes" className="text-xs text-slate-700 dark:text-slate-300">{t('form.customNotes')}</Label>
                        <Textarea
                          id="notes"
                          value={customNotes}
                          onChange={(e) => setCustomNotes(e.target.value)}
                          placeholder={t('form.customNotesPlaceholder')}
                          rows={2}
                          className="text-sm"
                        />
                      </div>
                      
                      {/* Output Language Selector */}
                      <LanguageSelect
                        value={outputLanguage}
                        onChange={setOutputLanguage}
                        label={tLang('outputLanguage')}
                        description={tLang('outputLanguageDesc')}
                        disabled={loading}
                      />
                    </div>
                  )}

                  <Button 
                    type="submit" 
                    disabled={loading || !companyName}
                    className="w-full bg-green-600 hover:bg-green-700"
                  >
                    {loading ? (
                      <>
                        <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
                        {t('form.generating')}
                      </>
                    ) : (
                      <>
                        <Icons.zap className="mr-2 h-4 w-4" />
                        {t('form.startPrep')}
                      </>
                    )}
                  </Button>
                </form>
              </div>

              {/* How it works Panel */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950 dark:to-emerald-950 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <Icons.sparkles className="h-4 w-4 text-green-600 dark:text-green-400" />
                  {t('whatYouGet.title')}
                </h3>
                <ul className="space-y-2 text-xs text-slate-700 dark:text-slate-300">
                  <li className="flex items-start gap-2">
                    <Icons.check className="h-4 w-4 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" />
                    <span>{t('whatYouGet.item1')}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <Icons.check className="h-4 w-4 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" />
                    <span>{t('whatYouGet.item2')}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <Icons.check className="h-4 w-4 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" />
                    <span>{t('whatYouGet.item3')}</span>
                  </li>
                </ul>
              </div>

            </div>
          </div>
        </div>

        <Toaster />
      </div>
    </DashboardLayout>
  )
}
