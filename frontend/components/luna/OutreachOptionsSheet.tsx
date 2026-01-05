'use client'

/**
 * Outreach Options Sheet
 * SPEC-046-Luna-Unified-AI-Assistant / IMPL-046-Outreach-From-Contact
 * 
 * Sheet for creating outreach messages from Luna's prepare_outreach CTA.
 * - Channel selection (LinkedIn, Email, WhatsApp)
 * - AI content generation
 * - Save as draft or mark as sent
 */

import React, { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Linkedin,
  Mail,
  MessageCircle,
  Phone,
  Sparkles,
  Copy,
  Check,
  Send,
  Save,
  Loader2,
} from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'
import { Input } from '@/components/ui/input'

// =============================================================================
// TYPES
// =============================================================================

export type OutreachChannel = 'linkedin_connect' | 'linkedin_message' | 'email' | 'whatsapp'

interface OutreachActionData {
  sheet: 'outreach_options'
  prospectId: string
  contactId: string
  researchId?: string
  channels: OutreachChannel[]
}

interface OutreachOptionsSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  actionData: OutreachActionData | null
  onComplete?: () => void
}

interface GenerateResponse {
  subject?: string
  body: string
  channel: OutreachChannel
}

interface ContactData {
  id: string
  email?: string
  linkedin_url?: string
  phone?: string
}

// =============================================================================
// CHANNEL CONFIG
// =============================================================================

const CHANNEL_CONFIG: Record<OutreachChannel, {
  icon: React.ReactNode
  label: string
  description: string
  color: string
}> = {
  linkedin_connect: {
    icon: <Linkedin className="w-5 h-5" />,
    label: 'LinkedIn Connect',
    description: 'Send a connection request with a personalized note',
    color: 'text-blue-600 bg-blue-50',
  },
  linkedin_message: {
    icon: <Linkedin className="w-5 h-5" />,
    label: 'LinkedIn Message',
    description: 'Send a direct message (InMail or connected)',
    color: 'text-blue-600 bg-blue-50',
  },
  email: {
    icon: <Mail className="w-5 h-5" />,
    label: 'Email',
    description: 'Send a personalized email',
    color: 'text-rose-600 bg-rose-50',
  },
  whatsapp: {
    icon: <Phone className="w-5 h-5" />,
    label: 'WhatsApp',
    description: 'Send a WhatsApp message',
    color: 'text-green-600 bg-green-50',
  },
}

// =============================================================================
// COMPONENT
// =============================================================================

