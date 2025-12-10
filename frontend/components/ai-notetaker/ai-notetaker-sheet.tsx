'use client'

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { api } from '@/lib/api'
import { logger } from '@/lib/logger'
import { 
  ScheduleRecordingRequest, 
  ScheduleRecordingResponse,
  PLATFORM_INFO,
  MeetingPlatform 
} from '@/types/ai-notetaker'
import type { ProspectContact, Deal } from '@/types'

interface AINotetakerSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: (recording: ScheduleRecordingResponse) => void
  // Pre-fill props
  prefilledMeetingUrl?: string
  prefilledMeetingTitle?: string
  prefilledProspectId?: string
}

interface Prospect {
  id: string
  company_name: string
}

export function AINotetakerSheet({
  open,
  onOpenChange,
  onSuccess,
  prefilledMeetingUrl,
  prefilledMeetingTitle,
  prefilledProspectId
}: AINotetakerSheetProps) {
  const t = useTranslations('aiNotetaker')
  const tCommon = useTranslations('common')
  const { toast } = useToast()
  const supabase = createClientComponentClient()

  // Form state
  const [meetingUrl, setMeetingUrl] = useState('')
  const [meetingTitle, setMeetingTitle] = useState('')
  const [scheduleMode, setScheduleMode] = useState<'now' | 'later'>('now')
  const [scheduledDate, setScheduledDate] = useState('')
  const [scheduledTime, setScheduledTime] = useState('')
  const [prospectId, setProspectId] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(false)

  // Prospects for dropdown
  const [prospects, setProspects] = useState<Prospect[]>([])
  const [loadingProspects, setLoadingProspects] = useState(false)

  // Detected platform
  const [detectedPlatform, setDetectedPlatform] = useState<MeetingPlatform | null>(null)

  // Context state (contacts, deals, and preparations linked to prospect)
  const [showContext, setShowContext] = useState(false)
  const [availableContacts, setAvailableContacts] = useState<ProspectContact[]>([])
  const [selectedContactIds, setSelectedContactIds] = useState<string[]>([])
  const [availableDeals, setAvailableDeals] = useState<Deal[]>([])
  const [selectedDealId, setSelectedDealId] = useState<string>('')
  const [availablePreps, setAvailablePreps] = useState<Array<{ id: string; meeting_type: string; created_at: string }>>([])
  const [selectedPrepId, setSelectedPrepId] = useState<string>('')
  const [loadingContext, setLoadingContext] = useState(false)

  // Reset and prefill when sheet opens
  useEffect(() => {
    if (open) {
      setMeetingUrl(prefilledMeetingUrl || '')
      setMeetingTitle(prefilledMeetingTitle || '')
      setProspectId(prefilledProspectId)
      setScheduleMode(prefilledMeetingUrl ? 'now' : 'later')
      setScheduledDate('')
      setScheduledTime('')
      setDetectedPlatform(null)

      // Detect platform from prefilled URL
      if (prefilledMeetingUrl) {
        detectPlatform(prefilledMeetingUrl)
      }

      // Fetch prospects
      fetchProspects()
    }
  }, [open, prefilledMeetingUrl, prefilledMeetingTitle, prefilledProspectId])

  // Detect platform from URL
  const detectPlatform = (url: string) => {
    if (url.includes('teams.microsoft.com') || url.includes('teams.live.com')) {
      setDetectedPlatform('teams')
    } else if (url.includes('meet.google.com')) {
      setDetectedPlatform('meet')
    } else if (url.includes('zoom.us') || url.includes('zoomgov.com')) {
      setDetectedPlatform('zoom')
    } else if (url.includes('webex.com')) {
      setDetectedPlatform('webex')
    } else {
      setDetectedPlatform(null)
    }
  }

  // Handle URL change
  const handleUrlChange = (url: string) => {
    setMeetingUrl(url)
    detectPlatform(url)
  }

  // Fetch prospects for dropdown
  const fetchProspects = async () => {
    setLoadingProspects(true)
    try {
      const { data } = await api.get<{ prospects: Prospect[] }>('/api/v1/prospects')
      if (data?.prospects) {
        setProspects(data.prospects)
      }
    } catch (error) {
      logger.error('Failed to fetch prospects', error)
    } finally {
      setLoadingProspects(false)
    }
  }

  // Fetch contacts, deals, and preparations when prospect changes
  useEffect(() => {
    const fetchContext = async () => {
      if (!prospectId) {
        setAvailableContacts([])
        setAvailableDeals([])
        setAvailablePreps([])
        setSelectedContactIds([])
        setSelectedDealId('')
        setSelectedPrepId('')
        return
      }

      setLoadingContext(true)
      try {
        // Fetch contacts, deals, and preparations in parallel
        const [contactsResult, dealsResult, prepsResult] = await Promise.all([
          api.get<{ contacts: ProspectContact[] }>(`/api/v1/prospects/${prospectId}/contacts`),
          supabase
            .from('deals')
            .select('*')
            .eq('prospect_id', prospectId)
            .eq('is_active', true)
            .order('created_at', { ascending: false }),
          supabase
            .from('meeting_preps')
            .select('id, meeting_type, created_at')
            .eq('prospect_id', prospectId)
            .eq('status', 'completed')
            .order('created_at', { ascending: false })
            .limit(5)
        ])

        if (!contactsResult.error && contactsResult.data) {
          setAvailableContacts(contactsResult.data.contacts || [])
        }
        if (!dealsResult.error && dealsResult.data) {
          setAvailableDeals(dealsResult.data || [])
        }
        if (!prepsResult.error && prepsResult.data) {
          setAvailablePreps(prepsResult.data || [])
          // Auto-select the most recent preparation
          if (prepsResult.data.length > 0) {
            setSelectedPrepId(prepsResult.data[0].id)
          }
        }
      } catch (error) {
        logger.error('Failed to fetch context', error)
      } finally {
        setLoadingContext(false)
      }
    }

    fetchContext()
  }, [prospectId, supabase])

  // Handle form submission
  const handleSubmit = async () => {
    if (!meetingUrl.trim()) {
      toast({
        title: t('error'),
        description: t('urlRequired'),
        variant: 'destructive'
      })
      return
    }

    setLoading(true)
    try {
      // Build request with context
      const request: ScheduleRecordingRequest = {
        meeting_url: meetingUrl.trim(),
        meeting_title: meetingTitle.trim() || undefined,
        prospect_id: prospectId || undefined,
        // Context fields
        meeting_prep_id: selectedPrepId || undefined,
        contact_ids: selectedContactIds.length > 0 ? selectedContactIds : undefined,
        deal_id: selectedDealId || undefined,
      }

      // Add scheduled time if scheduling for later
      if (scheduleMode === 'later' && scheduledDate && scheduledTime) {
        const scheduledDateTime = new Date(`${scheduledDate}T${scheduledTime}`)
        request.scheduled_time = scheduledDateTime.toISOString()
      }

      const { data, error } = await api.post<ScheduleRecordingResponse>(
        '/api/v1/ai-notetaker/schedule',
        request
      )

      if (error || !data) {
        throw new Error(error?.message || 'Failed to schedule')
      }

      toast({
        title: t('success'),
        description: scheduleMode === 'now' 
          ? t('successNow')
          : t('successLater', { date: scheduledDate, time: scheduledTime })
      })

      onSuccess?.(data)
      onOpenChange(false)

    } catch (error) {
      logger.error('Failed to schedule AI Notetaker', error)
      toast({
        title: t('error'),
        description: error instanceof Error ? error.message : 'Failed to schedule',
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  // Get today's date for min date input
  const today = new Date().toISOString().split('T')[0]

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader className="mb-6">
          <SheetTitle className="flex items-center gap-2">
            <Icons.fileText className="h-5 w-5 text-orange-500" />
            {t('title')}
          </SheetTitle>
          <SheetDescription>
            {t('description')}
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-6">
          {/* Meeting URL */}
          <div className="space-y-2">
            <Label htmlFor="meeting-url">{t('urlLabel')} *</Label>
            <div className="relative">
              <Input
                id="meeting-url"
                value={meetingUrl}
                onChange={(e) => handleUrlChange(e.target.value)}
                placeholder={t('urlPlaceholder')}
                className="pr-10"
              />
              {detectedPlatform && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <span className="text-lg" title={PLATFORM_INFO[detectedPlatform].label}>
                    {PLATFORM_INFO[detectedPlatform].icon}
                  </span>
                </div>
              )}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {t('urlHelp')}
            </p>
          </div>

          {/* Meeting Title (optional) */}
          <div className="space-y-2">
            <Label htmlFor="meeting-title">
              {t('titleLabel')} <span className="text-slate-400">({tCommon('optional')})</span>
            </Label>
            <Input
              id="meeting-title"
              value={meetingTitle}
              onChange={(e) => setMeetingTitle(e.target.value)}
              placeholder={t('titlePlaceholder')}
            />
          </div>

          {/* Schedule Mode */}
          <div className="space-y-3">
            <Label>{t('whenToJoin')}</Label>
            <RadioGroup
              value={scheduleMode}
              onValueChange={(v) => setScheduleMode(v as 'now' | 'later')}
              className="space-y-2"
            >
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="now" id="join-now" />
                <Label htmlFor="join-now" className="cursor-pointer font-normal">
                  {t('joinNow')}
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="later" id="join-later" />
                <Label htmlFor="join-later" className="cursor-pointer font-normal">
                  {t('scheduleLater')}
                </Label>
              </div>
            </RadioGroup>
          </div>

          {/* Date/Time picker (when scheduling for later) */}
          {scheduleMode === 'later' && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="scheduled-date">{t('dateLabel')}</Label>
                <Input
                  id="scheduled-date"
                  type="date"
                  value={scheduledDate}
                  onChange={(e) => setScheduledDate(e.target.value)}
                  min={today}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="scheduled-time">{t('timeLabel')}</Label>
                <Input
                  id="scheduled-time"
                  type="time"
                  value={scheduledTime}
                  onChange={(e) => setScheduledTime(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* Prospect Selector */}
          <div className="space-y-2">
            <Label>{t('prospectLabel')}</Label>
            <Select
              value={prospectId || 'none'}
              onValueChange={(v) => setProspectId(v === 'none' ? undefined : v)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a prospect..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">
                  <span className="text-slate-500">No prospect linked</span>
                </SelectItem>
                {prospects.map((prospect) => (
                  <SelectItem key={prospect.id} value={prospect.id}>
                    {prospect.company_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Context Section (Preparation, Contacts & Deals) - only show if prospect selected */}
          {prospectId && (availableContacts.length > 0 || availableDeals.length > 0 || availablePreps.length > 0) && (
            <div className="space-y-3">
              <Button 
                type="button"
                variant="ghost" 
                size="sm" 
                className="w-full justify-between text-slate-600 dark:text-slate-400"
                onClick={() => setShowContext(!showContext)}
              >
                <span className="flex items-center gap-2">
                  <Icons.users className="h-4 w-4" />
                  {t('contextLabel')}
                  {selectedContactIds.length > 0 && (
                    <span className="text-xs bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400 px-1.5 py-0.5 rounded">
                      {selectedContactIds.length}
                    </span>
                  )}
                </span>
                <Icons.chevronDown className={`h-4 w-4 transition-transform ${showContext ? 'rotate-180' : ''}`} />
              </Button>
              
              {showContext && (
                <div className="space-y-4 pl-2 border-l-2 border-slate-200 dark:border-slate-700">
                  {/* Preparation */}
                  {availablePreps.length > 0 && (
                    <div className="space-y-2">
                      <Label className="text-sm text-slate-500">{t('prepLabel')}</Label>
                      <Select
                        value={selectedPrepId || 'none'}
                        onValueChange={(v) => setSelectedPrepId(v === 'none' ? '' : v)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder={t('prepPlaceholder')} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">
                            <span className="text-slate-500">{t('noPrep')}</span>
                          </SelectItem>
                          {availablePreps.map((prep) => (
                            <SelectItem key={prep.id} value={prep.id}>
                              {prep.meeting_type} - {new Date(prep.created_at).toLocaleDateString()}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  {/* Contacts */}
                  {availableContacts.length > 0 && (
                    <div className="space-y-2">
                      <Label className="text-sm text-slate-500">{t('contactsLabel')}</Label>
                      <div className="space-y-2 max-h-32 overflow-y-auto">
                        {availableContacts.map((contact) => (
                          <div key={contact.id} className="flex items-center gap-2">
                            <Checkbox
                              id={`contact-${contact.id}`}
                              checked={selectedContactIds.includes(contact.id)}
                              onCheckedChange={(checked) => {
                                if (checked) {
                                  setSelectedContactIds([...selectedContactIds, contact.id])
                                } else {
                                  setSelectedContactIds(selectedContactIds.filter((id) => id !== contact.id))
                                }
                              }}
                            />
                            <label
                              htmlFor={`contact-${contact.id}`}
                              className="text-sm cursor-pointer flex-1"
                            >
                              {contact.name}
                              {contact.role && (
                                <span className="text-slate-500 ml-1">({contact.role})</span>
                              )}
                            </label>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Deals */}
                  {availableDeals.length > 0 && (
                    <div className="space-y-2">
                      <Label className="text-sm text-slate-500">{t('dealLabel')}</Label>
                      <Select
                        value={selectedDealId || 'none'}
                        onValueChange={(v) => setSelectedDealId(v === 'none' ? '' : v)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder={t('dealPlaceholder')} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">
                            <span className="text-slate-500">{t('noDeal')}</span>
                          </SelectItem>
                          {availableDeals.map((deal) => (
                            <SelectItem key={deal.id} value={deal.id}>
                              {deal.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Submit Button */}
          <Button
            onClick={handleSubmit}
            disabled={loading || !meetingUrl.trim()}
            className="w-full bg-orange-600 hover:bg-orange-700"
          >
            {loading ? (
              <>
                <Icons.spinner className="h-4 w-4 mr-2 animate-spin" />
                {t('scheduling')}
              </>
            ) : (
              <>
                <Icons.fileText className="h-4 w-4 mr-2" />
                {t('submit')}
              </>
            )}
          </Button>

          {/* Info box */}
          <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 text-sm text-slate-600 dark:text-slate-400">
            <div className="flex items-start gap-2">
              <Icons.info className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <div>{t('infoBox')}</div>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}

