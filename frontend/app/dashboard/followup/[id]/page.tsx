'use client'

import { useState, useEffect, useCallback, useMemo, startTransition } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { Toaster } from '@/components/ui/toaster'
import { DashboardLayout } from '@/components/layout/dashboard-layout'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { MarkdownEditor } from '@/components/markdown-editor'
import { useTranslations } from 'next-intl'
import { api } from '@/lib/api'
import { logger } from '@/lib/logger'

// Note: We use multiple translation namespaces for reusable strings
import { exportAsMarkdown, exportAsPdf, exportAsDocx } from '@/lib/export-utils'
import { ActionsGrid } from '@/components/followup/action-card'
import { ActionPanel } from '@/components/followup/action-panel'
import { ACTION_TYPES, type FollowupAction, type ActionType, type ActionsListResponse } from '@/types/followup-actions'
import type { User } from '@supabase/supabase-js'

interface Followup {
  id: string
  organization_id: string
  user_id: string
  meeting_prep_id: string | null
  prospect_id: string | null
  audio_url: string | null
  audio_filename: string | null
  audio_duration_seconds: number | null
  transcription_text: string | null
  transcription_segments: Array<{ speaker: string; start: number; end: number; text: string }>
  speaker_count: number
  executive_summary: string | null
  key_points: string[]
  concerns: string[]
  decisions: string[]
  next_steps: string[]
  action_items: Array<{ task: string; assignee: string; due_date: string | null; priority: string }>
  email_draft: string | null
  email_tone: string
  meeting_date: string | null
  prospect_company_name: string | null
  meeting_subject: string | null
  status: string
  error_message: string | null
  created_at: string
  completed_at: string | null
  include_coaching: boolean
  contact_ids?: string[]
  commercial_signals: {
    koopsignalen: string[]
    cross_sell: string[]
    risks: string[]
  } | null
  observations: {
    doubts: string[]
    unspoken_needs: string[]
    opportunities: string[]
    red_flags: string[]
  } | null
  coaching_feedback: {
    strengths: string[]
    improvements: string[]
    tips: string[]
  } | null
  full_summary_content: string | null
  deal_id?: string
}

interface ProspectContact {
  id: string
  name: string
  role?: string
  communication_style?: string
  decision_authority?: string
}

interface ResearchBrief {
  id: string
  company_name: string
  status: string
  completed_at?: string
}

interface MeetingPrep {
  id: string
  prospect_company_name: string
  meeting_type: string
  status: string
  completed_at?: string
}

interface LinkedDeal {
  id: string
  name: string
  prospect_id: string
  is_active: boolean
}

