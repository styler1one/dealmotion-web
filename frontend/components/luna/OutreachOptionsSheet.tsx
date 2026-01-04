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
  const [isGenerating, setIsGenerating] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [copied, setCopied] = useState(false)
  const [outreachId, setOutreachId] = useState<string | null>(null)
  
  // Reset state when sheet opens
  useEffect(() => {
    if (open) {
      setSelectedChannel(null)
      setSubject('')
      setBody('')
      setOutreachId(null)
    }
  }, [open])
  
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
      }
    } catch {
      toast({ title: t('generateFailed'), variant: 'destructive' })
    } finally {
      setIsGenerating(false)
    }
  }
  
  // Save as draft
  const handleSaveDraft = async () => {
    if (!selectedChannel || !actionData || !body) return
    
    setIsSaving(true)
    try {
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
              onValueChange={(v) => setSelectedChannel(v as OutreachChannel)}
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
          
          {/* Step 2: Generate Content */}
          {selectedChannel && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <Label className="text-sm font-medium">{t('messageContent')}</Label>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleGenerate}
                  disabled={isGenerating}
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
