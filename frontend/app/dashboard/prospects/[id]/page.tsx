'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { User } from '@supabase/supabase-js'
import { 
  Building2, 
  Users, 
  Search, 
  FileText, 
  ChevronRight,
  ChevronLeft,
  Plus,
  Globe,
  Linkedin,
  MapPin,
  CheckCircle2,
  Circle,
  Loader2,
  Mic,
  ExternalLink,
  Send,
  Pin,
  PinOff,
  Trash2,
  Lightbulb,
  Calendar,
  ArrowRight,
  Mail
} from 'lucide-react'
import { DashboardLayout } from '@/components/layout/dashboard-layout'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/components/ui/use-toast'
import { useConfirmDialog } from '@/components/confirm-dialog'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { ProspectHub, ProspectContact, ProspectHubPreparation, ProspectHubFollowup, CalendarMeeting, Deal } from '@/types'
import { smartDate } from '@/lib/date-utils'
import { Badge } from '@/components/ui/badge'
import { Video, Clock } from 'lucide-react'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { ResearchForm, PreparationForm, FollowupUploadForm } from '@/components/forms'
import { ContactSearchModal } from '@/components/contacts'
import { logger } from '@/lib/logger'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// ============================================================
// Types
// ============================================================

interface ProspectNote {
  id: string
  prospect_id: string
  user_id: string
  content: string
  is_pinned: boolean
  created_at: string
  updated_at: string
}

interface TimelineEvent {
  id: string
  type: 'research' | 'contact' | 'prep' | 'meeting' | 'followup' | 'created'
  title: string
  date: string
}

// ============================================================
// Main Component
// ============================================================

