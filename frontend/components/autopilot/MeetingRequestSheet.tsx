'use client'

/**
 * Meeting Request Sheet Component
 * SPEC-045 / TASK-048
 *
 * Inline sheet for planning a meeting from Autopilot.
 * Shows:
 * - Contact information with quick actions
 * - AI-generated meeting request email
 * - Calendar quick actions (Google, Outlook)
 * - Prep highlights
 * - Completion button
 */

import React, { useState, useEffect, useCallback } from 'react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Mail,
  Phone,
  Linkedin,
  Copy,
  ExternalLink,
  Calendar,
  CheckCircle2,
  ChevronDown,
  User,
  FileText,
  RefreshCw,
  Loader2,
} from 'lucide-react'
import { useToast } from '@/components/ui/use-toast'
import { api } from '@/lib/api'
import type { ProspectContact, MeetingPrep } from '@/types'

interface MeetingRequestSheetProps {
  prospectId: string
  prepId: string
  companyName: string
  onComplete: () => void
  onCancel: () => void
}

interface ContactCardProps {
  contact: ProspectContact
  onCopyEmail: (email: string) => void
}

function ContactCard({ contact, onCopyEmail }: ContactCardProps) {
  const t = useTranslations('autopilot.meetingRequest')

  const handleOpenLinkedIn = () => {
    if (contact.linkedin_url) {
      window.open(contact.linkedin_url, '_blank')
    }
  }

  const handleOpenEmail = () => {
    if (contact.email) {
      window.location.href = `mailto:${contact.email}`
    }
  }

  const handleCall = () => {
    if (contact.phone) {
      window.location.href = `tel:${contact.phone}`
    }
  }

  const decisionBadgeColor = {
    decision_maker: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    influencer: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    gatekeeper: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    end_user: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400',
  }

  return (
    <Card className="p-4 border border-slate-200 dark:border-slate-700">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
            <User className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-slate-900 dark:text-white">
                {contact.name}
              </span>
              {contact.decision_authority && (
                <Badge className={`text-xs ${decisionBadgeColor[contact.decision_authority]}`}>
                  {contact.decision_authority === 'decision_maker' && '⭐ Decision Maker'}
                  {contact.decision_authority === 'influencer' && 'Influencer'}
                  {contact.decision_authority === 'gatekeeper' && 'Gatekeeper'}
                  {contact.decision_authority === 'end_user' && 'End User'}
                </Badge>
              )}
            </div>
            {contact.role && (
              <p className="text-sm text-slate-500 dark:text-slate-400">{contact.role}</p>
            )}

            <div className="mt-2 space-y-1">
              {contact.email && (
                <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <Mail className="w-3.5 h-3.5" />
                  <span>{contact.email}</span>
                </div>
              )}
              {contact.phone && (
                <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <Phone className="w-3.5 h-3.5" />
                  <span>{contact.phone}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-slate-100 dark:border-slate-700">
        {contact.email && (
          <>
            <Button
              size="sm"
              variant="outline"
              className="text-xs h-7"
              onClick={() => onCopyEmail(contact.email!)}
            >
              <Copy className="w-3 h-3 mr-1" />
              {t('copyEmail') || 'Kopieer'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="text-xs h-7"
              onClick={handleOpenEmail}
            >
              <Mail className="w-3 h-3 mr-1" />
              {t('openEmail') || 'Email'}
            </Button>
          </>
        )}
        {contact.phone && (
          <Button
            size="sm"
            variant="outline"
            className="text-xs h-7"
            onClick={handleCall}
          >
            <Phone className="w-3 h-3 mr-1" />
            {t('call') || 'Bel'}
          </Button>
        )}
        {contact.linkedin_url && (
          <Button
            size="sm"
            variant="outline"
            className="text-xs h-7"
            onClick={handleOpenLinkedIn}
          >
            <Linkedin className="w-3 h-3 mr-1" />
            LinkedIn
          </Button>
        )}
      </div>
    </Card>
  )
}

export function MeetingRequestSheet({
  prospectId,
  prepId,
  companyName,
  onComplete,
  onCancel,
}: MeetingRequestSheetProps) {
  const t = useTranslations('autopilot.meetingRequest')
  const { toast } = useToast()

  // State
  const [contacts, setContacts] = useState<ProspectContact[]>([])
  const [prep, setPrep] = useState<MeetingPrep | null>(null)
  const [emailContent, setEmailContent] = useState('')
  const [selectedContact, setSelectedContact] = useState<ProspectContact | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isGeneratingEmail, setIsGeneratingEmail] = useState(false)
  const [prepExpanded, setPrepExpanded] = useState(false)

  // Load contacts and prep
  const loadData = useCallback(async () => {
    setIsLoading(true)
    try {
      // Load contacts and prep in parallel
      const [contactsResult, prepResult] = await Promise.all([
        api.get<{ contacts: ProspectContact[] }>(`/api/v1/prospects/${prospectId}/contacts`),
        api.get<MeetingPrep>(`/api/v1/preparation/${prepId}`),
      ])

      if (!contactsResult.error && contactsResult.data) {
        const loadedContacts = contactsResult.data.contacts || []
        setContacts(loadedContacts)
        // Auto-select first decision maker or first contact
        const decisionMaker = loadedContacts.find(c => c.decision_authority === 'decision_maker')
        setSelectedContact(decisionMaker || loadedContacts[0] || null)
      }

      if (!prepResult.error && prepResult.data) {
        setPrep(prepResult.data)
      }
    } catch (err) {
      console.error('Failed to load data:', err)
    } finally {
      setIsLoading(false)
    }
  }, [prospectId, prepId])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Generate email template when contact is selected
  useEffect(() => {
    if (selectedContact) {
      generateEmailTemplate(selectedContact)
    }
  }, [selectedContact])

  const generateEmailTemplate = async (contact: ProspectContact) => {
    setIsGeneratingEmail(true)

    // For now, generate a simple template locally
    // Could be replaced with AI-generated email via backend
    const firstName = contact.name.split(' ')[0]
    const template = `Beste ${firstName},

Ik heb mij verdiept in ${companyName} en zie interessante raakvlakken met onze oplossingen.

Zou je volgende week tijd hebben voor een kort kennismakingsgesprek van 30 minuten?

Ik ben beschikbaar op:
- [Dag 1] [Tijd]
- [Dag 2] [Tijd]

Met vriendelijke groet,
[Jouw naam]`

    setEmailContent(template)
    setIsGeneratingEmail(false)
  }

  const regenerateEmail = () => {
    if (selectedContact) {
      generateEmailTemplate(selectedContact)
    }
  }

  const handleCopyEmail = (email: string) => {
    navigator.clipboard.writeText(email)
    toast({
      title: t('emailCopied') || 'Email gekopieerd',
      description: email,
    })
  }

  const handleCopyTemplate = () => {
    navigator.clipboard.writeText(emailContent)
    toast({
      title: t('templateCopied') || 'Email template gekopieerd',
      description: t('pasteInEmail') || 'Plak in je email client',
    })
  }

  const handleOpenMailto = () => {
    if (selectedContact?.email) {
      const subject = encodeURIComponent(`Kennismaking - ${companyName}`)
      const body = encodeURIComponent(emailContent)
      window.location.href = `mailto:${selectedContact.email}?subject=${subject}&body=${body}`
    }
  }

  const handleOpenGoogleCalendar = () => {
    const title = encodeURIComponent(`Meeting - ${companyName}`)
    const details = encodeURIComponent(`Gesprek met ${selectedContact?.name || 'contact'} van ${companyName}`)
    const duration = 30 // minutes
    const now = new Date()
    const nextWeek = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)
    nextWeek.setHours(10, 0, 0, 0)

    const startDate = nextWeek.toISOString().replace(/-|:|\.\d\d\d/g, '')
    const endDate = new Date(nextWeek.getTime() + duration * 60 * 1000).toISOString().replace(/-|:|\.\d\d\d/g, '')

    const url = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${title}&details=${details}&dates=${startDate}/${endDate}`
    window.open(url, '_blank')
  }

  const handleOpenOutlookCalendar = () => {
    const title = encodeURIComponent(`Meeting - ${companyName}`)
    const details = encodeURIComponent(`Gesprek met ${selectedContact?.name || 'contact'} van ${companyName}`)

    const url = `https://outlook.office.com/calendar/0/deeplink/compose?subject=${title}&body=${details}&startdt=&enddt=`
    window.open(url, '_blank')
  }

  const handleComplete = () => {
    toast({
      title: t('meetingPlanned') || 'Meeting gepland!',
      description: t('proposalCompleted') || 'Het voorstel is afgerond.',
    })
    onComplete()
  }

  // Extract prep highlights from brief_content
  const getPrepHighlights = (): string[] => {
    if (!prep?.brief_content) return []

    // Try to extract key points from the prep content
    const content = prep.brief_content
    const lines = content.split('\n').filter(line => line.trim())

    // Get first few meaningful lines
    const highlights = lines
      .filter(line => !line.startsWith('#') && line.length > 20)
      .slice(0, 3)
      .map(line => line.replace(/^\*\s*/, '').replace(/\*\*/g, '').trim())

    return highlights
  }

  if (isLoading) {
    return (
      <div className="space-y-4 p-4">
        <Skeleton className="h-8 w-3/4" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Section 1: Contacts */}
      <div>
        <h3 className="text-sm font-medium text-slate-900 dark:text-white mb-3 flex items-center gap-2">
          <User className="w-4 h-4" />
          {t('contacts') || 'Contactpersonen'}
        </h3>

        {contacts.length === 0 ? (
          <Card className="p-4 bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800">
            <p className="text-sm text-amber-700 dark:text-amber-300">
              {t('noContacts') || 'Geen contactpersonen gevonden. Voeg eerst een contact toe.'}
            </p>
          </Card>
        ) : (
          <div className="space-y-3">
            {contacts.slice(0, 3).map((contact) => (
              <div
                key={contact.id}
                className={`cursor-pointer transition-all ${selectedContact?.id === contact.id ? 'ring-2 ring-indigo-500 rounded-lg' : ''
                  }`}
                onClick={() => setSelectedContact(contact)}
              >
                <ContactCard contact={contact} onCopyEmail={handleCopyEmail} />
              </div>
            ))}
            {contacts.length > 3 && (
              <p className="text-xs text-slate-500 dark:text-slate-400 text-center">
                +{contacts.length - 3} {t('moreContacts') || 'meer contacten'}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Section 2: Email Template */}
      {selectedContact && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-slate-900 dark:text-white flex items-center gap-2">
              <Mail className="w-4 h-4" />
              {t('emailTemplate') || 'Meeting uitnodiging'}
            </h3>
            <Button
              size="sm"
              variant="ghost"
              className="text-xs h-7"
              onClick={regenerateEmail}
              disabled={isGeneratingEmail}
            >
              {isGeneratingEmail ? (
                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
              ) : (
                <RefreshCw className="w-3 h-3 mr-1" />
              )}
              {t('regenerate') || 'Hergenereer'}
            </Button>
          </div>

          <div className="space-y-2">
            <div className="text-xs text-slate-500 dark:text-slate-400">
              {t('to') || 'Aan'}: {selectedContact.name} ({selectedContact.email || 'geen email'})
            </div>
            <Textarea
              value={emailContent}
              onChange={(e) => setEmailContent(e.target.value)}
              className="min-h-[200px] text-sm font-mono"
            />
          </div>

          <div className="flex flex-wrap gap-2 mt-3">
            <Button
              size="sm"
              variant="outline"
              onClick={handleCopyTemplate}
            >
              <Copy className="w-4 h-4 mr-1" />
              {t('copyTemplate') || 'Kopieer tekst'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={handleOpenMailto}
              disabled={!selectedContact.email}
            >
              <Mail className="w-4 h-4 mr-1" />
              {t('openInEmail') || 'Open in email'}
            </Button>
          </div>
        </div>
      )}

      {/* Section 3: Calendar Actions */}
      <div>
        <h3 className="text-sm font-medium text-slate-900 dark:text-white mb-3 flex items-center gap-2">
          <Calendar className="w-4 h-4" />
          {t('planInCalendar') || 'Plan in je agenda'}
        </h3>

        <div className="grid grid-cols-2 gap-3">
          <Button
            variant="outline"
            className="justify-start"
            onClick={handleOpenGoogleCalendar}
          >
            <div className="w-5 h-5 mr-2 flex items-center justify-center">
              <svg viewBox="0 0 24 24" className="w-4 h-4">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
            </div>
            Google Calendar
            <ExternalLink className="w-3 h-3 ml-auto" />
          </Button>

          <Button
            variant="outline"
            className="justify-start"
            onClick={handleOpenOutlookCalendar}
          >
            <div className="w-5 h-5 mr-2 flex items-center justify-center">
              <svg viewBox="0 0 24 24" className="w-4 h-4">
                <path fill="#0078D4" d="M24 7.387v10.478c0 .23-.08.424-.238.576-.158.152-.353.228-.582.228h-8.547v-6.036l1.238.96c.088.064.19.096.307.096.116 0 .22-.032.307-.096l7.515-5.828v-.378z" />
                <path fill="#0078D4" d="M24 5.39v.844l-8.11 6.29-7.89-6.133V5.39c0-.23.08-.424.238-.576.158-.152.353-.228.582-.228h14.598c.23 0 .424.076.582.228z" />
                <path fill="#0364B8" d="M0 7.66v9.063c0 .207.077.385.23.534.153.148.338.223.555.223h7.432V6.903H.785c-.217 0-.402.074-.555.223-.153.148-.23.327-.23.534z" />
              </svg>
            </div>
            Outlook
            <ExternalLink className="w-3 h-3 ml-auto" />
          </Button>
        </div>
      </div>

      {/* Section 4: Prep Highlights (Toggle) */}
      {prep && (
        <div>
          <Button 
            variant="ghost" 
            className="w-full justify-between p-3 h-auto"
            onClick={() => setPrepExpanded(!prepExpanded)}
          >
            <span className="flex items-center gap-2 text-sm font-medium text-slate-900 dark:text-white">
              <FileText className="w-4 h-4" />
              {t('prepHighlights') || 'Prep highlights'}
            </span>
            <ChevronDown className={`w-4 h-4 transition-transform ${prepExpanded ? 'rotate-180' : ''}`} />
          </Button>
          {prepExpanded && (
            <Card className="p-4 mt-2 bg-slate-50 dark:bg-slate-800/50">
              <ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
                {getPrepHighlights().map((highlight, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-indigo-500">•</span>
                    {highlight}
                  </li>
                ))}
              </ul>
              <Button
                size="sm"
                variant="link"
                className="mt-3 p-0 h-auto text-indigo-600 dark:text-indigo-400"
                onClick={() => window.open(`/dashboard/preparation/${prepId}`, '_blank')}
              >
                {t('viewFullPrep') || 'Bekijk volledige prep'}
                <ExternalLink className="w-3 h-3 ml-1" />
              </Button>
            </Card>
          )}
        </div>
      )}

      {/* Section 5: Complete Button */}
      <div className="pt-4 border-t border-slate-200 dark:border-slate-700">
        <Button
          className="w-full bg-green-600 hover:bg-green-700 text-white"
          onClick={handleComplete}
        >
          <CheckCircle2 className="w-4 h-4 mr-2" />
          {t('meetingPlannedButton') || 'Meeting gepland - Markeer als afgerond'}
        </Button>

        <div className="flex justify-between mt-3">
          <Button variant="ghost" size="sm" onClick={onCancel}>
            {t('cancel') || 'Annuleren'}
          </Button>
        </div>
      </div>
    </div>
  )
}