export function OutreachOptionsSheet({
  open,
  onOpenChange,
  actionData,
  onComplete,
}: OutreachOptionsSheetProps) {
  const t = useTranslations('luna')
  const { toast } = useToast()
  
  // State
  const [selectedChannel, setSelectedChannel] = useState<OutreachChannel | null>(null)
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [userInput, setUserInput] = useState('')  // User input for customizing message
  const [isGenerating, setIsGenerating] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [copied, setCopied] = useState(false)
  const [outreachId, setOutreachId] = useState<string | null>(null)
  const [userLanguage, setUserLanguage] = useState<string>('en')  // User's output language
  
  // Contact data state
  const [contactData, setContactData] = useState<ContactData | null>(null)
  const [loadingContact, setLoadingContact] = useState(false)
  const [missingFields, setMissingFields] = useState<{
    email?: string
    linkedin_url?: string
    phone?: string
  }>({})
  const [isSavingContact, setIsSavingContact] = useState(false)
  
  // Load contact data when sheet opens
  useEffect(() => {
    if (open && actionData) {
      loadContactData()
    } else {
      setContactData(null)
      setMissingFields({})
    }
  }, [open, actionData])
  
  // Reset state when sheet opens
  useEffect(() => {
    if (open) {
      setSelectedChannel(null)
      setSubject('')
      setBody('')
      setUserInput('')
      setOutreachId(null)
      loadUserLanguage()
    }
  }, [open, actionData])
  
  // Load draft when channel is selected
  useEffect(() => {
    if (open && selectedChannel && actionData) {
      loadDraft()
    }
  }, [selectedChannel, open, actionData])
  
  // Load user's output language
  const loadUserLanguage = async () => {
    try {
      const { data, error } = await api.get<{ output_language?: string }>('/api/v1/settings')
      if (!error && data?.output_language) {
        setUserLanguage(data.output_language)
      }
    } catch (error) {
      console.error('Failed to load user language:', error)
    }
  }
  
  // Load existing draft for this contact and channel
  const loadDraft = async () => {
    if (!actionData?.contactId || !selectedChannel) return
    
    try {
      const { data, error } = await api.get<Array<{
        id: string
        channel: OutreachChannel
        subject?: string
        body: string
        status: string
      }>>(`/api/v1/luna/outreach?contactId=${actionData.contactId}&status=draft`)
      
      if (!error && data && data.length > 0) {
        // Only load draft for the currently selected channel
        const draft = data.find(d => d.channel === selectedChannel)
        
        if (draft) {
          setOutreachId(draft.id)
          setSubject(draft.subject || '')
          setBody(draft.body)
          toast({ 
            title: t('draftLoaded') || 'Draft loaded',
            description: t('draftLoadedDesc') || 'Previous draft has been loaded'
          })
        }
      }
    } catch (error) {
      // Silently fail - no draft is fine
      console.debug('No draft found or error loading draft:', error)
    }
  }
  
  // Load contact data
  const loadContactData = async () => {
    if (!actionData) return
    
    setLoadingContact(true)
    try {
      const { data, error } = await api.get<ContactData>(`/api/v1/contacts/${actionData.contactId}`)
      if (!error && data) {
        setContactData(data)
      }
    } catch (error) {
      console.error('Failed to load contact data:', error)
    } finally {
      setLoadingContact(false)
    }
  }
  
  // Check if required data exists for selected channel
  const getRequiredField = (channel: OutreachChannel): 'email' | 'linkedin_url' | 'phone' | null => {
    switch (channel) {
      case 'email':
        return 'email'
      case 'linkedin_connect':
      case 'linkedin_message':
        return 'linkedin_url'
      case 'whatsapp':
        return 'phone'
      default:
        return null
    }
  }
  
  // Check if channel can be used (has required data)
  const canUseChannel = (channel: OutreachChannel): boolean => {
    if (!contactData) return false
    const requiredField = getRequiredField(channel)
    if (!requiredField) return true
    return !!contactData[requiredField]
  }
  
  // Handle channel selection - check if data is missing
  const handleChannelSelect = (channel: OutreachChannel) => {
    setSelectedChannel(channel)
    const requiredField = getRequiredField(channel)
    if (requiredField && !contactData?.[requiredField]) {
      // Initialize missing field
      setMissingFields(prev => ({
        ...prev,
        [requiredField]: ''
      }))
    } else {
      setMissingFields({})
    }
  }
  
  // Save missing contact information
  const handleSaveContactInfo = async () => {
    if (!actionData || !selectedChannel) return
    
    const requiredField = getRequiredField(selectedChannel)
    if (!requiredField || !missingFields[requiredField]) return
    
    setIsSavingContact(true)
    try {
      const { error } = await api.patch(`/api/v1/contacts/${actionData.contactId}`, {
        [requiredField]: missingFields[requiredField]
      })
      
      if (error) {
        toast({ title: t('saveContactInfoFailed') || 'Failed to save contact info', variant: 'destructive' })
        return
      }
      
      // Update local contact data
      setContactData(prev => prev ? {
        ...prev,
        [requiredField]: missingFields[requiredField]
      } : null)
      
      setMissingFields({})
      toast({ title: t('saveContactInfoSuccess') || 'Contact info saved' })
    } catch (error) {
      console.error('Failed to save contact info:', error)
      toast({ title: t('saveContactInfoFailed') || 'Failed to save contact info', variant: 'destructive' })
    } finally {
      setIsSavingContact(false)
    }
  }
  
  // Available channels from action data
  const availableChannels = actionData?.channels || []
  
  // Generate content
  const handleGenerate = async () => {
    if (!selectedChannel || !actionData) return
    
    setIsGenerating(true)
    try {
      const { data, error } = await api.post<GenerateResponse>(
        '/api/v1/luna/outreach/generate',
        {
          prospectId: actionData.prospectId,
          contactId: actionData.contactId,
          researchId: actionData.researchId,
          channel: selectedChannel,
          language: userLanguage,
          userInput: userInput.trim() || undefined,
        }
      )
      
      if (error) {
        toast({ title: t('generateFailed'), variant: 'destructive' })
        return
      }
      
      if (data) {
        setSubject(data.subject || '')
        setBody(data.body)
        toast({ title: t('generateSuccess') })
        
        // Auto-save draft after generation
        await handleSaveDraftAuto()
      }
    } catch {
      toast({ title: t('generateFailed'), variant: 'destructive' })
    } finally {
      setIsGenerating(false)
    }
  }
  
  // Auto-save draft (silent, no toast)
  const handleSaveDraftAuto = async () => {
    if (!selectedChannel || !actionData || !body) return
    
    try {
      // Check if draft exists for this channel
      const { data: drafts, error: fetchError } = await api.get<Array<{
        id: string
        channel: OutreachChannel
        status: string
      }>>(`/api/v1/luna/outreach?contactId=${actionData.contactId}&status=draft`)
      
      if (!fetchError && drafts && drafts.length > 0) {
        const existingDraft = drafts.find(d => d.channel === selectedChannel)
        
        if (existingDraft) {
          // Update existing draft
          const { error } = await api.patch(
            `/api/v1/luna/outreach/${existingDraft.id}`,
            {
              subject: subject || undefined,
              body,
              channel: selectedChannel,
            }
          )
          
          if (!error) {
            setOutreachId(existingDraft.id)
          }
        } else {
          // Create new draft
          const { data, error } = await api.post<{ id: string }>(
            '/api/v1/luna/outreach',
            {
              prospectId: actionData.prospectId,
              contactId: actionData.contactId,
              researchId: actionData.researchId,
              channel: selectedChannel,
              subject: subject || undefined,
              body,
              status: 'draft',
            }
          )
          
          if (!error && data) {
            setOutreachId(data.id)
          }
        }
      } else {
        // No drafts exist, create new one
        const { data, error } = await api.post<{ id: string }>(
          '/api/v1/luna/outreach',
          {
            prospectId: actionData.prospectId,
            contactId: actionData.contactId,
            researchId: actionData.researchId,
            channel: selectedChannel,
            subject: subject || undefined,
            body,
            status: 'draft',
          }
        )
        
        if (!error && data) {
          setOutreachId(data.id)
        }
      }
    } catch (error) {
      // Silently fail - auto-save shouldn't interrupt user flow
      console.debug('Auto-save draft failed:', error)
    }
  }
  
  // Save as draft
  const handleSaveDraft = async () => {
    if (!selectedChannel || !actionData || !body) return
    
    setIsSaving(true)
    try {
      // If we have an outreach ID, update it; otherwise create new
      if (outreachId) {
        const { error } = await api.patch(
          `/api/v1/luna/outreach/${outreachId}`,
          {
            subject: subject || undefined,
            body,
            channel: selectedChannel,
          }
        )
        
        if (error) {
          toast({ title: t('saveDraftFailed'), variant: 'destructive' })
          return
        }
        
        toast({ title: t('saveDraftSuccess') })
      } else {
        const { data, error } = await api.post<{ id: string }>(
          '/api/v1/luna/outreach',
          {
            prospectId: actionData.prospectId,
            contactId: actionData.contactId,
            researchId: actionData.researchId,
            channel: selectedChannel,
            subject: subject || undefined,
            body,
            status: 'draft',
          }
        )
        
        if (error) {
          toast({ title: t('saveDraftFailed'), variant: 'destructive' })
          return
        }
        
        if (data) {
          setOutreachId(data.id)
          toast({ title: t('saveDraftSuccess') })
        }
      }
    } catch {
      toast({ title: t('saveDraftFailed'), variant: 'destructive' })
    } finally {
      setIsSaving(false)
    }
  }
  
  // Mark as sent
  const handleMarkSent = async () => {
    if (!selectedChannel || !actionData || !body) return
    
    setIsSaving(true)
    try {
      // If we have an outreach ID, update it; otherwise create and mark sent
      if (outreachId) {
        const { error } = await api.patch(
          `/api/v1/luna/outreach/${outreachId}/sent`,
          {}
        )
        
        if (error) {
          toast({ title: t('markSentFailed'), variant: 'destructive' })
          return
        }
      } else {
        const { error } = await api.post(
          '/api/v1/luna/outreach',
          {
            prospectId: actionData.prospectId,
            contactId: actionData.contactId,
            researchId: actionData.researchId,
            channel: selectedChannel,
            subject: subject || undefined,
            body,
            status: 'sent',
          }
        )
        
        if (error) {
          toast({ title: t('markSentFailed'), variant: 'destructive' })
          return
        }
      }
      
      toast({ title: t('markSentSuccess') })
      onOpenChange(false)
      onComplete?.()
    } catch {
      toast({ title: t('markSentFailed'), variant: 'destructive' })
    } finally {
      setIsSaving(false)
    }
  }
  
  // Copy to clipboard
  const handleCopy = async () => {
    const textToCopy = subject ? `${subject}\n\n${body}` : body
    await navigator.clipboard.writeText(textToCopy)
    setCopied(true)
    toast({ title: t('copied') })
    setTimeout(() => setCopied(false), 2000)
  }
  
  // Skip this outreach
  const handleSkip = async () => {
    if (!selectedChannel || !actionData) {
      onOpenChange(false)
      return
    }
    
    setIsSaving(true)
    try {
      await api.post('/api/v1/luna/outreach', {
        prospectId: actionData.prospectId,
        contactId: actionData.contactId,
        channel: selectedChannel || 'other',
        status: 'skipped',
      })
      
      onOpenChange(false)
      onComplete?.()
    } catch {
      onOpenChange(false)
    } finally {
      setIsSaving(false)
    }
  }
  
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{t('outreachTitle')}</SheetTitle>
          <SheetDescription>
            {t('outreachDescription')}
          </SheetDescription>
        </SheetHeader>
        
        <div className="mt-6 space-y-6">
          {/* Step 1: Channel Selection */}
          <div>
            <Label className="text-sm font-medium">{t('selectChannel')}</Label>
            <RadioGroup
              value={selectedChannel || ''}
              onValueChange={(v) => handleChannelSelect(v as OutreachChannel)}
              className="mt-3 grid gap-3"
            >
              {availableChannels.map((channel) => {
                const config = CHANNEL_CONFIG[channel]
                if (!config) return null
                
                return (
                  <label
                    key={channel}
                    className={`
                      flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors
                      ${selectedChannel === channel 
                        ? 'border-primary bg-primary/5' 
                        : 'border-gray-200 hover:border-gray-300'
                      }
                    `}
                  >
                    <RadioGroupItem value={channel} />
                    <div className={`p-2 rounded-lg ${config.color}`}>
                      {config.icon}
                    </div>
                    <div className="flex-1">
                      <div className="font-medium">{config.label}</div>
                      <div className="text-xs text-gray-500">{config.description}</div>
                    </div>
                  </label>
                )
              })}
            </RadioGroup>
          </div>
          
          {/* Step 1.5: Collect Missing Contact Info */}
          {selectedChannel && !canUseChannel(selectedChannel) && (
            <div className="p-4 border border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-800 rounded-lg">
              <Label className="text-sm font-medium text-amber-900 dark:text-amber-200 mb-3 block">
                {t('missingContactInfo') || 'Missing Contact Information'}
              </Label>
              <p className="text-xs text-amber-700 dark:text-amber-300 mb-3">
                {selectedChannel === 'email' && t('addEmailInfo') || 
                 selectedChannel === 'linkedin_connect' || selectedChannel === 'linkedin_message' ? t('addLinkedInInfo') || 'Add LinkedIn URL' :
                 selectedChannel === 'whatsapp' ? t('addPhoneInfo') || 'Add phone number' : ''}
              </p>
              {selectedChannel === 'email' && (
                <div className="space-y-2">
                  <Input
                    type="email"
                    placeholder={t('emailPlaceholder') || 'email@example.com'}
                    value={missingFields.email || ''}
                    onChange={(e) => setMissingFields(prev => ({ ...prev, email: e.target.value }))}
                  />
                  <Button
                    size="sm"
                    onClick={handleSaveContactInfo}
                    disabled={isSavingContact || !missingFields.email}
                    className="w-full"
                  >
                    {isSavingContact ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Check className="w-4 h-4 mr-2" />
                    )}
                    {t('saveContactInfo') || 'Save Email'}
                  </Button>
                </div>
              )}
              {(selectedChannel === 'linkedin_connect' || selectedChannel === 'linkedin_message') && (
                <div className="space-y-2">
                  <Input
                    type="url"
                    placeholder={t('linkedInPlaceholder') || 'https://linkedin.com/in/...'}
                    value={missingFields.linkedin_url || ''}
                    onChange={(e) => setMissingFields(prev => ({ ...prev, linkedin_url: e.target.value }))}
                  />
                  <Button
                    size="sm"
                    onClick={handleSaveContactInfo}
                    disabled={isSavingContact || !missingFields.linkedin_url}
                    className="w-full"
                  >
                    {isSavingContact ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Check className="w-4 h-4 mr-2" />
                    )}
                    {t('saveContactInfo') || 'Save LinkedIn URL'}
                  </Button>
                </div>
              )}
              {selectedChannel === 'whatsapp' && (
                <div className="space-y-2">
                  <Input
                    type="tel"
                    placeholder={t('phonePlaceholder') || '+31 6 12345678'}
                    value={missingFields.phone || ''}
                    onChange={(e) => setMissingFields(prev => ({ ...prev, phone: e.target.value }))}
                  />
                  <Button
                    size="sm"
                    onClick={handleSaveContactInfo}
                    disabled={isSavingContact || !missingFields.phone}
                    className="w-full"
                  >
                    {isSavingContact ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Check className="w-4 h-4 mr-2" />
                    )}
                    {t('saveContactInfo') || 'Save Phone Number'}
                  </Button>
                </div>
              )}
            </div>
          )}
          
          {/* Step 2: User Input (Optional) */}
          {selectedChannel && canUseChannel(selectedChannel) && (
            <div>
              <Label className="text-sm font-medium mb-2 block">
                {t('customInstructions') || 'Custom Instructions (Optional)'}
              </Label>
              <Textarea
                placeholder={t('customInstructionsPlaceholder') || 'E.g., "Focus on their data migration project" or "Mention our Databricks expertise"...'}
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                className="min-h-[80px] text-sm"
              />
              <p className="text-xs text-gray-500 mt-1">
                {t('customInstructionsHint') || 'Add specific instructions to customize the generated message'}
              </p>
            </div>
          )}
          
          {/* Step 3: Generate Content */}
          {selectedChannel && canUseChannel(selectedChannel) && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <Label className="text-sm font-medium">{t('messageContent')}</Label>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleGenerate}
                  disabled={isGenerating || loadingContact}
                >
                  {isGenerating ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Sparkles className="w-4 h-4 mr-2" />
                  )}
                  {t('generate')}
                </Button>
              </div>
              
              {isGenerating ? (
                <div className="space-y-3">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-32 w-full" />
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Subject line (for email) */}
                  {selectedChannel === 'email' && (
                    <div>
                      <Label htmlFor="subject" className="text-xs text-gray-500">
                        {t('subject')}
                      </Label>
                      <input
                        id="subject"
                        type="text"
                        value={subject}
                        onChange={(e) => setSubject(e.target.value)}
                        placeholder={t('subjectPlaceholder')}
                        className="w-full mt-1 px-3 py-2 border rounded-md text-sm"
                      />
                    </div>
                  )}
                  
                  {/* Message body */}
                  <div>
                    <Label htmlFor="body" className="text-xs text-gray-500">
                      {t('message')}
                    </Label>
                    <Textarea
                      id="body"
                      value={body}
                      onChange={(e) => setBody(e.target.value)}
                      placeholder={t('messagePlaceholder')}
                      className="mt-1 min-h-[150px]"
                    />
                  </div>
                </div>
              )}
            </div>
          )}
          
          {/* Step 3: Actions */}
          {selectedChannel && body && (
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopy}
              >
                {copied ? (
                  <Check className="w-4 h-4 mr-2" />
                ) : (
                  <Copy className="w-4 h-4 mr-2" />
                )}
                {t('copy')}
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                onClick={handleSaveDraft}
                disabled={isSaving}
              >
                <Save className="w-4 h-4 mr-2" />
                {t('saveDraft')}
              </Button>
              
              <Button
                size="sm"
                onClick={handleMarkSent}
                disabled={isSaving}
              >
                {isSaving ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Send className="w-4 h-4 mr-2" />
                )}
                {t('markAsSent')}
              </Button>
            </div>
          )}
        </div>
        
        <SheetFooter className="mt-6">
          <Button variant="ghost" onClick={handleSkip} disabled={isSaving}>
            {t('skip')}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