export default function ProspectHubPage() {
  const params = useParams()
  const router = useRouter()
  const prospectId = params.id as string
  const t = useTranslations('prospectHub')
  const tCommon = useTranslations('common')
  const { toast } = useToast()
  const { confirm } = useConfirmDialog()
  
  const supabase = createClientComponentClient()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [hubData, setHubData] = useState<ProspectHub | null>(null)
  const [organizationId, setOrganizationId] = useState<string | null>(null)
  
  // Notes state
  const [notes, setNotes] = useState<ProspectNote[]>([])
  const [newNoteContent, setNewNoteContent] = useState('')
  const [savingNote, setSavingNote] = useState(false)
  
  // Meetings state
  const [upcomingMeetings, setUpcomingMeetings] = useState<CalendarMeeting[]>([])
  const [loadingMeetings, setLoadingMeetings] = useState(false)
  
  // Deals state (for forms)
  const [deals, setDeals] = useState<Deal[]>([])
  
  // Sheet state - inline actions (SPEC-041)
  const [researchSheetOpen, setResearchSheetOpen] = useState(false)
  const [prepSheetOpen, setPrepSheetOpen] = useState(false)
  const [followupSheetOpen, setFollowupSheetOpen] = useState(false)
  const [contactModalOpen, setContactModalOpen] = useState(false)
  
  // Contact detail view state
  const [selectedContact, setSelectedContact] = useState<ProspectContact | null>(null)
  const [contactDetailOpen, setContactDetailOpen] = useState(false)
  
  // Refetch hub data function - used after sheet actions
  const refetchHubData = useCallback(async () => {
    if (!organizationId) return
    
    try {
      const now = new Date()
      const fromDate = now.toISOString()
      const toDate = new Date(now.getTime() + 14 * 24 * 60 * 60 * 1000).toISOString()
      
      const [hubResponse, notesResponse, meetingsResponse, dealsResponse] = await Promise.all([
        api.get<ProspectHub>(
          `/api/v1/prospects/${prospectId}/hub?organization_id=${organizationId}`
        ),
        api.get<ProspectNote[]>(`/api/v1/prospects/${prospectId}/notes`),
        api.get<{ meetings: CalendarMeeting[] }>(
          `/api/v1/calendar-meetings?prospect_id=${prospectId}&from_date=${fromDate}&to_date=${toDate}`
        ),
        supabase
          .from('deals')
          .select('*')
          .eq('prospect_id', prospectId)
          .eq('is_active', true)
          .order('created_at', { ascending: false })
      ])
      
      if (!hubResponse.error && hubResponse.data) {
        setHubData(hubResponse.data)
      }
      if (!notesResponse.error && notesResponse.data) {
        setNotes(notesResponse.data)
      }
      if (!meetingsResponse.error && meetingsResponse.data) {
        setUpcomingMeetings(meetingsResponse.data.meetings || [])
      }
      if (!dealsResponse.error && dealsResponse.data) {
        setDeals(dealsResponse.data || [])
      }
    } catch (error) {
      logger.error('Error refetching hub data:', error)
    }
  }, [organizationId, prospectId, supabase])

  // Initial load
  useEffect(() => {
    async function loadData() {
      try {
        const { data: { user } } = await supabase.auth.getUser()
        setUser(user)
        
        if (user) {
          const { data: orgMember } = await supabase
            .from('organization_members')
            .select('organization_id')
            .eq('user_id', user.id)
            .single()
          
          if (orgMember) {
            setOrganizationId(orgMember.organization_id)
            
            // Calculate date range for upcoming meetings (14 days ahead)
            const now = new Date()
            const fromDate = now.toISOString()
            const toDate = new Date(now.getTime() + 14 * 24 * 60 * 60 * 1000).toISOString()
            
            // Fetch hub data, notes, meetings, and deals in parallel
            const [hubResponse, notesResponse, meetingsResponse, dealsResponse] = await Promise.all([
              api.get<ProspectHub>(
                `/api/v1/prospects/${prospectId}/hub?organization_id=${orgMember.organization_id}`
              ),
              api.get<ProspectNote[]>(`/api/v1/prospects/${prospectId}/notes`),
              api.get<{ meetings: CalendarMeeting[] }>(
                `/api/v1/calendar-meetings?prospect_id=${prospectId}&from_date=${fromDate}&to_date=${toDate}`
              ),
              supabase
                .from('deals')
                .select('*')
                .eq('prospect_id', prospectId)
                .eq('is_active', true)
                .order('created_at', { ascending: false })
            ])
            
            if (!hubResponse.error && hubResponse.data) {
              setHubData(hubResponse.data)
            }
            
            if (!notesResponse.error && notesResponse.data) {
              setNotes(notesResponse.data)
            }
            
            if (!meetingsResponse.error && meetingsResponse.data) {
              setUpcomingMeetings(meetingsResponse.data.meetings || [])
            }
            
            if (!dealsResponse.error && dealsResponse.data) {
              setDeals(dealsResponse.data || [])
            }
          }
        }
      } catch (error) {
        logger.error('Error loading data:', error)
      } finally {
        setLoading(false)
      }
    }
    
    loadData()
  }, [supabase, prospectId])
  
  // Add note handler
  const handleAddNote = async () => {
    if (!newNoteContent.trim()) return
    
    setSavingNote(true)
    try {
      const { data, error } = await api.post<ProspectNote>(
        `/api/v1/prospects/${prospectId}/notes`,
        { content: newNoteContent.trim(), is_pinned: false }
      )
      
      if (!error && data) {
        setNotes([data, ...notes])
        setNewNoteContent('')
      }
    } catch (error) {
      toast({ variant: "destructive", title: t('errors.noteSaveFailed') })
    } finally {
      setSavingNote(false)
    }
  }
  
  // Toggle pin handler
  const handleTogglePin = async (note: ProspectNote) => {
    try {
      const { error } = await api.patch(
        `/api/v1/prospects/${prospectId}/notes/${note.id}`,
        { is_pinned: !note.is_pinned }
      )
      
      if (!error) {
        setNotes(notes.map(n => 
          n.id === note.id ? { ...n, is_pinned: !n.is_pinned } : n
        ).sort((a, b) => {
          if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        }))
      }
    } catch (error) {
      console.error('Error toggling pin:', error)
    }
  }
  
  // Delete note handler
  const handleDeleteNote = async (noteId: string) => {
    const confirmed = await confirm({
      title: t('confirm.deleteNoteTitle'),
      description: t('confirm.deleteNoteDescription'),
      confirmLabel: tCommon('delete'),
      cancelLabel: tCommon('cancel'),
      variant: 'danger'
    })
    
    if (!confirmed) return
    
    try {
      const { error } = await api.delete(`/api/v1/prospects/${prospectId}/notes/${noteId}`)
      if (!error) {
        setNotes(notes.filter(n => n.id !== noteId))
      }
    } catch (error) {
      console.error('Error deleting note:', error)
    }
  }
  
  // Loading state
  if (loading) {
    return (
      <DashboardLayout user={user}>
        <div className="flex items-center justify-center h-96">
          <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
        </div>
      </DashboardLayout>
    )
  }
  
  // Not found state
  if (!hubData) {
    return (
      <DashboardLayout user={user}>
        <div className="flex flex-col items-center justify-center h-96 text-center">
          <Building2 className="w-16 h-16 text-slate-300 dark:text-slate-600 mb-4" />
          <h2 className="text-xl font-semibold mb-2 text-slate-900 dark:text-white">
            {t('errors.notFound')}
          </h2>
          <Button onClick={() => router.push('/dashboard/prospects')} variant="outline">
            <ChevronLeft className="w-4 h-4 mr-1" />
            {t('actions.backToProspects')}
          </Button>
        </div>
      </DashboardLayout>
    )
  }
  
  const { prospect, research, contacts, preparations, followups, stats, recent_activities } = hubData
  
  // Determine journey progress
  // Check if any meeting has passed (is_now or end_time < now)
  const hasPastMeeting = upcomingMeetings.some(m => {
    const endTime = new Date(m.end_time)
    return m.is_now || endTime < new Date()
  })
  
  const journeySteps = [
    { key: 'research', done: !!research, label: t('journey.research') },
    { key: 'contacts', done: contacts.length > 0, label: t('journey.contacts') },
    { key: 'preparation', done: stats.prep_count > 0, label: t('journey.preparation') },
    { key: 'meeting', done: hasPastMeeting || upcomingMeetings.length > 0, label: t('journey.meeting') },
    { key: 'followup', done: stats.followup_count > 0, label: t('journey.followup') }
  ]
  
  const currentStepIndex = journeySteps.findIndex(s => !s.done)
  const nextStep = journeySteps[currentStepIndex] || null
  
  // Extract key insights from research - look for actual data, not headers
  const getKeyInsights = (): { label: string; value: string }[] => {
    if (!research?.brief_content) return []
    
    const content = research.brief_content
    const lines = content.split('\n')
    const insights: { label: string; value: string }[] = []
    
    // Headers to skip (these are section labels, not data)
    const skipHeaders = [
      'what this means commercially',
      'commercial insight', 
      'what these signals suggest',
      'their value proposition',
      'what they do',
      'revenue model'
    ]
    
    // Look specifically for "**Label**: Value" patterns (the actual data)
    for (const line of lines) {
      const trimmed = line.trim()
      
      // Skip empty lines and markdown headers
      if (!trimmed || trimmed.startsWith('#')) continue
      
      // Remove bullet point prefix if present
      const withoutBullet = trimmed.replace(/^[•\-\*]\s*/, '').trim()
      
      // Match "**Label**: Value" pattern (this is actual data)
      const labelValueMatch = withoutBullet.match(/^\*\*(.+?)\*\*[:\s]+(.+)$/)
      if (labelValueMatch) {
        const label = labelValueMatch[1].trim()
        const value = labelValueMatch[2].trim()
        
        // Skip if it's a known header or has no real value
        if (skipHeaders.some(h => label.toLowerCase().includes(h))) continue
        if (value.length < 3 || value === '[...]' || value.startsWith('[')) continue
        
        // Good insight found!
        insights.push({ label, value })
        if (insights.length >= 4) break
      }
    }
    
    // If we didn't find enough label:value pairs, look for key sections
    if (insights.length < 2) {
      // Look for founded year, headquarters, etc in table format
      const tableMatch = content.match(/\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|/g)
      if (tableMatch) {
        for (const row of tableMatch) {
          const match = row.match(/\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|/)
          if (match && match[2] && !match[2].startsWith('[')) {
            const label = match[1].trim()
            const value = match[2].trim()
            if (value.length > 2 && !insights.some(i => i.label === label)) {
              insights.push({ label, value })
              if (insights.length >= 4) break
            }
          }
        }
      }
    }
    
    return insights.slice(0, 4)
  }
  
  const keyInsights = getKeyInsights()
  
  // Get next action config - now opens sheets instead of navigating (SPEC-041)
  const getNextActionConfig = () => {
    if (!research) {
      return {
        title: t('nextAction.startResearch'),
        description: t('nextAction.startResearchDesc'),
        action: () => setResearchSheetOpen(true),
        buttonLabel: t('nextAction.startResearchBtn')
      }
    }
    if (contacts.length === 0) {
      return {
        title: t('nextAction.addContacts'),
        description: t('nextAction.addContactsDesc'),
        action: () => setContactModalOpen(true),
        buttonLabel: t('nextAction.addContactsBtn')
      }
    }
    if (stats.prep_count === 0) {
      return {
        title: t('nextAction.createPrep'),
        description: t('nextAction.createPrepDesc'),
        action: () => setPrepSheetOpen(true),
        buttonLabel: t('nextAction.createPrepBtn')
      }
    }
    if (stats.followup_count === 0) {
      return {
        title: t('nextAction.addFollowup'),
        description: t('nextAction.addFollowupDesc'),
        action: () => setFollowupSheetOpen(true),
        buttonLabel: t('nextAction.addFollowupBtn')
      }
    }
    return {
      title: t('nextAction.allDone'),
      description: t('nextAction.allDoneDesc'),
      action: () => setFollowupSheetOpen(true),
      buttonLabel: t('nextAction.viewFollowups')
    }
  }
  
  const nextAction = getNextActionConfig()
  
  // Build timeline events - combine activities with meetings
  const activityEvents: TimelineEvent[] = (recent_activities || []).slice(0, 6).map((event) => ({
    id: event.id,
    type: event.activity_type as TimelineEvent['type'],
    title: event.title,
    date: event.created_at
  }))
  
  // Add meetings as timeline events
  const meetingEvents: TimelineEvent[] = upcomingMeetings
    .filter(m => new Date(m.end_time) < new Date() || m.is_now) // Only past/current meetings
    .slice(0, 3)
    .map(meeting => ({
      id: `meeting-${meeting.id}`,
      type: 'meeting' as const,
      title: meeting.title,
      date: meeting.start_time
    }))
  
  // Combine and sort by date (most recent first)
  const timelineEvents: TimelineEvent[] = [...activityEvents, ...meetingEvents]
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
    .slice(0, 8)
  
  return (
    <DashboardLayout user={user}>
      <div className="p-4 lg:p-6 max-w-7xl mx-auto">
        
        {/* Back Button */}
        <Button 
          variant="ghost" 
          size="sm" 
          onClick={() => router.push('/dashboard/prospects')}
          className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 -ml-2 mb-4"
        >
          <ChevronLeft className="w-4 h-4 mr-1" />
          {t('actions.backToProspects')}
        </Button>
        
        {/* ============================================================ */}
        {/* HEADER */}
        {/* ============================================================ */}
        <div className="bg-gradient-to-r from-purple-600 to-purple-700 rounded-xl p-6 mb-6 text-white">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center flex-shrink-0">
                <Building2 className="w-7 h-7 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold">{prospect.company_name}</h1>
                <div className="flex items-center gap-3 mt-1 text-purple-100 text-sm flex-wrap">
                  {prospect.industry && (
                    <span className="flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-purple-300" />
                      {prospect.industry}
                    </span>
                  )}
                  {(prospect.city || prospect.country) && (
                    <span className="flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5" />
                      {[prospect.city, prospect.country].filter(Boolean).join(', ')}
                    </span>
                  )}
                </div>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              {prospect.website && (
                <Button 
                  variant="secondary" 
                  size="sm" 
                  className="bg-white/20 hover:bg-white/30 text-white border-0"
                  asChild
                >
                  <a href={prospect.website} target="_blank" rel="noopener noreferrer">
                    <Globe className="w-4 h-4" />
                  </a>
                </Button>
              )}
              {prospect.linkedin_url && (
                <Button 
                  variant="secondary" 
                  size="sm" 
                  className="bg-white/20 hover:bg-white/30 text-white border-0"
                  asChild
                >
                  <a href={prospect.linkedin_url} target="_blank" rel="noopener noreferrer">
                    <Linkedin className="w-4 h-4" />
                  </a>
                </Button>
              )}
            </div>
          </div>
        </div>
        
        {/* ============================================================ */}
        {/* MAIN GRID: Content + Sidebar */}
        {/* ============================================================ */}
        <div className="grid lg:grid-cols-12 gap-6">
          
          {/* LEFT: Main Content (8 cols) */}
          <div className="lg:col-span-8 space-y-6">
            
            {/* KEY INSIGHTS - Attractive gradient card */}
            {keyInsights.length > 0 && (
              <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-amber-50 via-orange-50 to-yellow-50 dark:from-amber-950/40 dark:via-orange-950/30 dark:to-yellow-950/20 border border-amber-200/60 dark:border-amber-800/40 shadow-sm">
                {/* Decorative elements */}
                <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-amber-200/30 to-orange-200/20 dark:from-amber-800/20 dark:to-orange-800/10 rounded-full blur-2xl -translate-y-1/2 translate-x-1/2" />
                <div className="absolute bottom-0 left-0 w-24 h-24 bg-gradient-to-tr from-yellow-200/30 to-amber-200/20 dark:from-yellow-800/20 dark:to-amber-800/10 rounded-full blur-xl translate-y-1/2 -translate-x-1/2" />
                
                <div className="relative p-5">
                  {/* Header */}
                  <div className="flex items-center gap-2 mb-4">
                    <div className="p-2 rounded-lg bg-amber-100 dark:bg-amber-900/50">
                      <Lightbulb className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                    </div>
                    <h3 className="font-semibold text-slate-900 dark:text-white">
                      {t('sections.keyInsights')}
                    </h3>
                  </div>
                  
                  {/* Insights Grid */}
                  <div className="grid gap-2.5">
                    {keyInsights.map((insight, i) => (
                      <div 
                        key={i} 
                        className="flex items-start gap-3 p-3 rounded-lg bg-white/70 dark:bg-slate-900/50 backdrop-blur-sm border border-amber-100/60 dark:border-amber-800/40 hover:border-amber-200 dark:hover:border-amber-700/60 transition-colors"
                      >
                        <div className="w-2 h-2 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 mt-2 flex-shrink-0 shadow-sm" />
                        <div className="flex-1 min-w-0">
                          <span className="font-semibold text-amber-900 dark:text-amber-200 text-sm">
                            {insight.label}:
                          </span>
                          <span className="text-slate-700 dark:text-slate-300 text-sm ml-1.5">
                            {insight.value}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                  
                  {/* Footer link */}
                  {research && (
                    <div className="mt-4 pt-3 border-t border-amber-200/50 dark:border-amber-800/30">
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="h-8 text-amber-700 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-300 hover:bg-amber-100/50 dark:hover:bg-amber-900/30"
                        onClick={() => router.push(`/dashboard/research/${research.id}`)}
                      >
                        {t('actions.viewFullResearch')}
                        <ExternalLink className="w-3.5 h-3.5 ml-1.5" />
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            )}
            
            {/* DOCUMENTS - Now with inline Sheet actions (SPEC-041) */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <FileText className="w-5 h-5 text-purple-500" />
                  {t('sections.documents')}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-2">
                  {/* Research - with explicit View Research button when completed */}
                  <DocumentRow
                    icon={<Search className="w-4 h-4" />}
                    label={t('documents.research')}
                    status={
                      research?.status === 'completed' ? 'completed' :
                      research?.status === 'pending' || research?.status === 'researching' ? 'in_progress' :
                      'empty'
                    }
                    statusLabel={research?.status === 'pending' || research?.status === 'researching' ? t('status.inProgress') : undefined}
                    date={research?.completed_at}
                    onClick={research?.status === 'completed' ? () => router.push(`/dashboard/research/${research.id}`) : undefined}
                    actionLabel={!research ? t('actions.create') : research?.status === 'completed' ? t('actions.viewResearch') : undefined}
                    onAction={!research ? () => setResearchSheetOpen(true) : research?.status === 'completed' ? () => router.push(`/dashboard/research/${research.id}`) : undefined}
                  />
                  
                  {/* Preparations - expandable with inline items */}
                  <DocumentSection
                    icon={<FileText className="w-4 h-4" />}
                    label={t('documents.preparation')}
                    items={preparations}
                    createLabel={preparations.length > 0 ? t('actions.createNew') : t('actions.create')}
                    onCreate={() => setPrepSheetOpen(true)}
                    onItemClick={(id) => router.push(`/dashboard/preparation/${id}`)}
                    getItemTitle={(item) => {
                      const prep = item as ProspectHubPreparation
                      const meetingType = prep.meeting_type ? prep.meeting_type.charAt(0).toUpperCase() + prep.meeting_type.slice(1).replace('_', ' ') : 'Meeting'
                      const contactName = prep.contact_names?.[0]
                      return contactName ? `${meetingType} with ${contactName}` : meetingType
                    }}
                    getItemStatus={(item) => (item as ProspectHubPreparation).status}
                    getItemDate={(item) => item.completed_at || item.created_at}
                  />
                  
                  {/* Follow-ups - expandable with inline items */}
                  <DocumentSection
                    icon={<Mic className="w-4 h-4" />}
                    label={t('documents.followup')}
                    items={followups}
                    createLabel={followups.length > 0 ? t('actions.createNew') : t('actions.create')}
                    onCreate={() => setFollowupSheetOpen(true)}
                    onItemClick={(id) => router.push(`/dashboard/followup/${id}`)}
                    getItemTitle={(item) => {
                      const fu = item as ProspectHubFollowup
                      const subject = fu.meeting_subject || 'Meeting Analysis'
                      const contactName = fu.contact_names?.[0]
                      return contactName ? `${subject} with ${contactName}` : subject
                    }}
                    getItemStatus={(item) => (item as ProspectHubFollowup).status}
                    getItemDate={(item) => item.completed_at || item.created_at}
                  />
                </div>
              </CardContent>
            </Card>
            
            {/* UPCOMING MEETINGS */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Calendar className="w-5 h-5 text-purple-500" />
                    {t('sections.upcomingMeetings')}
                    {upcomingMeetings.length > 0 && (
                      <span className="text-slate-400 font-normal">({upcomingMeetings.length})</span>
                    )}
                  </CardTitle>
                  <Button 
                    variant="ghost" 
                    size="sm"
                    onClick={() => router.push(`/dashboard/meetings?prospect_id=${prospectId}`)}
                    className="text-purple-600"
                  >
                    {t('actions.viewAll')}
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                {upcomingMeetings.length === 0 ? (
                  <div className="text-center py-6 text-slate-500">
                    <Calendar className="w-10 h-10 mx-auto mb-2 text-slate-300 dark:text-slate-600" />
                    <p className="text-sm">{t('empty.noMeetings')}</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {upcomingMeetings.slice(0, 3).map(meeting => (
                      <div 
                        key={meeting.id}
                        className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                      >
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-slate-900 dark:text-white truncate text-sm">
                              {meeting.title}
                            </p>
                            <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
                              <Clock className="w-3 h-3" />
                              <span>{smartDate(meeting.start_time)}</span>
                              {meeting.is_online && (
                                <>
                                  <span>•</span>
                                  <Video className="w-3 h-3" />
                                  <span>{tCommon('online')}</span>
                                </>
                              )}
                            </div>
                          </div>
                          {meeting.is_now && (
                            <Badge variant="destructive" className="text-xs animate-pulse">
                              {t('badges.now')}
                            </Badge>
                          )}
                        </div>
                        
                        {/* Prep status */}
                        <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-200 dark:border-slate-700">
                          {meeting.prep_status?.has_prep ? (
                            <Badge variant="outline" className="text-xs text-green-600 border-green-200 bg-green-50 dark:bg-green-900/20">
                              <CheckCircle2 className="w-3 h-3 mr-1" />
                              {t('badges.prepared')}
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-xs text-amber-600 border-amber-200 bg-amber-50 dark:bg-amber-900/20">
                              {t('badges.notPrepared')}
                            </Badge>
                          )}
                          
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 text-xs text-purple-600"
                            onClick={() => {
                              if (meeting.prep_status?.has_prep && meeting.prep_status.prep_id) {
                                router.push(`/dashboard/preparation/${meeting.prep_status.prep_id}`)
                              } else {
                                router.push(`/dashboard/preparation?prospect_id=${prospectId}&meeting_date=${meeting.start_time}`)
                              }
                            }}
                          >
                            {meeting.prep_status?.has_prep ? t('actions.viewPrep') : t('actions.prepareNow')}
                            <ArrowRight className="w-3 h-3 ml-1" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
          
          {/* RIGHT: Sidebar (4 cols) */}
          <div className="lg:col-span-4 space-y-6">
            
            {/* JOURNEY PROGRESS */}
            <Card className="border-purple-200 dark:border-purple-800/50 bg-purple-50/50 dark:bg-purple-950/20">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">{t('sections.journey')}</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-3">
                  {journeySteps.map((step, i) => (
                    <div 
                      key={step.key}
                      className={`flex items-center gap-3 ${
                        step.done 
                          ? 'text-purple-700 dark:text-purple-300' 
                          : i === currentStepIndex 
                            ? 'text-purple-600 dark:text-purple-400 font-medium' 
                            : 'text-slate-400 dark:text-slate-500'
                      }`}
                    >
                      {step.done ? (
                        <CheckCircle2 className="w-5 h-5 text-purple-500" />
                      ) : i === currentStepIndex ? (
                        <div className="w-5 h-5 rounded-full border-2 border-purple-500 flex items-center justify-center">
                          <div className="w-2 h-2 rounded-full bg-purple-500" />
                        </div>
                      ) : (
                        <Circle className="w-5 h-5" />
                      )}
                      <span className="text-sm">{step.label}</span>
                    </div>
                  ))}
                </div>
                
                {/* Next Action */}
                <div className="mt-6 pt-4 border-t border-purple-200 dark:border-purple-800">
                  <p className="text-xs font-medium text-purple-600 dark:text-purple-400 uppercase tracking-wide mb-2">
                    {t('nextAction.label')}
                  </p>
                  <p className="text-sm text-slate-700 dark:text-slate-300 mb-3">
                    {nextAction.description}
                  </p>
                  <Button 
                    size="sm" 
                    className="w-full bg-purple-600 hover:bg-purple-700"
                    onClick={nextAction.action}
                  >
                    {nextAction.buttonLabel}
                    <ArrowRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              </CardContent>
            </Card>
            
            {/* PEOPLE - Compact sidebar version */}
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Users className="w-4 h-4 text-purple-500" />
                    {t('sections.people')}
                    <span className="text-slate-400 font-normal text-sm">({contacts.length})</span>
                  </CardTitle>
                  {research && (
                    <Button 
                      variant="ghost" 
                      size="sm"
                      onClick={() => setContactModalOpen(true)}
                      className="h-7 text-xs text-purple-600"
                    >
                      <Plus className="w-3 h-3 mr-1" />
                      Add
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                {contacts.length === 0 ? (
                  <p className="text-sm text-slate-400 text-center py-3">
                    {t('empty.noContacts')}
                  </p>
                ) : (
                  <div className="space-y-2">
                    {contacts.slice(0, 3).map(contact => {
                      const isAnalyzing = !contact.analyzed_at && contact.profile_brief === "Analyse wordt uitgevoerd..."
                      const hasAnalysis = !!contact.analyzed_at && !!contact.profile_brief
                      
                      return (
                        <div 
                          key={contact.id} 
                          className={`flex items-center gap-2 p-2 rounded-lg transition-colors ${
                            isAnalyzing 
                              ? 'bg-amber-50 dark:bg-amber-900/20' 
                              : hasAnalysis
                                ? 'hover:bg-purple-50 dark:hover:bg-purple-900/20 cursor-pointer'
                                : 'bg-slate-50/50 dark:bg-slate-800/30'
                          }`}
                          onClick={() => {
                            if (hasAnalysis) {
                              setSelectedContact(contact)
                              setContactDetailOpen(true)
                            }
                          }}
                        >
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-medium text-xs flex-shrink-0 ${
                            isAnalyzing 
                              ? 'bg-amber-400' 
                              : 'bg-gradient-to-br from-purple-400 to-purple-600'
                          }`}>
                            {isAnalyzing ? (
                              <Loader2 className="w-4 h-4 animate-spin text-white" />
                            ) : (
                              contact.name.charAt(0).toUpperCase()
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
                              {contact.name}
                            </p>
                            <p className="text-xs text-slate-500 truncate">
                              {isAnalyzing ? (
                                <span className="text-amber-600 dark:text-amber-400">Analyzing...</span>
                              ) : (
                                contact.role || '—'
                              )}
                            </p>
                          </div>
                          {hasAnalysis && (
                            <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />
                          )}
                        </div>
                      )
                    })}
                    {contacts.length > 3 && (
                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={() => research && router.push(`/dashboard/research/${research.id}`)}
                        className="w-full h-7 text-xs text-slate-500"
                      >
                        +{contacts.length - 3} {t('more')}
                      </Button>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
            
            {/* QUICK NOTES */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">{t('sections.notes')}</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex gap-2 mb-3">
                  <Input
                    value={newNoteContent}
                    onChange={e => setNewNoteContent(e.target.value)}
                    placeholder={t('notes.placeholder')}
                    className="h-9 text-sm"
                    onKeyDown={e => e.key === 'Enter' && handleAddNote()}
                  />
                  <Button 
                    size="sm" 
                    className="h-9 px-3 bg-purple-600 hover:bg-purple-700"
                    onClick={handleAddNote}
                    disabled={!newNoteContent.trim() || savingNote}
                  >
                    {savingNote ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  </Button>
                </div>
                
                {notes.length === 0 ? (
                  <p className="text-sm text-slate-400 text-center py-4">
                    {t('notes.empty')}
                  </p>
                ) : (
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {notes.map(note => (
                      <div 
                        key={note.id} 
                        className={`p-2.5 rounded-lg text-sm group transition-colors ${
                          note.is_pinned 
                            ? 'bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/50' 
                            : 'bg-slate-50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-800'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-slate-700 dark:text-slate-300 flex-1">{note.content}</p>
                          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button 
                              onClick={() => handleTogglePin(note)}
                              className="p-1 hover:bg-slate-200 dark:hover:bg-slate-700 rounded"
                            >
                              {note.is_pinned ? (
                                <PinOff className="w-3.5 h-3.5 text-amber-500" />
                              ) : (
                                <Pin className="w-3.5 h-3.5 text-slate-400" />
                              )}
                            </button>
                            <button 
                              onClick={() => handleDeleteNote(note.id)}
                              className="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded"
                            >
                              <Trash2 className="w-3.5 h-3.5 text-slate-400 hover:text-red-500" />
                            </button>
                          </div>
                        </div>
                        <p className="text-xs text-slate-400 mt-1.5">{smartDate(note.created_at)}</p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
        
        {/* ============================================================ */}
        {/* HORIZONTAL TIMELINE */}
        {/* ============================================================ */}
        {timelineEvents.length > 0 && (
          <Card className="mt-6">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Calendar className="w-5 h-5 text-purple-500" />
                {t('sections.timeline')}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="flex items-start gap-4 overflow-x-auto pb-2 -mx-2 px-2">
                {timelineEvents.map((event, i) => (
                  <div 
                    key={event.id}
                    className="flex-shrink-0 flex flex-col items-center text-center"
                    style={{ minWidth: '120px' }}
                  >
                    {/* Connector line */}
                    <div className="flex items-center w-full mb-2">
                      <div className={`h-0.5 flex-1 ${i === 0 ? 'bg-transparent' : 'bg-purple-200 dark:bg-purple-800'}`} />
                      <div className="w-3 h-3 rounded-full bg-purple-500 flex-shrink-0 ring-4 ring-purple-100 dark:ring-purple-900/50" />
                      <div className={`h-0.5 flex-1 ${i === timelineEvents.length - 1 ? 'bg-transparent' : 'bg-purple-200 dark:bg-purple-800'}`} />
                    </div>
                    
                    <p className="text-xs font-medium text-slate-700 dark:text-slate-300 mb-0.5">
                      {event.title}
                    </p>
                    <p className="text-xs text-slate-400">
                      {smartDate(event.date)}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
        
        {/* ============================================================ */}
        {/* INLINE ACTION SHEETS (SPEC-041) */}
        {/* ============================================================ */}
        
        {/* Research Sheet */}
        <Sheet open={researchSheetOpen} onOpenChange={setResearchSheetOpen}>
          <SheetContent side="right" className="sm:max-w-md overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Search className="w-5 h-5 text-blue-600" />
                {t('sheets.startResearch')}
              </SheetTitle>
              <SheetDescription>
                {t('sheets.startResearchDesc')}
              </SheetDescription>
            </SheetHeader>
            <div className="mt-6">
              <ResearchForm
                initialCompanyName={prospect.company_name}
                initialCountry={prospect.country || ''}
                onSuccess={(_result) => {
                  setResearchSheetOpen(false)
                  toast({ title: t('toast.researchStarted') })
                  // Already on prospect hub, just refetch to show "In Progress"
                  refetchHubData()
                }}
                onCancel={() => setResearchSheetOpen(false)}
                isSheet={true}
              />
            </div>
          </SheetContent>
        </Sheet>
        
        {/* Preparation Sheet */}
        <Sheet open={prepSheetOpen} onOpenChange={setPrepSheetOpen}>
          <SheetContent side="right" className="sm:max-w-md overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-green-600" />
                {t('sheets.createPrep')}
              </SheetTitle>
              <SheetDescription>
                {t('sheets.createPrepDesc', { company: prospect.company_name })}
              </SheetDescription>
            </SheetHeader>
            <div className="mt-6">
              <PreparationForm
                initialCompanyName={prospect.company_name}
                initialContacts={contacts}
                initialDeals={deals}
                onSuccess={() => {
                  setPrepSheetOpen(false)
                  toast({ title: t('toast.prepStarted') })
                  refetchHubData()
                }}
                onCancel={() => setPrepSheetOpen(false)}
                isSheet={true}
              />
            </div>
          </SheetContent>
        </Sheet>
        
        {/* Follow-up Upload Sheet */}
        <Sheet open={followupSheetOpen} onOpenChange={setFollowupSheetOpen}>
          <SheetContent side="right" className="sm:max-w-md overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Mic className="w-5 h-5 text-orange-600" />
                {t('sheets.uploadFollowup')}
              </SheetTitle>
              <SheetDescription>
                {t('sheets.uploadFollowupDesc', { company: prospect.company_name })}
              </SheetDescription>
            </SheetHeader>
            <div className="mt-6">
              <FollowupUploadForm
                initialProspectCompany={prospect.company_name}
                initialContacts={contacts}
                initialDeals={deals}
                onSuccess={() => {
                  setFollowupSheetOpen(false)
                  toast({ title: t('toast.followupStarted') })
                  refetchHubData()
                }}
                onCancel={() => setFollowupSheetOpen(false)}
                isSheet={true}
              />
            </div>
          </SheetContent>
        </Sheet>
        
        {/* Contact Search Modal - Reuses existing component (SPEC-041 FR-6) */}
        {research && (
          <ContactSearchModal
            isOpen={contactModalOpen}
            onClose={() => setContactModalOpen(false)}
            companyName={prospect.company_name}
            companyLinkedInUrl={prospect.linkedin_url || undefined}
            researchId={research.id}
            onContactAdded={() => {
              setContactModalOpen(false)
              toast({ title: t('toast.contactAdded') })
              refetchHubData()
            }}
          />
        )}
        
        {/* Contact Detail Sheet - View contact analysis */}
        <Sheet open={contactDetailOpen} onOpenChange={setContactDetailOpen}>
          <SheetContent side="right" className="sm:max-w-lg overflow-y-auto">
            {selectedContact && (
              <>
                <SheetHeader>
                  <SheetTitle className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-400 to-purple-600 flex items-center justify-center text-white font-medium">
                      {selectedContact.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="text-lg">{selectedContact.name}</div>
                      {selectedContact.role && (
                        <div className="text-sm font-normal text-slate-500">{selectedContact.role}</div>
                      )}
                    </div>
                  </SheetTitle>
                </SheetHeader>
                
                <div className="mt-6 space-y-6">
                  {/* Contact Info */}
                  <div className="flex flex-wrap gap-3">
                    {selectedContact.email && (
                      <a href={`mailto:${selectedContact.email}`} className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
                        <Mail className="w-4 h-4" />
                        {selectedContact.email}
                      </a>
                    )}
                    {selectedContact.linkedin_url && (
                      <a href={selectedContact.linkedin_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
                        <Linkedin className="w-4 h-4" />
                        LinkedIn
                      </a>
                    )}
                  </div>
                  
                  {/* Communication Style & Authority */}
                  {(selectedContact.communication_style || selectedContact.decision_authority) && (
                    <div className="flex flex-wrap gap-2">
                      {selectedContact.communication_style && (
                        <Badge variant="secondary" className="bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300">
                          {selectedContact.communication_style}
                        </Badge>
                      )}
                      {selectedContact.decision_authority && (
                        <Badge variant="secondary" className="bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300">
                          {selectedContact.decision_authority.replace('_', ' ')}
                        </Badge>
                      )}
                    </div>
                  )}
                  
                  {/* Profile Brief - Rendered as Markdown */}
                  {selectedContact.profile_brief && (
                    <div>
                      <h4 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">
                        {t('contactDetail.profileBrief')}
                      </h4>
                      <div className="prose prose-sm prose-slate dark:prose-invert max-w-none bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            h1: ({ node, ...props }) => <h1 className="text-lg font-bold mb-2 text-slate-900 dark:text-white" {...props} />,
                            h2: ({ node, ...props }) => <h2 className="text-base font-bold mt-4 mb-2 text-slate-900 dark:text-white border-b border-slate-200 dark:border-slate-700 pb-1" {...props} />,
                            h3: ({ node, ...props }) => <h3 className="text-sm font-semibold mt-3 mb-1.5 text-slate-900 dark:text-white" {...props} />,
                            p: ({ node, ...props }) => <p className="mb-2 text-sm text-slate-700 dark:text-slate-300 leading-relaxed" {...props} />,
                            ul: ({ node, ...props }) => <ul className="list-disc list-inside mb-2 space-y-1 text-sm" {...props} />,
                            ol: ({ node, ...props }) => <ol className="list-decimal list-inside mb-2 space-y-1 text-sm" {...props} />,
                            li: ({ node, ...props }) => <li className="ml-2 text-slate-700 dark:text-slate-300" {...props} />,
                            strong: ({ node, ...props }) => <strong className="font-semibold text-slate-900 dark:text-white" {...props} />,
                            hr: ({ node, ...props }) => <hr className="my-3 border-slate-200 dark:border-slate-700" {...props} />,
                            table: ({ node, ...props }) => (
                              <div className="overflow-x-auto my-3 rounded-lg border border-slate-200 dark:border-slate-700">
                                <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700 text-sm" {...props} />
                              </div>
                            ),
                            thead: ({ node, ...props }) => <thead className="bg-slate-100 dark:bg-slate-700/50" {...props} />,
                            tbody: ({ node, ...props }) => <tbody className="divide-y divide-slate-200 dark:divide-slate-700 bg-white dark:bg-slate-800" {...props} />,
                            tr: ({ node, ...props }) => <tr {...props} />,
                            th: ({ node, ...props }) => <th className="px-3 py-2 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider" {...props} />,
                            td: ({ node, ...props }) => <td className="px-3 py-2 text-slate-700 dark:text-slate-300 whitespace-normal" {...props} />,
                          }}
                        >
                          {selectedContact.profile_brief}
                        </ReactMarkdown>
                      </div>
                    </div>
                  )}
                  
                  {/* Opening Suggestions */}
                  {selectedContact.opening_suggestions && selectedContact.opening_suggestions.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">
                        {t('contactDetail.openingSuggestions')}
                      </h4>
                      <ul className="space-y-2">
                        {selectedContact.opening_suggestions.map((suggestion, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-400">
                            <Lightbulb className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
                            {suggestion}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {/* Questions to Ask */}
                  {selectedContact.questions_to_ask && selectedContact.questions_to_ask.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">
                        {t('contactDetail.questionsToAsk')}
                      </h4>
                      <ul className="space-y-2">
                        {selectedContact.questions_to_ask.map((question, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-400">
                            <span className="text-blue-500">?</span>
                            {question}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {/* Topics to Avoid */}
                  {selectedContact.topics_to_avoid && selectedContact.topics_to_avoid.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-slate-900 dark:text-white mb-2 text-red-600 dark:text-red-400">
                        {t('contactDetail.topicsToAvoid')}
                      </h4>
                      <ul className="space-y-2">
                        {selectedContact.topics_to_avoid.map((topic, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm text-red-600 dark:text-red-400">
                            <span>⚠️</span>
                            {topic}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </>
            )}
          </SheetContent>
        </Sheet>
      </div>
    </DashboardLayout>
  )
}

// ============================================================
// Sub Components
// ============================================================

interface DocumentRowProps {
  icon: React.ReactNode
  label: string
  status: 'completed' | 'in_progress' | 'empty'
  statusLabel?: string  // Label for in_progress status
  date?: string
  count?: number
  onClick?: () => void
  actionLabel?: string
  onAction?: () => void
}

function DocumentRow({ icon, label, status, statusLabel, date, count, onClick, actionLabel, onAction }: DocumentRowProps) {
  return (
    <div 
      className={`flex items-center justify-between p-3 rounded-lg transition-colors ${
        status === 'completed' 
          ? 'bg-green-50 dark:bg-green-900/20 hover:bg-green-100 dark:hover:bg-green-900/30 cursor-pointer' 
          : status === 'in_progress'
            ? 'bg-blue-50 dark:bg-blue-900/20'
            : 'bg-slate-50 dark:bg-slate-800/50'
      }`}
      onClick={status === 'completed' ? onClick : undefined}
    >
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${
          status === 'completed' 
            ? 'bg-green-100 dark:bg-green-900/40 text-green-600 dark:text-green-400' 
            : status === 'in_progress'
              ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400'
              : 'bg-slate-200 dark:bg-slate-700 text-slate-400'
        }`}>
          {icon}
        </div>
        <div>
          <p className={`text-sm font-medium ${
            status === 'completed' 
              ? 'text-slate-900 dark:text-white' 
              : status === 'in_progress'
                ? 'text-blue-700 dark:text-blue-300'
                : 'text-slate-500 dark:text-slate-400'
          }`}>
            {label}
            {count !== undefined && count > 0 && (
              <span className="ml-1.5 text-slate-400 font-normal">({count})</span>
            )}
          </p>
          {date && (
            <p className="text-xs text-slate-400">{smartDate(date)}</p>
          )}
        </div>
      </div>
      
      <div className="flex items-center gap-2">
        {status === 'completed' && (
          <>
            <CheckCircle2 className="w-4 h-4 text-green-500" />
            {actionLabel && onAction ? (
              <Button 
                variant="ghost" 
                size="sm"
                className="h-7 text-xs text-green-700 dark:text-green-400 hover:bg-green-100 dark:hover:bg-green-900/40"
                onClick={(e) => {
                  e.stopPropagation()
                  onAction()
                }}
              >
                {actionLabel}
                <ChevronRight className="w-3 h-3 ml-1" />
              </Button>
            ) : (
              <ChevronRight className="w-4 h-4 text-slate-400" />
            )}
          </>
        )}
        {status === 'in_progress' && (
          <span className="flex items-center gap-1.5 text-xs font-medium text-blue-600 dark:text-blue-400">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            {statusLabel || 'In Progress'}
          </span>
        )}
        {status === 'empty' && actionLabel && onAction && (
          <Button 
            variant="outline" 
            size="sm"
            onClick={(e) => {
              e.stopPropagation()
              onAction()
            }}
          >
            <Plus className="w-3 h-3 mr-1" />
            {actionLabel}
          </Button>
        )}
        {status === 'empty' && !onAction && (
          <Circle className="w-4 h-4 text-slate-300 dark:text-slate-600" />
        )}
      </div>
    </div>
  )
}

// Document Section with expandable inline items
interface DocumentSectionProps {
  icon: React.ReactNode
  label: string
  items: Array<{ id: string; created_at: string; completed_at?: string }>
  createLabel: string
  onCreate: () => void
  onItemClick: (id: string) => void
  getItemTitle: (item: { id: string; created_at: string; completed_at?: string }) => string
  getItemStatus: (item: { id: string; created_at: string; completed_at?: string }) => string
  getItemDate: (item: { id: string; created_at: string; completed_at?: string }) => string
}

function DocumentSection({ 
  icon, 
  label, 
  items, 
  createLabel, 
  onCreate, 
  onItemClick, 
  getItemTitle, 
  getItemStatus,
  getItemDate 
}: DocumentSectionProps) {
  const hasItems = items.length > 0
  const completedItems = items.filter(i => getItemStatus(i) === 'completed')
  const inProgressItems = items.filter(i => getItemStatus(i) !== 'completed' && getItemStatus(i) !== 'failed')
  
  return (
    <div className={`rounded-lg overflow-hidden ${
      hasItems 
        ? 'bg-green-50 dark:bg-green-900/20' 
        : 'bg-slate-50 dark:bg-slate-800/50'
    }`}>
      {/* Header row */}
      <div className="flex items-center justify-between p-3">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${
            hasItems 
              ? 'bg-green-100 dark:bg-green-900/40 text-green-600 dark:text-green-400' 
              : 'bg-slate-200 dark:bg-slate-700 text-slate-400'
          }`}>
            {icon}
          </div>
          <div>
            <p className={`text-sm font-medium ${
              hasItems 
                ? 'text-slate-900 dark:text-white' 
                : 'text-slate-500 dark:text-slate-400'
            }`}>
              {label}
              {hasItems && (
                <span className="ml-1.5 text-slate-400 font-normal">({items.length})</span>
              )}
            </p>
          </div>
        </div>
        
        <Button 
          variant="outline" 
          size="sm"
          onClick={(e) => {
            e.stopPropagation()
            onCreate()
          }}
          className={hasItems ? 'bg-white dark:bg-slate-800' : ''}
        >
          <Plus className="w-3 h-3 mr-1" />
          {createLabel}
        </Button>
      </div>
      
      {/* Inline items list */}
      {hasItems && (
        <div className="px-3 pb-3 space-y-1.5">
          {items.slice(0, 5).map((item) => {
            const status = getItemStatus(item)
            const isCompleted = status === 'completed'
            const isInProgress = status !== 'completed' && status !== 'failed'
            const isFailed = status === 'failed'
            
            return (
              <div
                key={item.id}
                onClick={() => isCompleted && onItemClick(item.id)}
                className={`flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors ${
                  isCompleted 
                    ? 'bg-white dark:bg-slate-800 hover:bg-green-100 dark:hover:bg-green-900/40 cursor-pointer' 
                    : isInProgress
                      ? 'bg-blue-100/50 dark:bg-blue-900/30'
                      : 'bg-red-100/50 dark:bg-red-900/30'
                }`}
              >
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  {isCompleted && <CheckCircle2 className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />}
                  {isInProgress && <Loader2 className="w-3.5 h-3.5 text-blue-500 animate-spin flex-shrink-0" />}
                  {isFailed && <Circle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />}
                  <span className={`truncate ${
                    isCompleted 
                      ? 'text-slate-700 dark:text-slate-200' 
                      : isInProgress 
                        ? 'text-blue-700 dark:text-blue-300'
                        : 'text-red-600 dark:text-red-400'
                  }`}>
                    {getItemTitle(item)}
                  </span>
                </div>
                <div className="flex items-center gap-2 ml-2 flex-shrink-0">
                  <span className="text-xs text-slate-400">
                    {smartDate(getItemDate(item))}
                  </span>
                  {isCompleted && <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
                </div>
              </div>
            )
          })}
          {items.length > 5 && (
            <p className="text-xs text-slate-400 text-center py-1">
              +{items.length - 5} more
            </p>
          )}
        </div>
      )}
    </div>
  )
}
