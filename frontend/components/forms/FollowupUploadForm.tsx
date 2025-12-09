'use client'

import { useState, useEffect, useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { ProspectAutocomplete } from '@/components/prospect-autocomplete'
import { useSettings } from '@/lib/settings-context'
import { api } from '@/lib/api'
import { logger } from '@/lib/logger'
import { getErrorMessage } from '@/lib/error-utils'
import type { ProspectContact, Deal } from '@/types'

interface FollowupUploadFormProps {
  // Pre-filled values (from Hub context)
  initialProspectCompany?: string
  initialContacts?: ProspectContact[]  // Pre-loaded contacts from Hub
  initialDeals?: Deal[]                 // Pre-loaded deals from Hub
  
  // Callbacks
  onSuccess?: () => void
  onCancel?: () => void
  
  // Mode
  isSheet?: boolean  // Different styling for sheet vs page
}

export function FollowupUploadForm({
  initialProspectCompany = '',
  initialContacts = [],
  initialDeals = [],
  onSuccess,
  onCancel,
  isSheet = false
}: FollowupUploadFormProps) {
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const t = useTranslations('followup')
  const tCommon = useTranslations('common')
  const { settings } = useSettings()
  
  // Form state
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [prospectCompany, setProspectCompany] = useState(initialProspectCompany)
  const [meetingSubject, setMeetingSubject] = useState('')
  const [meetingDate, setMeetingDate] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [uploadType, setUploadType] = useState<'audio' | 'transcript'>('audio')
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  
  // Contact selector state
  const [availableContacts, setAvailableContacts] = useState<ProspectContact[]>(initialContacts)
  const [selectedContactIds, setSelectedContactIds] = useState<string[]>([])
  const [loadingContacts, setLoadingContacts] = useState(false)
  
  // Deal selector state
  const [availableDeals, setAvailableDeals] = useState<Deal[]>(initialDeals)
  const [selectedDealId, setSelectedDealId] = useState<string>('')
  const [loadingDeals, setLoadingDeals] = useState(false)
  
  // Track if we're in Hub context (pre-filled data)
  const isHubContext = useMemo(() => initialProspectCompany.length > 0, [initialProspectCompany])
  
  // Fetch contacts and deals when prospect company changes (optimized: single search, parallel fetch)
  // Skip if in Hub context (data already provided)
  useEffect(() => {
    if (isHubContext) return  // Data already provided from Hub
    
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
  }, [prospectCompany, isHubContext, supabase])

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
      formData.append('include_coaching', 'false')
      formData.append('language', settings.email_language)

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

      // Only reset form if not in sheet context
      if (!isSheet) {
        setSelectedFile(null)
        setProspectCompany('')
        setMeetingSubject('')
        setMeetingDate('')
        setShowAdvanced(false)
        setSelectedContactIds([])
        setAvailableContacts([])
        setSelectedDealId('')
        setAvailableDeals([])
      }
      
      // Call success callback
      onSuccess?.()

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

  return (
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
        onClick={() => document.getElementById('followup-file-input')?.click()}
      >
        <input
          id="followup-file-input"
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
        {isHubContext ? (
          // In Hub context: show read-only company name
          <div className="mt-1 h-9 px-3 flex items-center text-sm bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 rounded-md">
            <Icons.check className="h-4 w-4 text-green-600 dark:text-green-400 mr-2" />
            <span className="text-slate-900 dark:text-white font-medium">{prospectCompany}</span>
          </div>
        ) : (
          // In page context: show autocomplete
          <ProspectAutocomplete
            value={prospectCompany}
            onChange={setProspectCompany}
            placeholder={t('form.selectProspectPlaceholder')}
            disabled={uploading}
          />
        )}
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

      {/* Action buttons */}
      <div className={`flex gap-2 ${isSheet ? 'pt-2' : ''}`}>
        {isSheet && onCancel && (
          <Button 
            type="button" 
            variant="outline" 
            onClick={onCancel}
            disabled={uploading}
            className="flex-1"
          >
            {t('form.cancel')}
          </Button>
        )}
        <Button 
          className={`${isSheet ? 'flex-1' : 'w-full'} bg-orange-600 hover:bg-orange-700`}
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
  )
}

