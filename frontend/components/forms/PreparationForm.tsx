'use client'

import { useState, useEffect, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { ProspectAutocomplete } from '@/components/prospect-autocomplete'
import { LanguageSelect } from '@/components/language-select'
import { useSettings } from '@/lib/settings-context'
import { api } from '@/lib/api'
import { logger } from '@/lib/logger'
import type { ProspectContact, Deal } from '@/types'

interface PrepStartResult {
  id: string
  prospect_id?: string
}

interface MeetingHistoryItem {
  id: string
  meeting_date: string
  meeting_subject: string
  summary_preview: string
  prospect_company_name: string
  created_at: string
}

interface PreparationFormProps {
  // Pre-filled values (from Hub context)
  initialCompanyName?: string
  initialContacts?: ProspectContact[]  // Pre-loaded contacts from Hub
  initialDeals?: Deal[]                 // Pre-loaded deals from Hub
  calendarMeetingId?: string | null     // Link to calendar meeting
  
  // Callbacks
  onSuccess?: (result?: PrepStartResult) => void
  onCancel?: () => void
  
  // Mode
  isSheet?: boolean  // Different styling for sheet vs page
}

export function PreparationForm({
  initialCompanyName = '',
  initialContacts = [],
  initialDeals = [],
  calendarMeetingId: initialCalendarMeetingId = null,
  onSuccess,
  onCancel,
  isSheet = false
}: PreparationFormProps) {
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const t = useTranslations('preparation')
  const tLang = useTranslations('language')
  const { settings, loaded: settingsLoaded } = useSettings()

  // Form state
  const [companyName, setCompanyName] = useState(initialCompanyName)
  const [meetingType, setMeetingType] = useState('discovery')
  const [customNotes, setCustomNotes] = useState('')
  const [outputLanguage, setOutputLanguage] = useState('en')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [loading, setLoading] = useState(false)
  
  // Contact persons state
  const [availableContacts, setAvailableContacts] = useState<ProspectContact[]>(initialContacts)
  const [selectedContactIds, setSelectedContactIds] = useState<string[]>([])
  const [contactsLoading, setContactsLoading] = useState(false)
  
  // Deal linking state
  const [availableDeals, setAvailableDeals] = useState<Deal[]>(initialDeals)
  const [selectedDealId, setSelectedDealId] = useState<string>('')
  const [dealsLoading, setDealsLoading] = useState(false)
  
  // Meeting history state (previous conversations)
  const [availableMeetingHistory, setAvailableMeetingHistory] = useState<MeetingHistoryItem[]>([])
  const [selectedFollowupIds, setSelectedFollowupIds] = useState<string[]>([])
  const [meetingHistoryLoading, setMeetingHistoryLoading] = useState(false)
  
  // Calendar meeting linking state
  const [calendarMeetingId, setCalendarMeetingId] = useState<string | null>(initialCalendarMeetingId)
  
  // Track if we're in Hub context (pre-filled data)
  const isHubContext = useMemo(() => initialCompanyName.length > 0, [initialCompanyName])

  // Set language from settings on load
  useEffect(() => {
    if (settingsLoaded) {
      setOutputLanguage(settings.output_language)
    }
  }, [settingsLoaded, settings.output_language])
  
  // Load contacts AND deals together when company name changes (single prospect search)
  // Skip if in Hub context (data already provided)
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
      logger.error('Failed to load contacts/deals:', error)
      setAvailableContacts([])
      setAvailableDeals([])
    } finally {
      setContactsLoading(false)
      setDealsLoading(false)
    }
  }

  // Load meeting history for a prospect (previous conversations)
  const loadMeetingHistory = async (prospectName: string) => {
    if (!prospectName || prospectName.length < 2) {
      setAvailableMeetingHistory([])
      setSelectedFollowupIds([])
      return
    }

    setMeetingHistoryLoading(true)
    
    try {
      const { data, error } = await api.get<{ followups: MeetingHistoryItem[]; total: number }>(
        `/api/v1/prep/meeting-history/${encodeURIComponent(prospectName)}`
      )

      if (!error && data) {
        setAvailableMeetingHistory(data.followups || [])
        // Auto-select all by default (user can uncheck if needed)
        if (data.followups && data.followups.length > 0) {
          setSelectedFollowupIds(data.followups.map(f => f.id))
        }
      } else {
        setAvailableMeetingHistory([])
      }
    } catch (error) {
      logger.error('Failed to load meeting history:', error)
      setAvailableMeetingHistory([])
    } finally {
      setMeetingHistoryLoading(false)
    }
  }

  // Only fetch contacts/deals/history if NOT in Hub context
  useEffect(() => {
    if (isHubContext) return  // Data already provided from Hub
    
    const timeoutId = setTimeout(() => {
      loadContactsAndDealsForProspect(companyName)
      loadMeetingHistory(companyName)
    }, 500)

    return () => clearTimeout(timeoutId)
  }, [companyName, isHubContext])
  
  // In Hub context, still load meeting history
  useEffect(() => {
    if (isHubContext && companyName) {
      loadMeetingHistory(companyName)
    }
  }, [isHubContext, companyName])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        toast({ title: t('toast.failed'), description: t('toast.failedDesc'), variant: 'destructive' })
        return
      }

      const { data, error } = await api.post<{ id: string; prospect_id?: string }>('/api/v1/prep/start', {
        prospect_company_name: companyName,
        meeting_type: meetingType,
        custom_notes: customNotes || null,
        contact_ids: selectedContactIds.length > 0 ? selectedContactIds : null,
        deal_id: selectedDealId || null,
        calendar_meeting_id: calendarMeetingId || null,
        language: outputLanguage,
        selected_followup_ids: selectedFollowupIds.length > 0 ? selectedFollowupIds : null
      })

      if (!error && data) {
        toast({ title: t('toast.started'), description: t('toast.startedDesc') })
        
        // Only reset form if not in Hub context
        if (!isSheet) {
          setCompanyName('')
          setCustomNotes('')
          setOutputLanguage(settings.output_language)
          setSelectedContactIds([])
          setAvailableContacts([])
          setSelectedDealId('')
          setAvailableDeals([])
          setSelectedFollowupIds([])
          setAvailableMeetingHistory([])
          setCalendarMeetingId(null)
          setShowAdvanced(false)
        }
        
        // Call success callback with result data for redirect
        onSuccess?.({ id: data.id, prospect_id: data.prospect_id })
      } else {
        toast({ title: t('toast.failed'), description: error?.message || t('toast.failedDesc'), variant: 'destructive' })
      }
    } catch (error) {
      logger.error('Preparation submit failed:', error)
      toast({ title: t('toast.failed'), description: t('toast.failedDesc'), variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <Label htmlFor="company" className="text-xs text-slate-700 dark:text-slate-300">{t('form.selectProspect')} *</Label>
        {isHubContext ? (
          // In Hub context: show read-only company name
          <div className="mt-1 h-9 px-3 flex items-center text-sm bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 rounded-md">
            <Icons.check className="h-4 w-4 text-green-600 dark:text-green-400 mr-2" />
            <span className="text-slate-900 dark:text-white font-medium">{companyName}</span>
          </div>
        ) : (
          // In page context: show autocomplete
          <ProspectAutocomplete
            value={companyName}
            onChange={setCompanyName}
            placeholder={t('form.selectProspectPlaceholder')}
          />
        )}
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

      {/* Meeting History (Previous Conversations) */}
      {availableMeetingHistory.length > 0 && (
        <div>
          <Label className="text-xs text-slate-700 dark:text-slate-300 flex items-center gap-1">
            📜 {t('form.previousMeetings') || 'Previous Meetings'}
            <span className="text-slate-400 font-normal">({availableMeetingHistory.length})</span>
          </Label>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">
            {t('form.previousMeetingsDesc') || 'Include context from previous conversations'}
          </p>
          <div className="mt-1 space-y-1 max-h-40 overflow-y-auto p-2 border border-slate-200 dark:border-slate-700 rounded-md bg-slate-50 dark:bg-slate-800">
            {availableMeetingHistory.map((meeting) => {
              const isSelected = selectedFollowupIds.includes(meeting.id)
              const meetingDate = meeting.meeting_date 
                ? new Date(meeting.meeting_date).toLocaleDateString('nl-NL', { 
                    day: 'numeric', 
                    month: 'short', 
                    year: 'numeric' 
                  })
                : 'Unknown date'
              
              return (
                <label
                  key={meeting.id}
                  className={`flex items-start gap-2 p-2 rounded cursor-pointer text-xs ${
                    isSelected 
                      ? 'bg-purple-100 dark:bg-purple-900/50 border border-purple-200 dark:border-purple-800' 
                      : 'hover:bg-slate-100 dark:hover:bg-slate-700'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedFollowupIds(prev => [...prev, meeting.id])
                      } else {
                        setSelectedFollowupIds(prev => prev.filter(id => id !== meeting.id))
                      }
                    }}
                    className="rounded border-gray-300 dark:border-gray-600 mt-0.5"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-900 dark:text-white truncate">
                        {meeting.meeting_subject || 'Meeting'}
                      </span>
                      <span className="text-slate-400 flex-shrink-0">{meetingDate}</span>
                    </div>
                    {meeting.summary_preview && (
                      <p className="text-slate-500 dark:text-slate-400 mt-0.5 line-clamp-2">
                        {meeting.summary_preview}
                      </p>
                    )}
                  </div>
                </label>
              )
            })}
          </div>
          {selectedFollowupIds.length > 0 && (
            <p className="text-xs text-purple-600 dark:text-purple-400 mt-1">
              ✓ {selectedFollowupIds.length} {selectedFollowupIds.length === 1 ? 'meeting' : 'meetings'} will be included as context
            </p>
          )}
        </div>
      )}

      {(contactsLoading || dealsLoading || meetingHistoryLoading) && (
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

      {/* Action buttons */}
      <div className={`flex gap-2 ${isSheet ? 'pt-2' : ''}`}>
        {isSheet && onCancel && (
          <Button 
            type="button" 
            variant="outline" 
            onClick={onCancel}
            disabled={loading}
            className="flex-1"
          >
            {t('form.cancel')}
          </Button>
        )}
        <Button 
          type="submit" 
          disabled={loading || !companyName}
          className={`${isSheet ? 'flex-1' : 'w-full'} bg-green-600 hover:bg-green-700`}
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
      </div>
    </form>
  )
}

