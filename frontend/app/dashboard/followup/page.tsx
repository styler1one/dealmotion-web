'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/date-utils'
import { logger } from '@/lib/logger'
import { getErrorMessage } from '@/lib/error-utils'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { Toaster } from '@/components/ui/toaster'
import { DashboardLayout } from '@/components/layout'
import { ProspectAutocomplete } from '@/components/prospect-autocomplete'
import { useTranslations } from 'next-intl'
import { useSettings } from '@/lib/settings-context'
import { useConfirmDialog } from '@/components/confirm-dialog'
import type { User } from '@supabase/supabase-js'
import type { ProspectContact, Deal } from '@/types'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

interface FollowupItem {
  id: string
  prospect_company_name: string | null
  meeting_subject: string | null
  meeting_date: string | null
  status: string
  executive_summary: string | null
  audio_duration_seconds: number | null
  created_at: string
  completed_at: string | null
}

export default function FollowupPage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const { confirm } = useConfirmDialog()
  const t = useTranslations('followup')
  const tCommon = useTranslations('common')
  const { settings, loaded: settingsLoaded } = useSettings()
  
  const [user, setUser] = useState<User | null>(null)
  const [followups, setFollowups] = useState<FollowupItem[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadType, setUploadType] = useState<'audio' | 'transcript'>('audio')
  
  // Form state
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [prospectCompany, setProspectCompany] = useState('')
  const [meetingSubject, setMeetingSubject] = useState('')
  const [meetingDate, setMeetingDate] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  
  // Contact selector state
  const [availableContacts, setAvailableContacts] = useState<ProspectContact[]>([])
  const [selectedContactIds, setSelectedContactIds] = useState<string[]>([])
  const [loadingContacts, setLoadingContacts] = useState(false)
  
  // Deal selector state
  const [availableDeals, setAvailableDeals] = useState<Deal[]>([])
  const [selectedDealId, setSelectedDealId] = useState<string>('')
  const [loadingDeals, setLoadingDeals] = useState(false)
  
  // Fetch contacts and deals when prospect company changes (optimized: single search, parallel fetch)
  useEffect(() => {
    const fetchContactsAndDeals = async () => {
      if (!prospectCompany) {
        setAvailableContacts([])
        setSelectedContactIds([])
        setAvailableDeals([])
        setSelectedDealId('')
        return
      }
      
      setLoadingContacts(true)
      setLoadingDeals(true)
      
      try {
        // Single prospect search using api client
        const { data: prospects, error: prospectError } = await api.get<Array<{ id: string; company_name: string }>>(
          `/api/v1/prospects/search?q=${encodeURIComponent(prospectCompany)}&limit=5`
        )
        
        if (prospectError || !prospects || !Array.isArray(prospects)) {
          setAvailableContacts([])
          setAvailableDeals([])
          return
        }
        
        const prospect = prospects.find((p) => 
          p.company_name?.toLowerCase() === prospectCompany.toLowerCase()
        )
        
        if (prospect) {
          // Fetch contacts AND deals in PARALLEL
          const [contactsResult, dealsResult] = await Promise.all([
            api.get<{ contacts: ProspectContact[] }>(`/api/v1/prospects/${prospect.id}/contacts`),
            supabase
              .from('deals')
              .select('*')
              .eq('prospect_id', prospect.id)
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
        logger.error('Error fetching contacts/deals', error)
        setAvailableContacts([])
        setAvailableDeals([])
      } finally {
        setLoadingContacts(false)
        setLoadingDeals(false)
      }
    }
    
    const debounce = setTimeout(fetchContactsAndDeals, 500)
    return () => clearTimeout(debounce)
  }, [prospectCompany, supabase])
  
  const fetchFollowups = useCallback(async () => {
    try {
      // Use api client for consistent auth handling
      const { data, error } = await api.get<FollowupItem[]>('/api/v1/followup/list')
      
      if (!error && data) {
        setFollowups(data)
      }
    } catch (error) {
      logger.error('Error fetching followups', error)
    } finally {
      setLoading(false)
    }
  }, [])

  const followupsRef = useRef<FollowupItem[]>([])
  followupsRef.current = followups

  useEffect(() => {
    // Load user and followups in parallel
    Promise.all([
      supabase.auth.getUser().then(({ data: { user } }) => setUser(user)),
      fetchFollowups()
    ])

    // Check for pre-selected company from Preparation page
    const followupFor = sessionStorage.getItem('followupForCompany')
    if (followupFor) {
      setProspectCompany(followupFor)
      sessionStorage.removeItem('followupForCompany')
    }
  }, [fetchFollowups])

  useEffect(() => {
    const interval = setInterval(() => {
      const hasProcessing = followupsRef.current.some(f => 
        ['uploading', 'transcribing', 'summarizing'].includes(f.status)
      )
      if (hasProcessing) {
        fetchFollowups()
      }
    }, 5000)
    
    return () => clearInterval(interval)
  }, [fetchFollowups])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const ext = file.name.toLowerCase().split('.').pop() || ''
      
      if (uploadType === 'audio') {
        const allowedTypes = ['audio/mpeg', 'audio/mp4', 'audio/wav', 'audio/webm', 'audio/x-m4a']
        if (!allowedTypes.includes(file.type)) {
          toast({
            title: t('toast.invalidFileType'),
            description: t('toast.invalidFileTypeDescAudio'),
            variant: 'destructive'
          })
          return
        }
        
        if (file.size > 50 * 1024 * 1024) {
          toast({
            title: t('toast.fileTooLarge'),
            description: t('toast.fileTooLargeDescAudio'),
            variant: 'destructive'
          })
          return
        }
      } else {
        const allowedExts = ['txt', 'md', 'docx', 'srt']
        if (!allowedExts.includes(ext)) {
          toast({
            title: t('toast.invalidFileType'),
            description: t('toast.invalidFileTypeDescTranscript'),
            variant: 'destructive'
          })
          return
        }
        
        if (file.size > 10 * 1024 * 1024) {
          toast({
            title: t('toast.fileTooLarge'),
            description: t('toast.fileTooLargeDescTranscript'),
            variant: 'destructive'
          })
          return
        }
      }
      
      setSelectedFile(file)
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) {
      toast({
        title: t('toast.noFileSelected'),
        description: t('toast.noFileSelectedDesc'),
        variant: 'destructive'
      })
      return
    }

    setUploading(true)
    setUploadProgress(10)

    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        throw new Error('Not authenticated')
      }

      const formData = new FormData()
      formData.append('file', selectedFile)
      if (prospectCompany) formData.append('prospect_company_name', prospectCompany)
      if (meetingSubject) formData.append('meeting_subject', meetingSubject)
      if (meetingDate) formData.append('meeting_date', meetingDate)
      if (selectedContactIds.length > 0) formData.append('contact_ids', selectedContactIds.join(','))
      if (selectedDealId) formData.append('deal_id', selectedDealId)
      formData.append('include_coaching', 'false') // Coaching can be enabled later in Follow-up Actions
      formData.append('language', settings.email_language) // Use language from user settings

      setUploadProgress(30)

      const endpoint = uploadType === 'audio' 
        ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1/followup/upload`
        : `${process.env.NEXT_PUBLIC_API_URL}/api/v1/followup/upload-transcript`

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`
        },
        body: formData
      })

      setUploadProgress(80)

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Upload failed')
      }

      setUploadProgress(100)

      toast({
        title: t('toast.uploadStarted'),
        description: t('toast.uploadStartedDesc')
      })

      // Reset form
      setSelectedFile(null)
      setProspectCompany('')
      setMeetingSubject('')
      setMeetingDate('')
      setShowAdvanced(false)
      setSelectedContactIds([])
      setAvailableContacts([])
      setSelectedDealId('')
      setAvailableDeals([])
      
      fetchFollowups()

    } catch (error) {
      logger.error('Upload failed', error)
      toast({
        title: t('toast.failed'),
        description: getErrorMessage(error) || t('toast.failedDesc'),
        variant: 'destructive'
      })
    } finally {
      setUploading(false)
      setUploadProgress(0)
    }
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
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
      const { error } = await api.delete(`/api/v1/followup/${id}`)

      if (!error) {
        toast({ title: t('toast.deleted') })
        fetchFollowups()
      } else {
        throw new Error('Delete failed')
      }
    } catch (error) {
      toast({
        title: t('toast.failed'),
        variant: 'destructive'
      })
    }
  }

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-'
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const completedFollowups = followups.filter(f => f.status === 'completed').length
  const processingFollowups = followups.filter(f => ['uploading', 'transcribing', 'summarizing'].includes(f.status)).length

  if (loading) {
    return (
      <DashboardLayout user={user}>
        <div className="flex items-center justify-center h-full">
          <div className="text-center space-y-4">
            <Icons.spinner className="h-8 w-8 animate-spin text-orange-600 mx-auto" />
            <p className="text-slate-500 dark:text-slate-400">{t('loading')}</p>
          </div>
        </div>
      </DashboardLayout>
    )
  }

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
          
          {/* Left Column - Follow-ups History */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                <Icons.mail className="h-5 w-5 text-slate-400" />
                {t('history.title')}
                <span className="text-sm font-normal text-slate-400">({followups.length})</span>
              </h2>
              <Button variant="ghost" size="sm" onClick={fetchFollowups}>
                <Icons.refresh className="h-4 w-4" />
              </Button>
            </div>

            {followups.length === 0 ? (
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-12 text-center">
                <Icons.mic className="h-16 w-16 text-slate-200 dark:text-slate-700 mx-auto mb-4" />
                <h3 className="font-semibold text-slate-700 dark:text-slate-200 mb-2">{t('history.empty')}</h3>
                <p className="text-slate-500 dark:text-slate-400 text-sm mb-4">
                  {t('history.emptyDesc')}
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {followups.map((followup) => (
                  <div
                    key={followup.id}
                    className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 hover:shadow-md dark:hover:shadow-slate-800/50 transition-all cursor-pointer group"
                    onClick={() => router.push(`/dashboard/followup/${followup.id}`)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-semibold text-slate-900 dark:text-white truncate">
                            {followup.prospect_company_name || followup.meeting_subject || 'Meeting'}
                          </h4>
                          
                          {followup.status === 'completed' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 dark:bg-green-900/50 text-green-700 dark:text-green-400 flex-shrink-0">
                              <Icons.check className="h-3 w-3" />
                              {t('stats.completed')}
                            </span>
                          )}
                          {followup.status === 'transcribing' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-50 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-400 flex-shrink-0">
                              <Icons.spinner className="h-3 w-3 animate-spin" />
                              {t('form.processing')}
                            </span>
                          )}
                          {followup.status === 'summarizing' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-purple-50 dark:bg-purple-900/50 text-purple-700 dark:text-purple-400 flex-shrink-0">
                              <Icons.spinner className="h-3 w-3 animate-spin" />
                              {t('form.processing')}
                            </span>
                          )}
                          {followup.status === 'uploading' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400 flex-shrink-0">
                              <Icons.spinner className="h-3 w-3 animate-spin" />
                              {t('form.processing')}
                            </span>
                          )}
                          {followup.status === 'failed' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 dark:bg-red-900/50 text-red-700 dark:text-red-400 flex-shrink-0">
                              <Icons.alertCircle className="h-3 w-3" />
                              {t('toast.failed')}
                            </span>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                          {followup.meeting_date && (
                            <span>{formatDate(followup.meeting_date, settings.output_language)}</span>
                          )}
                          {followup.audio_duration_seconds && (
                            <span className="flex items-center gap-1">
                              <Icons.clock className="h-3 w-3" />
                              {formatDuration(followup.audio_duration_seconds)}
                            </span>
                          )}
                          <span>{formatDate(followup.created_at, settings.output_language)}</span>
                        </div>

                        {followup.executive_summary && (
                          <p className="text-xs text-slate-500 dark:text-slate-400 mt-2 line-clamp-1">
                            {followup.executive_summary}
                          </p>
                        )}
                      </div>
                      
                      <div className="flex items-center gap-1 ml-4">
                        {followup.status === 'completed' && (
                          <Button
                            variant="default"
                            size="sm"
                            className="h-8 text-xs bg-orange-600 hover:bg-orange-700 opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={(e) => {
                              e.stopPropagation()
                              router.push(`/dashboard/followup/${followup.id}`)
                            }}
                          >
                            <Icons.eye className="h-3 w-3 mr-1" />
                            {tCommon('view')}
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-slate-400 hover:text-red-600 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => handleDelete(followup.id, e)}
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
                    <p className="text-2xl font-bold text-green-600 dark:text-green-400">{completedFollowups}</p>
                    <p className="text-xs text-green-700 dark:text-green-300">{t('stats.completed')}</p>
                  </div>
                  <div className="bg-orange-50 dark:bg-orange-900/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">{processingFollowups}</p>
                    <p className="text-xs text-orange-700 dark:text-orange-300">{t('stats.processing')}</p>
                  </div>
                </div>
              </div>

              {/* Upload Form */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <Icons.upload className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                  {t('form.title')}
                </h3>
                
                <div className="space-y-3">
                  {/* Upload Type Selector */}
                  <div className="flex gap-2">
                    <Button
                      variant={uploadType === 'audio' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => { setUploadType('audio'); setSelectedFile(null); }}
                      disabled={uploading}
                      className="flex-1 h-8 text-xs"
                    >
                      <Icons.mic className="h-3 w-3 mr-1" />
                      {t('form.uploadAudio')}
                    </Button>
                    <Button
                      variant={uploadType === 'transcript' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => { setUploadType('transcript'); setSelectedFile(null); }}
                      disabled={uploading}
                      className="flex-1 h-8 text-xs"
                    >
                      <Icons.fileText className="h-3 w-3 mr-1" />
                      {t('form.uploadTranscript')}
                    </Button>
                  </div>

                  {/* File Upload */}
                  <div 
                    className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors
                      ${selectedFile ? 'border-green-500 dark:border-green-600 bg-green-50 dark:bg-green-900/30' : 'border-gray-300 dark:border-slate-600 hover:border-gray-400 dark:hover:border-slate-500'}
                      ${uploading ? 'pointer-events-none opacity-50' : ''}`}
                    onClick={() => document.getElementById('file-input')?.click()}
                  >
                    <input
                      id="file-input"
                      type="file"
                      accept={uploadType === 'audio' 
                        ? "audio/mpeg,audio/mp4,audio/wav,audio/webm,audio/x-m4a"
                        : ".txt,.md,.docx,.srt"}
                      onChange={handleFileSelect}
                      className="hidden"
                      disabled={uploading}
                    />
                    {selectedFile ? (
                      <div className="flex items-center justify-center gap-2">
                        <Icons.fileText className="h-6 w-6 text-green-600 dark:text-green-400" />
                        <div className="text-left">
                          <p className="font-medium text-xs truncate max-w-[150px] text-slate-900 dark:text-white">{selectedFile.name}</p>
                          <p className="text-xs text-slate-500 dark:text-slate-400">
                            {(selectedFile.size / 1024 / 1024).toFixed(1)} MB
                          </p>
                        </div>
                      </div>
                    ) : (
                      <>
                        <Icons.upload className="h-8 w-8 mx-auto text-gray-400 dark:text-slate-500 mb-1" />
                        <p className="text-xs text-gray-600 dark:text-slate-300">
                          {t('form.dragDrop')}
                        </p>
                        <p className="text-xs text-gray-400 dark:text-slate-500 mt-1">
                          {uploadType === 'audio' 
                            ? t('form.supportedFormatsAudio') 
                            : t('form.supportedFormatsTranscript')}
                        </p>
                      </>
                    )}
                  </div>

                  {/* Progress bar */}
                  {uploading && (
                    <div className="space-y-1">
                      <div className="h-1.5 bg-gray-200 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-orange-600 transition-all duration-300"
                          style={{ width: `${uploadProgress}%` }}
                        />
                      </div>
                      <p className="text-xs text-center text-slate-500 dark:text-slate-400">
                        {uploadProgress < 30 ? 'Uploaden...' : 
                         uploadProgress < 80 ? 'Verwerken...' : 'Bijna klaar...'}
                      </p>
                    </div>
                  )}

                  {/* Prospect field */}
                  <div>
                    <Label className="text-xs text-slate-700 dark:text-slate-300">{t('form.selectProspect')}</Label>
                    <ProspectAutocomplete
                      value={prospectCompany}
                      onChange={setProspectCompany}
                      placeholder={t('form.selectProspectPlaceholder')}
                      disabled={uploading}
                    />
                  </div>

                  {/* Contact selector */}
                  {availableContacts.length > 0 && (
                    <div>
                      <Label className="text-xs text-slate-700 dark:text-slate-300">{t('form.selectContact')}</Label>
                      <div className="space-y-2 mt-2">
                        {availableContacts.map((contact) => (
                          <label
                            key={contact.id}
                            className="flex items-center gap-3 p-2 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer"
                          >
                            <Checkbox
                              checked={selectedContactIds.includes(contact.id)}
                              onCheckedChange={(checked) => {
                                if (checked) {
                                  setSelectedContactIds([...selectedContactIds, contact.id])
                                } else {
                                  setSelectedContactIds(selectedContactIds.filter(id => id !== contact.id))
                                }
                              }}
                              disabled={uploading}
                            />
                            <div>
                              <p className="text-sm font-medium text-slate-900 dark:text-white">{contact.name}</p>
                              {contact.role && (
                                <p className="text-xs text-slate-500 dark:text-slate-400">{contact.role}</p>
                              )}
                            </div>
                          </label>
                        ))}
                      </div>
                    </div>
                  )}
                  {loadingContacts && prospectCompany && (
                    <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                      <Icons.spinner className="h-3 w-3 animate-spin" />
                      Loading contacts...
                    </div>
                  )}

                  {/* Deal selector */}
                  {availableDeals.length > 0 && (
                    <div>
                      <Label className="text-xs text-slate-700 dark:text-slate-300 flex items-center gap-1">
                        🎯 {t('form.selectDeal')}
                      </Label>
                      <Select 
                        value={selectedDealId || 'none'} 
                        onValueChange={(val) => setSelectedDealId(val === 'none' ? '' : val)} 
                        disabled={uploading}
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
                  {loadingDeals && prospectCompany && (
                    <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                      <Icons.spinner className="h-3 w-3 animate-spin" />
                      Loading deals...
                    </div>
                  )}

                  {/* Advanced toggle */}
                  <button
                    type="button"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 flex items-center gap-1"
                  >
                    {showAdvanced ? <Icons.chevronDown className="h-3 w-3" /> : <Icons.chevronRight className="h-3 w-3" />}
                    {tCommon('extraOptions')}
                  </button>

                  {showAdvanced && (
                    <div className="space-y-3 pt-2 border-t border-slate-200 dark:border-slate-700">
                      <div>
                        <Label className="text-xs text-slate-700 dark:text-slate-300">{t('form.subject')}</Label>
                        <Input
                          placeholder={t('form.subjectPlaceholder')}
                          value={meetingSubject}
                          onChange={(e) => setMeetingSubject(e.target.value)}
                          disabled={uploading}
                          className="h-8 text-sm"
                        />
                      </div>
                      <div>
                        <Label className="text-xs text-slate-700 dark:text-slate-300">{t('form.date')}</Label>
                        <Input
                          type="date"
                          value={meetingDate}
                          onChange={(e) => setMeetingDate(e.target.value)}
                          disabled={uploading}
                          className="h-8 text-sm"
                        />
                      </div>
                    </div>
                  )}

                  <Button 
                    className="w-full bg-orange-600 hover:bg-orange-700" 
                    onClick={handleUpload}
                    disabled={!selectedFile || uploading}
                  >
                    {uploading ? (
                      <>
                        <Icons.spinner className="h-4 w-4 mr-2 animate-spin" />
                        {t('form.processing')}
                      </>
                    ) : (
                      <>
                        <Icons.zap className="h-4 w-4 mr-2" />
                        {t('form.startFollowup')}
                      </>
                    )}
                  </Button>
                </div>
              </div>

              {/* How it works Panel */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-gradient-to-br from-orange-50 to-amber-50 dark:from-orange-950 dark:to-amber-950 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <Icons.sparkles className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                  {t('whatYouGet.title')}
                </h3>
                <ul className="space-y-2 text-xs text-slate-700 dark:text-slate-300">
                  <li className="flex items-start gap-2">
                    <Icons.check className="h-4 w-4 text-orange-600 dark:text-orange-400 flex-shrink-0 mt-0.5" />
                    <span>{t('whatYouGet.item1')}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <Icons.check className="h-4 w-4 text-orange-600 dark:text-orange-400 flex-shrink-0 mt-0.5" />
                    <span>{t('whatYouGet.item2')}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <Icons.check className="h-4 w-4 text-orange-600 dark:text-orange-400 flex-shrink-0 mt-0.5" />
                    <span>{t('detail.actionItems')}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <Icons.check className="h-4 w-4 text-orange-600 dark:text-orange-400 flex-shrink-0 mt-0.5" />
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