export default function FollowupDetailPage() {
  const router = useRouter()
  const params = useParams()
  const followupId = params.id as string
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const t = useTranslations('followup')
  const tCommon = useTranslations('common')
  
  const [user, setUser] = useState<User | null>(null)
  const [followup, setFollowup] = useState<Followup | null>(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState<string | null>(null)
  const [showTranscript, setShowTranscript] = useState(false)
  const [researchBrief, setResearchBrief] = useState<ResearchBrief | null>(null)
  const [meetingPrep, setMeetingPrep] = useState<MeetingPrep | null>(null)
  const [linkedContacts, setLinkedContacts] = useState<ProspectContact[]>([])
  const [linkedDeal, setLinkedDeal] = useState<LinkedDeal | null>(null)
  
  // Edit summary states
  const [isEditingSummary, setIsEditingSummary] = useState(false)
  const [editedSummary, setEditedSummary] = useState('')
  const [isSavingSummary, setIsSavingSummary] = useState(false)
  
  // Export states
  const [isExporting, setIsExporting] = useState(false)
  
  // Actions states
  const [actions, setActions] = useState<FollowupAction[]>([])
  const [generatingActionType, setGeneratingActionType] = useState<ActionType | null>(null)
  const [selectedAction, setSelectedAction] = useState<FollowupAction | null>(null)

  useEffect(() => {
    // Get user for display purposes (non-blocking)
    supabase.auth.getUser().then(({ data: { user } }) => {
      setUser(user)
    })
  }, [supabase])

  const fetchFollowup = useCallback(async () => {
    try {
      // Note: api client handles authentication automatically
      const { data, error } = await api.get<Followup>(`/api/v1/followup/${followupId}`)

      if (!error && data) {
        setFollowup(data)
        
        // Fetch related data in PARALLEL (research, prep, contacts, deal)
        await Promise.all([
          data.prospect_company_name && fetchRelatedData(data.prospect_company_name),
          data.contact_ids && data.contact_ids.length > 0 && fetchLinkedContacts(data.contact_ids),
          data.deal_id && fetchLinkedDeal(data.deal_id)
        ].filter(Boolean))
      } else {
        toast({ title: t('toast.failed'), variant: 'destructive' })
        router.push('/dashboard/followup')
      }
    } catch (error) {
      logger.error('Error fetching followup', error, { source: 'FollowupDetailPage' })
    } finally {
      setLoading(false)
    }
  }, [followupId, supabase, router, toast])

  const fetchRelatedData = async (companyName: string) => {
    try {
      // Fetch research briefs and preps in parallel
      const [researchRes, prepRes] = await Promise.all([
        api.get<{ briefs: ResearchBrief[] }>('/api/v1/research/briefs'),
        api.get<{ preps: MeetingPrep[] }>('/api/v1/prep/briefs')
      ])

      if (!researchRes.error && researchRes.data) {
        const brief = researchRes.data.briefs?.find((b) => 
          b.company_name.toLowerCase() === companyName.toLowerCase()
        )
        if (brief) setResearchBrief(brief)
      }

      if (!prepRes.error && prepRes.data) {
        const prep = prepRes.data.preps?.find((p) => 
          p.prospect_company_name.toLowerCase() === companyName.toLowerCase()
        )
        if (prep) setMeetingPrep(prep)
      }
    } catch (error) {
      logger.error('Error fetching related data', error, { source: 'FollowupDetailPage' })
    }
  }

  const fetchLinkedContacts = async (contactIds: string[]) => {
    if (!contactIds || contactIds.length === 0) return
    
    try {
      const { data, error } = await api.get<{ contacts: ProspectContact[]; count: number }>(`/api/v1/contacts?ids=${contactIds.join(',')}`)

      if (!error && data) {
        setLinkedContacts(data.contacts || [])
      }
    } catch (error) {
      logger.error('Failed to fetch linked contacts', error, { source: 'FollowupDetailPage' })
    }
  }

  const fetchLinkedDeal = async (dealId: string) => {
    try {
      const { data, error } = await supabase
        .from('deals')
        .select('id, name, prospect_id, is_active')
        .eq('id', dealId)
        .single()

      if (!error && data) {
        setLinkedDeal(data)
      }
    } catch (error) {
      logger.error('Failed to fetch linked deal', error, { source: 'FollowupDetailPage' })
    }
  }

  // Fetch actions for this followup
  const fetchActions = useCallback(async (): Promise<FollowupAction[] | null> => {
    try {
      const { data, error } = await api.get<ActionsListResponse>(`/api/v1/followup/${followupId}/actions`)
      if (!error && data) {
        // Use startTransition to prevent blocking navigation
        startTransition(() => {
          setActions(data.actions || [])
        })
        return data.actions || []
      }
      return null
    } catch (error) {
      logger.error('Failed to fetch actions', error, { source: 'FollowupDetailPage' })
      return null
    }
  }, [followupId])

  // Auto-refresh for generating actions (polling)
  // IMPORTANT: Keep this simple like Research page - NO async in setInterval callback!
  useEffect(() => {
    const hasGeneratingActions = actions.some(a => 
      !a.content && a.metadata?.status !== 'error'
    )

    if (hasGeneratingActions || generatingActionType) {
      const interval = setInterval(() => {
        // Simple call, no await - matches Research page pattern
        fetchActions()
      }, 5000)

      return () => clearInterval(interval)
    }
  }, [actions, generatingActionType, fetchActions])
  
  // Separate effect to handle completion detection - runs when actions state changes
  useEffect(() => {
    if (!generatingActionType) return
    
    const targetAction = actions.find(a => a.action_type === generatingActionType)
    if (targetAction && (targetAction.content || targetAction.metadata?.status === 'error')) {
      // Action is complete or errored - use startTransition to not block navigation
      startTransition(() => {
        setGeneratingActionType(null)
      })
      
      // Show completion toast
      if (targetAction.content) {
        toast({
          title: t('actions.generated'),
          description: t('actions.generatedDesc', { 
            actionType: t(`actions.types.${generatingActionType}.label`)
          }),
        })
      }
    }
  }, [actions, generatingActionType, toast, t])
  
  // Keep selectedAction in sync with actions array (for live updates after regeneration)
  useEffect(() => {
    if (selectedAction && selectedAction.id !== 'summary-builtin') {
      const updatedAction = actions.find(a => a.id === selectedAction.id)
      if (updatedAction && updatedAction.content !== selectedAction.content) {
        setSelectedAction(updatedAction)
      }
    }
  }, [actions, selectedAction])

  // Generate a new action - fire-and-forget pattern
  const handleGenerateAction = async (actionType: ActionType) => {
    // Summary is built-in, not generated via API
    if (actionType === 'summary') {
      const summaryAction = buildSummaryAction()
      if (summaryAction) {
        setSelectedAction(summaryAction)
      }
      return
    }
    
    // Set generating state for UI feedback (will be cleared by polling when done)
    // Use startTransition to prevent blocking navigation
    startTransition(() => {
      setGeneratingActionType(actionType)
    })
    
    try {
      const { data, error } = await api.post<FollowupAction>(`/api/v1/followup/${followupId}/actions`, {
        action_type: actionType,
        regenerate: false,
      })
      
      if (error) {
        throw new Error(error.message || 'Generation failed')
      }
      
      if (data) {
        // Add the new action (with pending status initially)
        startTransition(() => {
          setActions(prev => [...prev.filter(a => a.action_type !== actionType), data])
        })
      }
      
      // Show feedback - generation runs in background, polling will pick up completion
      toast({ 
        title: t('actions.generating'),
        description: t('actions.generatingDesc', { actionType: t(`actions.types.${actionType}.label`) }),
      })
      
      // NOTE: Don't await fetchActions() here - let polling handle it
      // This prevents blocking the UI while waiting for refresh
      
    } catch (error) {
      logger.error('Failed to generate action', error, { source: 'FollowupDetailPage' })
      
      // Check if it's an "already exists" error - refresh to show existing action
      const errorMessage = error instanceof Error ? error.message : ''
      if (errorMessage.includes('already exists')) {
        toast({ 
          title: t('actions.alreadyExists'),
          description: t('actions.alreadyExistsDesc'),
        })
        // Refresh actions to show the existing one
        fetchActions()
      } else {
        toast({ title: t('actions.generationFailed'), variant: 'destructive' })
      }
      
      startTransition(() => {
        setGeneratingActionType(null)
      })
    }
  }

  // Update action content (edit)
  const handleUpdateAction = async (actionId: string, content: string) => {
    // Summary is built-in and not editable via API
    if (actionId === 'summary-builtin') {
      toast({ title: t('actions.summaryCannotEdit'), variant: 'destructive' })
      return
    }
    
    const { data, error } = await api.patch<FollowupAction>(
      `/api/v1/followup/${followupId}/actions/${actionId}`,
      { content }
    )
    
    if (!error && data) {
      setActions(prev => prev.map(a => a.id === actionId ? data : a))
    } else {
      throw new Error('Failed to update action')
    }
  }

  // Delete action
  const handleDeleteAction = async (actionId: string) => {
    // Summary is built-in and cannot be deleted
    if (actionId === 'summary-builtin') {
      toast({ title: t('actions.summaryCannotDelete'), variant: 'destructive' })
      return
    }
    
    const { error } = await api.delete(`/api/v1/followup/${followupId}/actions/${actionId}`)
    
    if (!error) {
      startTransition(() => {
        setActions(prev => prev.filter(a => a.id !== actionId))
      })
    } else {
      throw new Error('Failed to delete action')
    }
  }

  // Regenerate action - TRULY fire-and-forget using Web API directly
  // This bypasses React completely to ensure navigation is never blocked
  const handleRegenerateAction = (actionId: string) => {
    // Summary is built-in and cannot be regenerated
    if (actionId === 'summary-builtin') {
      toast({ title: t('actions.summaryCannotRegenerate'), variant: 'destructive' })
      return
    }
    
    const action = actions.find(a => a.id === actionId)
    if (!action) return
    
    // Update UI immediately - use startTransition to not block navigation
    startTransition(() => {
      setActions(prev => prev.filter(a => a.id !== actionId))
      setGeneratingActionType(action.action_type)
    })
    
    // Show feedback immediately
    toast({ 
      title: t('actions.regenerating'),
      description: t('actions.regeneratingDesc'),
    })
    
    // Use native fetch directly (NOT the api client) to completely bypass
    // any React-related code. Get token once, then fire-and-forget.
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    
    // Get auth token synchronously from Supabase storage (no async needed)
    const supabaseKey = Object.keys(localStorage).find(k => k.startsWith('sb-') && k.endsWith('-auth-token'))
    const authData = supabaseKey ? JSON.parse(localStorage.getItem(supabaseKey) || '{}') : {}
    const token = authData?.access_token || ''
    
    // Fire DELETE then POST using native fetch - completely outside React
    // Use requestIdleCallback or setTimeout to push to next frame
    if (typeof requestIdleCallback !== 'undefined') {
      requestIdleCallback(() => {
        fireRegenerateRequests(apiBase, token, followupId, actionId, action.action_type)
      })
    } else {
      setTimeout(() => {
        fireRegenerateRequests(apiBase, token, followupId, actionId, action.action_type)
      }, 0)
    }
  }
  
  // Helper function that runs completely outside React lifecycle
  function fireRegenerateRequests(apiBase: string, token: string, followupId: string, actionId: string, actionType: string) {
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    }
    
    // Delete existing action
    fetch(`${apiBase}/api/v1/followup/${followupId}/actions/${actionId}`, {
      method: 'DELETE',
      headers,
    }).then(() => {
      // Generate new one
      return fetch(`${apiBase}/api/v1/followup/${followupId}/actions`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          action_type: actionType,
          regenerate: false,
        }),
      })
    }).then(response => {
      if (!response.ok) {
        logger.error('Regeneration failed', { status: response.status }, { source: 'FollowupDetailPage' })
      }
      // Don't update React state - let polling handle it
    }).catch(error => {
      logger.error('Regeneration error', error, { source: 'FollowupDetailPage' })
    })
  }

  // View action - shows inline panel
  const handleViewAction = (action: FollowupAction) => {
    setSelectedAction(action)
  }

  useEffect(() => {
    fetchFollowup()
    
    const interval = setInterval(() => {
      if (followup && ['uploading', 'transcribing', 'summarizing'].includes(followup.status)) {
        fetchFollowup()
      }
    }, 5000)
    
    return () => clearInterval(interval)
  }, [fetchFollowup, followup?.status])

  // Fetch actions when followup is completed
  useEffect(() => {
    if (followup?.status === 'completed') {
      fetchActions()
    }
  }, [followup?.status, fetchActions])

  // Build summary action from followup data (special handling - not from API)
  const buildSummaryAction = useCallback((): FollowupAction | null => {
    // Prefer full_summary_content (new format) over parsed fields (legacy)
    if (!followup?.full_summary_content && !followup?.executive_summary) return null
    
    let content: string
    
    if (followup.full_summary_content) {
      // New format: use the full markdown content directly
      content = followup.full_summary_content
    } else {
      // Legacy fallback: build from parsed fields
      content = `## Summary\n\n${followup.executive_summary}\n\n`
      
      if (followup.key_points?.length) {
        content += `## Key Points\n\n${followup.key_points.map(p => `- ${p}`).join('\n')}\n\n`
      }
      
      if (followup.decisions?.length) {
        content += `## Decisions\n\n${followup.decisions.map(d => `- ${d}`).join('\n')}\n\n`
      }
      
      if (followup.next_steps?.length) {
        content += `## Next Steps\n\n${followup.next_steps.map(s => `- ${s}`).join('\n')}\n\n`
      }
      
      if (followup.concerns?.length) {
        content += `## Concerns\n\n${followup.concerns.map(c => `- ${c}`).join('\n')}\n\n`
      }
      
      if (followup.action_items?.length) {
        content += `## Action Items\n\n`
        content += followup.action_items.map(item => 
          `- **${item.task}** (${item.assignee}${item.due_date ? `, ${item.due_date}` : ''})`
        ).join('\n')
      }
    }
    
    return {
      id: 'summary-builtin',
      followup_id: followup.id,
      action_type: 'summary',
      content,
      metadata: { status: 'completed' },
      language: 'en',
      created_at: followup.created_at,
      updated_at: followup.completed_at || followup.created_at,
      icon: '📋',
      label: 'Summary',
      description: 'Meeting summary with key points and next steps',
      word_count: content.split(/\s+/).length,
    }
  }, [followup])

  // Combine built-in summary with API actions
  const allActions = useMemo(() => {
    const summaryAction = buildSummaryAction()
    if (summaryAction) {
      // Filter out any API summary action (shouldn't exist, but just in case)
      const apiActions = actions.filter(a => a.action_type !== 'summary')
      return [summaryAction, ...apiActions]
    }
    return actions
  }, [buildSummaryAction, actions])

  const handleCopy = async (text: string, type: string) => {
    await navigator.clipboard.writeText(text)
    setCopied(type)
    toast({ title: t('toast.copied') })
    setTimeout(() => setCopied(null), 2000)
  }

  // Start editing the summary
  const handleStartEditSummary = () => {
    if (followup?.executive_summary) {
      setEditedSummary(followup.executive_summary)
      setIsEditingSummary(true)
    }
  }

  // Cancel editing
  const handleCancelEditSummary = () => {
    setIsEditingSummary(false)
    setEditedSummary('')
  }

  // Save edited summary
  const handleSaveSummary = async () => {
    if (!followup || !editedSummary.trim()) return
    
    setIsSavingSummary(true)
    try {
      const { data, error } = await api.patch<Followup>(
        `/api/v1/followup/${followupId}`,
        { executive_summary: editedSummary }
      )
      
      if (error) {
        toast({
          title: t('detail.saveFailed'),
          description: t('detail.saveFailedDesc'),
          variant: 'destructive'
        })
        return
      }
      
      // Update local state
      setFollowup({ ...followup, executive_summary: editedSummary })
      setIsEditingSummary(false)
      setEditedSummary('')
      
      toast({
        title: t('detail.saved'),
        description: t('detail.savedDesc')
      })
    } catch (err) {
      logger.error('Error saving summary', err, { source: 'FollowupDetailPage' })
      toast({
        title: t('detail.saveFailed'),
        description: t('detail.saveFailedDesc'),
        variant: 'destructive'
      })
    } finally {
      setIsSavingSummary(false)
    }
  }

  // Build export content from all followup data
  const buildExportContent = () => {
    if (!followup) return ''
    
    let content = `# Meeting Follow-up: ${followup.prospect_company_name || followup.meeting_subject || 'Meeting'}\n\n`
    
    if (followup.meeting_date) {
      content += `**Date:** ${new Date(followup.meeting_date).toLocaleDateString()}\n\n`
    }
    
    if (followup.executive_summary) {
      content += `## Executive Summary\n\n${followup.executive_summary}\n\n`
    }
    
    if (followup.key_points?.length > 0) {
      content += `## Key Points\n\n${followup.key_points.map(p => `- ${p}`).join('\n')}\n\n`
    }
    
    if (followup.decisions?.length > 0) {
      content += `## Decisions\n\n${followup.decisions.map(d => `- ${d}`).join('\n')}\n\n`
    }
    
    if (followup.next_steps?.length > 0) {
      content += `## Next Steps\n\n${followup.next_steps.map(s => `- ${s}`).join('\n')}\n\n`
    }
    
    if (followup.action_items?.length > 0) {
      content += `## Action Items\n\n`
      followup.action_items.forEach(item => {
        content += `- **${item.task}** (${item.assignee || 'TBD'}${item.due_date ? `, due: ${item.due_date}` : ''})\n`
      })
      content += '\n'
    }
    
    if (followup.concerns?.length > 0) {
      content += `## Concerns\n\n${followup.concerns.map(c => `- ${c}`).join('\n')}\n\n`
    }
    
    if (followup.email_draft) {
      content += `## Follow-up Email Draft\n\n${followup.email_draft}\n`
    }
    
    return content
  }

  // Export handlers
  const handleExportMd = () => {
    const content = buildExportContent()
    if (!content) return
    exportAsMarkdown(content, followup?.prospect_company_name || 'followup')
    toast({
      title: t('actions.mdDownloaded'),
      description: tCommon('export.markdownDownloaded'),
    })
  }

  const handleExportPdf = async () => {
    const content = buildExportContent()
    if (!content) return
    setIsExporting(true)
    try {
      await exportAsPdf(content, followup?.prospect_company_name || 'followup', `${followup?.prospect_company_name || 'Meeting'} - Follow-up`)
      toast({
        title: t('actions.pdfDownloaded'),
        description: tCommon('export.pdfDownloaded'),
      })
    } catch (error) {
      logger.error('PDF export failed', error, { source: 'FollowupDetailPage' })
      toast({
        variant: 'destructive',
        title: t('toast.failed'),
        description: tCommon('export.pdfFailed'),
      })
    } finally {
      setIsExporting(false)
    }
  }

  const handleExportDocx = async () => {
    const content = buildExportContent()
    if (!content) return
    setIsExporting(true)
    try {
      await exportAsDocx(content, followup?.prospect_company_name || 'followup', `${followup?.prospect_company_name || 'Meeting'} - Follow-up`)
      toast({
        title: t('actions.docxDownloaded'),
        description: tCommon('export.wordDownloaded'),
      })
    } catch (error) {
      logger.error('DOCX export failed', error, { source: 'FollowupDetailPage' })
      toast({
        variant: 'destructive',
        title: t('toast.failed'),
        description: tCommon('export.wordFailed'),
      })
    } finally {
      setIsExporting(false)
    }
  }

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-'
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

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

  if (!followup) return null

  const isProcessing = ['uploading', 'transcribing', 'summarizing'].includes(followup.status)
  const hasCommercialSignals = followup.commercial_signals && (
    followup.commercial_signals.koopsignalen?.length > 0 ||
    followup.commercial_signals.cross_sell?.length > 0 ||
    followup.commercial_signals.risks?.length > 0
  )
  const hasObservations = followup.observations && (
    followup.observations.doubts?.length > 0 ||
    followup.observations.unspoken_needs?.length > 0 ||
    followup.observations.opportunities?.length > 0 ||
    followup.observations.red_flags?.length > 0
  )

  return (
    <DashboardLayout user={user}>
      <>
        <div className="p-4 lg:p-6">
          {/* Page Header */}
          <div className="flex items-center gap-4 mb-6">
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push('/dashboard/followup')}
            >
              <Icons.arrowLeft className="h-4 w-4 mr-2" />
              {tCommon('back')}
            </Button>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                {followup.prospect_company_name || followup.meeting_subject || 'Meeting Follow-up'}
              </h1>
              <div className="flex items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
                {followup.meeting_date && (
                  <span>{new Date(followup.meeting_date).toLocaleDateString('nl-NL')}</span>
                )}
                {followup.audio_duration_seconds && (
                  <span className="flex items-center gap-1">
                    <Icons.clock className="h-3 w-3" />
                    {formatDuration(followup.audio_duration_seconds)}
                  </span>
                )}
                {followup.speaker_count > 0 && (
                  <span className="flex items-center gap-1">
                    <Icons.users className="h-3 w-3" />
                    {followup.speaker_count} {t('detail.speakers')}
                  </span>
                )}
              </div>
            </div>
            {isProcessing && (
              <div className="ml-auto flex items-center gap-2 text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/30 px-3 py-2 rounded-lg">
                <Icons.spinner className="h-4 w-4 animate-spin" />
                <span className="text-sm font-medium">
                  {t('form.processing')}
                </span>
              </div>
            )}
          </div>

          {/* Error State */}
          {followup.status === 'failed' && (
            <div className="mb-6 p-4 rounded-xl border-2 border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30">
              <div className="flex items-center gap-2 text-red-700 dark:text-red-400">
                <Icons.alertCircle className="h-5 w-5" />
                <span className="font-medium">{t('toast.failed')}</span>
              </div>
              <p className="text-sm text-red-600 dark:text-red-400 mt-1">{followup.error_message}</p>
            </div>
          )}

          {/* Processing State */}
          {isProcessing && (
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-12 text-center shadow-sm">
              <Icons.spinner className="h-16 w-16 text-orange-600 mx-auto mb-4 animate-spin" />
              <h3 className="font-bold text-lg mb-2 text-slate-900 dark:text-white">
                {t('form.processing')}
              </h3>
              <p className="text-slate-500 dark:text-slate-400">{t('toast.startedDesc')}</p>
            </div>
          )}

          {/* Main Content - Two Column Layout */}
          {followup.status === 'completed' && (
            <div className="flex gap-6">
              {/* Left Column - Main Content */}
              <div className="flex-1 min-w-0 space-y-6">
                
                {/* Actions Section - NOW FIRST */}
                <div className="rounded-xl border-2 border-indigo-200 dark:border-indigo-800 bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-950 dark:to-purple-950 p-6 shadow-sm">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h2 className="font-bold text-lg flex items-center gap-2 text-slate-900 dark:text-white">
                        <Icons.sparkles className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                        {t('actions.title')}
                      </h2>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                        {t('actions.subtitle')}
                      </p>
                    </div>
                  </div>
                  
                  <ActionsGrid
                    actionTypes={ACTION_TYPES}
                    existingActions={allActions}
                    onGenerate={handleGenerateAction}
                    onView={handleViewAction}
                    disabled={!!generatingActionType}
                    generatingType={generatingActionType}
                  />
                  
                  {/* Selected Action Panel - Inline Display */}
                  {selectedAction && (
                    <div className="mt-6 border-t pt-6">
                      <ActionPanel
                        action={selectedAction}
                        companyName={followup?.prospect_company_name || 'Followup'}
                        onUpdate={handleUpdateAction}
                        onDelete={handleDeleteAction}
                        onRegenerate={handleRegenerateAction}
                        onClose={() => setSelectedAction(null)}
                      />
                    </div>
                  )}
                </div>

                {/* Commercial Signals (Legacy) */}
                {hasCommercialSignals && (
                  <div className="rounded-xl border-2 border-amber-200 dark:border-amber-800 bg-gradient-to-br from-amber-50 to-yellow-50 dark:from-amber-950 dark:to-yellow-950 p-6 shadow-sm">
                    <h2 className="font-bold text-lg flex items-center gap-2 mb-4 text-slate-900 dark:text-white">
                      <Icons.trendingUp className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                      💰 {t('detail.commercialSignals')}
                    </h2>
                    <div className="grid gap-4 md:grid-cols-3">
                      {followup.commercial_signals?.koopsignalen && followup.commercial_signals.koopsignalen.length > 0 && (
                        <div className="bg-white/60 dark:bg-slate-800/60 p-4 rounded-lg">
                          <h4 className="font-semibold text-sm text-green-700 dark:text-green-400 mb-2">✓ Koopsignalen</h4>
                          <ul className="space-y-1">
                            {followup.commercial_signals.koopsignalen.map((s, i) => (
                              <li key={i} className="text-xs text-slate-700 dark:text-slate-300">{s}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {followup.commercial_signals?.cross_sell && followup.commercial_signals.cross_sell.length > 0 && (
                        <div className="bg-white/60 dark:bg-slate-800/60 p-4 rounded-lg">
                          <h4 className="font-semibold text-sm text-blue-700 dark:text-blue-400 mb-2">💡 {t('detail.crossSellUpsell')}</h4>
                          <ul className="space-y-1">
                            {followup.commercial_signals.cross_sell.map((s, i) => (
                              <li key={i} className="text-xs text-slate-700 dark:text-slate-300">{s}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {followup.commercial_signals?.risks && followup.commercial_signals.risks.length > 0 && (
                        <div className="bg-red-50 dark:bg-red-900/30 p-4 rounded-lg">
                          <h4 className="font-semibold text-sm text-red-700 dark:text-red-400 mb-2">⚠️ {t('detail.risks')}</h4>
                          <ul className="space-y-1">
                            {followup.commercial_signals.risks.map((s, i) => (
                              <li key={i} className="text-xs text-red-700 dark:text-red-400">{s}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Observations */}
                {hasObservations && (
                  <div className="rounded-xl border-2 border-indigo-200 dark:border-indigo-800 bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-950 dark:to-purple-950 p-6 shadow-sm">
                    <h2 className="font-bold text-lg flex items-center gap-2 mb-4 text-slate-900 dark:text-white">
                      <Icons.search className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                      🔎 {t('detail.observations')}
                    </h2>
                    <div className="grid gap-4 md:grid-cols-2">
                      {followup.observations?.doubts && followup.observations.doubts.length > 0 && (
                        <div className="bg-amber-50 dark:bg-amber-900/30 p-4 rounded-lg">
                          <h4 className="font-semibold text-sm text-amber-700 dark:text-amber-400 mb-2">⚠️ {t('detail.doubts')}</h4>
                          <ul className="space-y-1">
                            {followup.observations.doubts.map((d, i) => (
                              <li key={i} className="text-xs text-slate-700 dark:text-slate-300">{d}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {followup.observations?.unspoken_needs && followup.observations.unspoken_needs.length > 0 && (
                        <div className="bg-yellow-50 dark:bg-yellow-900/30 p-4 rounded-lg">
                          <h4 className="font-semibold text-sm text-yellow-700 dark:text-yellow-400 mb-2">💡 {t('detail.unspokenNeeds')}</h4>
                          <ul className="space-y-1">
                            {followup.observations.unspoken_needs.map((n, i) => (
                              <li key={i} className="text-xs text-slate-700 dark:text-slate-300">{n}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {followup.observations?.opportunities && followup.observations.opportunities.length > 0 && (
                        <div className="bg-green-50 dark:bg-green-900/30 p-4 rounded-lg">
                          <h4 className="font-semibold text-sm text-green-700 dark:text-green-400 mb-2">🎯 Kansen</h4>
                          <ul className="space-y-1">
                            {followup.observations.opportunities.map((o, i) => (
                              <li key={i} className="text-xs text-slate-700 dark:text-slate-300">{o}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {followup.observations?.red_flags && followup.observations.red_flags.length > 0 && (
                        <div className="bg-red-50 dark:bg-red-900/30 p-4 rounded-lg">
                          <h4 className="font-semibold text-sm text-red-700 dark:text-red-400 mb-2">🚩 Rode Vlaggen</h4>
                          <ul className="space-y-1">
                            {followup.observations.red_flags.map((f, i) => (
                              <li key={i} className="text-xs text-red-700 dark:text-red-400">{f}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Transcription (collapsible) */}
                {followup.transcription_text && (
                  <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
                    <button
                      className="w-full p-4 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800"
                      onClick={() => setShowTranscript(!showTranscript)}
                    >
                      <h2 className="font-bold text-lg flex items-center gap-2 text-slate-900 dark:text-white">
                        <Icons.fileText className="h-5 w-5 text-slate-600 dark:text-slate-400" />
                        {t('detail.transcription')}
                      </h2>
                      {showTranscript ? <Icons.chevronDown className="h-5 w-5 text-slate-500" /> : <Icons.chevronRight className="h-5 w-5 text-slate-500" />}
                    </button>
                    {showTranscript && (
                      <div className="p-4 pt-0 border-t dark:border-slate-800">
                        <div className="max-h-96 overflow-y-auto bg-slate-50 dark:bg-slate-800 rounded-lg p-4">
                          <pre className="whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-300 font-sans">
                            {followup.transcription_text}
                          </pre>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-3"
                          onClick={() => handleCopy(followup.transcription_text || '', 'transcript')}
                        >
                          <Icons.copy className="h-4 w-4 mr-1" />
                          {copied === 'transcript' ? tCommon('copied') : t('detail.copyTranscription')}
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Right Column - Sticky Sidebar */}
              <div className="w-80 flex-shrink-0 hidden lg:block">
                <div className="sticky top-4 space-y-4">
                  
                  {/* Meeting Info */}
                  <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                    <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                      <Icons.calendar className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                      {t('detail.meetingInfo')}
                    </h3>
                    <div className="space-y-2 text-sm">
                      {followup.meeting_date && (
                        <div className="flex justify-between">
                          <span className="text-slate-500 dark:text-slate-400">{t('detail.date')}</span>
                          <span className="font-medium text-slate-900 dark:text-white">{new Date(followup.meeting_date).toLocaleDateString('nl-NL')}</span>
                        </div>
                      )}
                      {followup.audio_duration_seconds && (
                        <div className="flex justify-between">
                          <span className="text-slate-500 dark:text-slate-400">{t('detail.duration')}</span>
                          <span className="font-medium text-slate-900 dark:text-white">{formatDuration(followup.audio_duration_seconds)}</span>
                        </div>
                      )}
                      {followup.speaker_count > 0 && (
                        <div className="flex justify-between">
                          <span className="text-slate-500 dark:text-slate-400">{t('detail.speakers')}</span>
                          <span className="font-medium text-slate-900 dark:text-white">{followup.speaker_count}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Action Items */}
                  {followup.action_items?.length > 0 && (
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                      <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                        <Icons.check className="h-4 w-4 text-green-600 dark:text-green-400" />
                        {t('detail.actionItems')} ({followup.action_items.length})
                      </h3>
                      <div className="space-y-2">
                        {followup.action_items.slice(0, 5).map((item, i) => (
                          <div key={i} className="flex items-start gap-2 text-sm">
                            <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${
                              item.priority === 'high' ? 'bg-red-500' :
                              item.priority === 'medium' ? 'bg-yellow-500' : 'bg-green-500'
                            }`} />
                            <div className="min-w-0">
                              <p className="truncate font-medium text-slate-900 dark:text-white">{item.task}</p>
                              <p className="text-xs text-slate-500 dark:text-slate-400">
                                {item.assignee || 'TBD'} {item.due_date && `• ${item.due_date}`}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Related Research */}
                  {researchBrief && (
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                      <h3 className="font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                        <Icons.search className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                        {t('detail.linkedResearch')}
                      </h3>
                      <button
                        onClick={() => router.push(`/dashboard/research/${researchBrief.id}`)}
                        className="w-full p-3 bg-blue-50 dark:bg-blue-900/30 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors text-left group"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium text-sm text-blue-900 dark:text-blue-100">{researchBrief.company_name}</p>
                            <p className="text-xs text-blue-600 dark:text-blue-400">
                              {researchBrief.completed_at ? new Date(researchBrief.completed_at).toLocaleDateString('nl-NL') : '-'}
                            </p>
                          </div>
                          <Icons.chevronRight className="h-4 w-4 text-blue-600 dark:text-blue-400 group-hover:translate-x-1 transition-transform" />
                        </div>
                      </button>
                    </div>
                  )}

                  {/* Related Preparation */}
                  {meetingPrep && (
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                      <h3 className="font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                        <Icons.fileText className="h-4 w-4 text-green-600 dark:text-green-400" />
                        {t('detail.linkedPreparation')}
                      </h3>
                      <button
                        onClick={() => router.push(`/dashboard/preparation/${meetingPrep.id}`)}
                        className="w-full p-3 bg-green-50 dark:bg-green-900/30 rounded-lg hover:bg-green-100 dark:hover:bg-green-900/50 transition-colors text-left group"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium text-sm text-green-900 dark:text-green-100">{meetingPrep.prospect_company_name}</p>
                            <p className="text-xs text-green-600 dark:text-green-400">
                              {meetingPrep.meeting_type} • {meetingPrep.completed_at ? new Date(meetingPrep.completed_at).toLocaleDateString('nl-NL') : '-'}
                            </p>
                          </div>
                          <Icons.chevronRight className="h-4 w-4 text-green-600 dark:text-green-400 group-hover:translate-x-1 transition-transform" />
                        </div>
                      </button>
                    </div>
                  )}

                  {/* Linked Deal */}
                  {linkedDeal && (
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                      <h3 className="font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                        <Icons.target className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                        {t('detail.linkedDeal')}
                      </h3>
                      <button
                        onClick={() => router.push(`/dashboard/prospects/${linkedDeal.prospect_id}/deals/${linkedDeal.id}`)}
                        className="w-full p-3 bg-indigo-50 dark:bg-indigo-900/30 rounded-lg hover:bg-indigo-100 dark:hover:bg-indigo-900/50 transition-colors text-left group"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium text-sm text-indigo-900 dark:text-indigo-100">{linkedDeal.name}</p>
                            <p className="text-xs text-indigo-600 dark:text-indigo-400">
                              {linkedDeal.is_active ? '✅ Active' : '📁 Archived'}
                            </p>
                          </div>
                          <Icons.chevronRight className="h-4 w-4 text-indigo-600 dark:text-indigo-400 group-hover:translate-x-1 transition-transform" />
                        </div>
                      </button>
                    </div>
                  )}

                  {/* Linked Contacts */}
                  {linkedContacts.length > 0 && (
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                      <h3 className="font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                        <Icons.user className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                        {t('detail.linkedContact')}
                      </h3>
                      <div className="space-y-2">
                        {linkedContacts.map((contact) => (
                          <button
                            key={contact.id}
                            onClick={() => researchBrief && router.push(`/dashboard/research/${researchBrief.id}#contacts`)}
                            className="w-full p-3 bg-purple-50 dark:bg-purple-900/30 rounded-lg hover:bg-purple-100 dark:hover:bg-purple-900/50 transition-colors text-left group"
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="font-medium text-sm text-purple-900 dark:text-purple-100">{contact.name}</p>
                                {contact.role && (
                                  <p className="text-xs text-purple-600 dark:text-purple-400">{contact.role}</p>
                                )}
                                {contact.communication_style && (
                                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                                    💬 {contact.communication_style}
                                  </p>
                                )}
                                {contact.decision_authority && (
                                  <p className="text-xs text-slate-500 dark:text-slate-400">
                                    🎯 {contact.decision_authority}
                                  </p>
                                )}
                              </div>
                              <Icons.chevronRight className="h-4 w-4 text-purple-600 dark:text-purple-400 group-hover:translate-x-1 transition-transform" />
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Audio Player */}
                  {followup.audio_url && (
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                      <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                        <Icons.mic className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                        {t('detail.audioPlayer')}
                      </h3>
                      <audio controls className="w-full h-10">
                        <source src={followup.audio_url} />
                      </audio>
                    </div>
                  )}

                  {/* CTA - New Research */}
                  <div className="rounded-xl border-2 border-blue-200 dark:border-blue-800 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950 p-4 shadow-sm">
                    <h3 className="font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                      <Icons.arrowRight className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                      {t('detail.nextProspect')}
                    </h3>
                    <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
                      {t('detail.nextProspectDesc')}
                    </p>
                    <Button 
                      className="w-full bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600"
                      onClick={() => router.push('/dashboard/research')}
                    >
                      <Icons.search className="h-4 w-4 mr-2" />
                      {t('detail.startNewResearch')}
                    </Button>
                  </div>

                </div>
              </div>
            </div>
          )}
        </div>
      
        <Toaster />
      </>
    </DashboardLayout>
  )
}
