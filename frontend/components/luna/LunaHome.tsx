'use client'

/**
 * Luna Home Component
 * SPEC-046-Luna-Unified-AI-Assistant
 * 
 * The main Luna home page with:
 * - Contextual greeting
 * - Action messages with tabs
 * - Context sidebar (meetings, stats, tip)
 */

import React, { useState, useMemo, useCallback } from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import {
  Sparkles,
  Search,
  FileText,
  Mic,
  Settings,
  Calendar,
  CheckCircle2,
  Clock,
  Lightbulb,
  RefreshCw,
  ChevronRight,
  StickyNote,
} from 'lucide-react'
import { useLuna } from './LunaProvider'
import { MessageCardWithInline, MessageListWithInline } from './MessageCard'
import { OutreachOptionsSheet, type OutreachChannel } from './OutreachOptionsSheet'
import { AINotetakerSheet } from '@/components/ai-notetaker/ai-notetaker-sheet'
import type { LunaMessage, UpcomingMeeting } from '@/types/luna'

// =============================================================================
// LUNA GREETING
// =============================================================================

function LunaGreeting() {
  const t = useTranslations('luna')
  const tHome = useTranslations('lunaHome')
  const { greeting, counts, isLoading } = useLuna()
  
  if (isLoading || !greeting) {
    return <Skeleton className="h-24 w-full rounded-xl" />
  }
  
  const hasUrgent = counts.urgent > 0
  const hasPending = counts.pending > 0
  
  return (
    <Card className={`border-0 shadow-sm ${hasUrgent ? 'bg-gradient-to-r from-orange-50 to-amber-50 dark:from-orange-950/20 dark:to-amber-950/20' : 'bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-950/20 dark:to-purple-950/20'}`}>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className={`p-3 rounded-full ${hasUrgent ? 'bg-orange-100 dark:bg-orange-900/30' : 'bg-indigo-100 dark:bg-indigo-900/30'}`}>
              <Sparkles className={`w-6 h-6 ${hasUrgent ? 'text-orange-500' : 'text-indigo-500'}`} />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Luna</h2>
                {greeting.emphasis && (
                  <Badge variant={hasUrgent ? 'destructive' : 'secondary'}>
                    {greeting.emphasis}
                  </Badge>
                )}
              </div>
              <p className="text-gray-600 dark:text-gray-400 max-w-xl">
                {greeting.message}
              </p>
              {greeting.action && greeting.actionRoute && (
                <Button variant="link" className="p-0 h-auto mt-2 text-indigo-600" asChild>
                  <a href={greeting.actionRoute}>
                    {greeting.action}
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </a>
                </Button>
              )}
            </div>
          </div>
          {hasPending && (
            <div className="text-right">
              <Badge variant={hasUrgent ? 'destructive' : 'secondary'} className="text-lg px-3 py-1">
                {counts.pending} {t('pending')}
              </Badge>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// =============================================================================
// QUICK ACTIONS
// =============================================================================

interface QuickAction {
  icon: React.ReactNode
  label: string
  href: string
  color: string
}

interface QuickActionsProps {
  onOpenAINotetaker: () => void
}

function QuickActions({ onOpenAINotetaker }: QuickActionsProps) {
  const t = useTranslations('lunaHome')
  
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-gray-500 dark:text-gray-400">
          {t('quickStart')}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="flex gap-2">
          <Button
            variant="ghost"
            className="flex-1 flex flex-col items-center gap-1 h-auto py-3 text-blue-500 bg-blue-50 hover:bg-blue-100 dark:bg-blue-950/30 dark:hover:bg-blue-900/40"
            asChild
          >
            <a href="/dashboard/research">
              <Search className="w-5 h-5" />
              <span className="text-xs">{t('quickActions.research')}</span>
            </a>
          </Button>
          <Button
            variant="ghost"
            className="flex-1 flex flex-col items-center gap-1 h-auto py-3 text-indigo-500 bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/30 dark:hover:bg-indigo-900/40"
            asChild
          >
            <a href="/dashboard/preparation">
              <FileText className="w-5 h-5" />
              <span className="text-xs">{t('quickActions.prep')}</span>
            </a>
          </Button>
          <Button
            variant="ghost"
            className="flex-1 flex flex-col items-center gap-1 h-auto py-3 text-rose-500 bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/30 dark:hover:bg-rose-900/40"
            asChild
          >
            <a href="/dashboard/recordings">
              <Mic className="w-5 h-5" />
              <span className="text-xs">{t('quickActions.record')}</span>
            </a>
          </Button>
          <Button
            variant="ghost"
            onClick={onOpenAINotetaker}
            className="flex-1 flex flex-col items-center gap-1 h-auto py-3 text-amber-500 bg-amber-50 hover:bg-amber-100 dark:bg-amber-950/30 dark:hover:bg-amber-900/40"
          >
            <StickyNote className="w-5 h-5" />
            <span className="text-xs">AI Notetaker</span>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

// =============================================================================
// TODAY'S MEETINGS
// =============================================================================

function TodaysMeetings() {
  const t = useTranslations('lunaHome')
  const { upcomingMeetings, isLoading } = useLuna()
  
  if (isLoading) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-gray-500 dark:text-gray-400 flex items-center gap-2">
            <Calendar className="w-4 h-4" />
            {t('todaysMeetings')}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0 space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </CardContent>
      </Card>
    )
  }
  
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-gray-500 dark:text-gray-400 flex items-center gap-2">
          <Calendar className="w-4 h-4" />
          {t('todaysMeetings')}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        {upcomingMeetings.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
            {t('noMeetingsToday')}
          </p>
        ) : (
          <div className="space-y-2">
            {upcomingMeetings.map((meeting) => (
              <MeetingItem key={meeting.id} meeting={meeting} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function MeetingItem({ meeting }: { meeting: UpcomingMeeting }) {
  const startTime = new Date(meeting.startTime)
  const timeStr = startTime.toLocaleTimeString('nl-NL', {
    hour: '2-digit',
    minute: '2-digit',
  })
  
  return (
    <a
      href={meeting.prepId ? `/dashboard/preparation/${meeting.prepId}` : `/dashboard/meetings`}
      className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
    >
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-gray-900 dark:text-gray-100 w-12">
          {timeStr}
        </span>
        <div>
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100 line-clamp-1">
            {meeting.title}
          </p>
          {meeting.company && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {meeting.company}
            </p>
          )}
        </div>
      </div>
      <Badge variant={meeting.hasPrep ? 'default' : 'outline'} className="text-xs">
        {meeting.hasPrep ? (
          <CheckCircle2 className="w-3 h-3 mr-1" />
        ) : (
          <Clock className="w-3 h-3 mr-1" />
        )}
        {meeting.hasPrep ? 'Prep ✓' : 'No prep'}
      </Badge>
    </a>
  )
}

// =============================================================================
// THIS WEEK'S STATS
// =============================================================================

function ThisWeekStats() {
  const t = useTranslations('lunaHome')
  const { stats, isLoading } = useLuna()
  
  if (isLoading || !stats) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-gray-500 dark:text-gray-400">
            {t('thisWeek')}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    )
  }
  
  const statItems = [
    { label: t('stats.research'), value: stats.week.researchCompleted, icon: '🔍' },
    { label: t('stats.preps'), value: stats.week.prepsCompleted, icon: '📋' },
    { label: t('stats.followups'), value: stats.week.followupsCompleted, icon: '✉️' },
  ]
  
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-gray-500 dark:text-gray-400">
          {t('thisWeek')}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-2">
          {statItems.map((item, i) => (
            <div key={i} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg">{item.icon}</span>
                <span className="text-sm text-gray-600 dark:text-gray-400">{item.label}</span>
              </div>
              <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                {item.value}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

// =============================================================================
// TODAY'S STATS
// =============================================================================

function TodaysStats() {
  const t = useTranslations('lunaHome')
  const { stats, isLoading } = useLuna()
  
  if (isLoading || !stats) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-gray-500 dark:text-gray-400">
            {t('today')}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    )
  }
  
  const statItems = [
    { label: t('stats.research'), value: stats.today.researchCompleted, icon: '🔍' },
    { label: t('stats.preps'), value: stats.today.prepsCompleted, icon: '📋' },
    { label: t('stats.followups'), value: stats.today.followupsCompleted, icon: '✉️' },
    { label: t('stats.outreach'), value: stats.today.outreachSent, icon: '📤' },
  ]
  
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-gray-500 dark:text-gray-400 flex items-center justify-between">
          <span>{t('today')}</span>
          <div className="flex gap-2">
            <span className="text-lg font-bold text-gray-900 dark:text-gray-100">
              {stats.completedToday}
            </span>
            <span className="text-gray-400">{t('completed')}</span>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="grid grid-cols-4 gap-2">
          {statItems.map((item, i) => (
            <div key={i} className="text-center">
              <div className="text-2xl mb-1">{item.icon}</div>
              <div className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {item.value}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                {item.label}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

// =============================================================================
// TIP OF DAY
// =============================================================================

function TipOfDay() {
  const t = useTranslations('lunaHome')
  const { tip, isLoading } = useLuna()
  
  if (isLoading || !tip) {
    return null
  }
  
  return (
    <Card className="bg-amber-50/50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-amber-700 dark:text-amber-400 flex items-center gap-2">
          <Lightbulb className="w-4 h-4" />
          {t('tipOfDay')}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <p className="text-sm text-amber-800 dark:text-amber-300">
          {tip.content}
        </p>
      </CardContent>
    </Card>
  )
}

// =============================================================================
// CONTEXT SIDEBAR
// =============================================================================

interface ContextSidebarProps {
  onOpenSettings: () => void
  onOpenAINotetaker: () => void
}

function ContextSidebar({ onOpenSettings, onOpenAINotetaker }: ContextSidebarProps) {
  const t = useTranslations('lunaHome')
  
  return (
    <div className="space-y-4">
      <QuickActions onOpenAINotetaker={onOpenAINotetaker} />
      <TodaysMeetings />
      <ThisWeekStats />
      <TodaysStats />
      <TipOfDay />
      
      {/* Settings Link */}
      <Button
        variant="ghost"
        className="w-full justify-start text-gray-500"
        onClick={onOpenSettings}
      >
        <Settings className="w-4 h-4 mr-2" />
        {t('settings')}
      </Button>
    </div>
  )
}

// =============================================================================
// MESSAGE INBOX
// =============================================================================

// Inline action data types
interface OutreachActionData {
  sheet: 'outreach_options'
  prospectId: string
  contactId: string
  researchId?: string
  channels: OutreachChannel[]
}

function MessageInbox() {
  const t = useTranslations('lunaHome')
  const tLuna = useTranslations('luna')
  const { messages, counts, refreshMessages, isLoading } = useLuna()
  const [activeTab, setActiveTab] = useState<'active' | 'new' | 'in_progress' | 'history'>('active')
  
  // State for inline sheets
  const [outreachSheetOpen, setOutreachSheetOpen] = useState(false)
  const [outreachActionData, setOutreachActionData] = useState<OutreachActionData | null>(null)
  
  // Handle inline action - open appropriate sheet
  const handleInlineAction = useCallback((message: LunaMessage) => {
    const actionData = message.actionData as Record<string, unknown> | null
    if (!actionData) return
    
    const sheetType = actionData.sheet as string | undefined
    
    if (sheetType === 'outreach_options') {
      setOutreachActionData({
        sheet: 'outreach_options',
        prospectId: actionData.prospectId as string || actionData.prospect_id as string || '',
        contactId: actionData.contactId as string || actionData.contact_id as string || '',
        researchId: actionData.researchId as string || actionData.research_id as string || undefined,
        channels: (actionData.channels as OutreachChannel[]) || ['linkedin_connect', 'linkedin_message', 'email'],
      })
      setOutreachSheetOpen(true)
    }
    // TODO: Add handlers for other inline sheets (schedule_meeting, summary_review, etc.)
  }, [])
  
  // Handle sheet completion
  const handleOutreachComplete = useCallback(() => {
    setOutreachSheetOpen(false)
    setOutreachActionData(null)
    refreshMessages()
  }, [refreshMessages])
  
  // Filter messages by tab
  const filteredMessages = useMemo(() => {
    switch (activeTab) {
      case 'active':
        return messages.filter(m => m.status === 'pending' || m.status === 'executing')
      case 'new':
        return messages.filter(m => m.status === 'pending' && !m.viewedAt)
      case 'in_progress':
        return messages.filter(m => m.status === 'executing')
      case 'history':
        return messages.filter(m => 
          m.status === 'completed' || m.status === 'dismissed' || m.status === 'expired'
        )
      default:
        return messages
    }
  }, [messages, activeTab])
  
  const newCount = messages.filter(m => m.status === 'pending' && !m.viewedAt).length
  const activeCount = messages.filter(m => m.status === 'pending' || m.status === 'executing').length
  const inProgressCount = messages.filter(m => m.status === 'executing').length
  const historyCount = messages.filter(m => 
    m.status === 'completed' || m.status === 'dismissed' || m.status === 'expired'
  ).length
  
  return (
    <>
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-indigo-500" />
              {t('inbox')}
              {counts.pending > 0 && (
                <Badge variant="secondary">{counts.pending} {tLuna('pending')}</Badge>
              )}
            </CardTitle>
            <Button variant="ghost" size="icon" onClick={refreshMessages}>
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
            <TabsList className="w-full grid grid-cols-4 mb-4">
              <TabsTrigger value="active" className="text-xs">
                {t('tabs.active')}
                {activeCount > 0 && (
                  <Badge variant="secondary" className="ml-1 text-xs">{activeCount}</Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="new" className="text-xs">
                {t('tabs.new')}
                {newCount > 0 && (
                  <Badge variant="destructive" className="ml-1 text-xs">{newCount}</Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="in_progress" className="text-xs">
                {t('tabs.inProgress')}
                {inProgressCount > 0 && (
                  <Badge variant="secondary" className="ml-1 text-xs">{inProgressCount}</Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="history" className="text-xs">
                {t('tabs.history')}
                {historyCount > 0 && (
                  <Badge variant="outline" className="ml-1 text-xs">{historyCount}</Badge>
                )}
              </TabsTrigger>
            </TabsList>
            
            <TabsContent value={activeTab} className="mt-0">
              {isLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-24 w-full" />
                  <Skeleton className="h-24 w-full" />
                  <Skeleton className="h-24 w-full" />
                </div>
              ) : (
                <MessageListWithInline
                  messages={filteredMessages}
                  surface="home"
                  onInlineAction={handleInlineAction}
                  emptyMessage={
                    activeTab === 'active'
                      ? t('noActiveActions')
                      : activeTab === 'new'
                      ? t('noNewActions')
                      : activeTab === 'in_progress'
                      ? t('noInProgressActions')
                      : t('noHistoryActions')
                  }
                />
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
      
      {/* Outreach Options Sheet */}
      <OutreachOptionsSheet
        open={outreachSheetOpen}
        onOpenChange={setOutreachSheetOpen}
        actionData={outreachActionData}
        onComplete={handleOutreachComplete}
      />
    </>
  )
}

// =============================================================================
// LUNA SETTINGS
// =============================================================================

function LunaSettingsSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const t = useTranslations('lunaHome')
  const { settings, updateSettings } = useLuna()
  
  if (!settings) return null
  
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{t('settingsTitle')}</SheetTitle>
        </SheetHeader>
        <div className="mt-6 space-y-6">
          {/* TODO: Add settings controls */}
          <p className="text-sm text-gray-500">
            {t('settingsDescription')}
          </p>
        </div>
      </SheetContent>
    </Sheet>
  )
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function LunaHome() {
  const { isLoading, isEnabled } = useLuna()
  const [showSettings, setShowSettings] = useState(false)
  const [aiNotetakerSheetOpen, setAiNotetakerSheetOpen] = useState(false)
  
  if (isLoading) {
    return <LunaHomeSkeleton />
  }
  
  if (!isEnabled) {
    // Fallback to old autopilot if Luna is disabled
    return null
  }
  
  return (
    <>
      <div className="max-w-7xl mx-auto">
        {/* Luna Greeting */}
        <div className="mb-6">
          <LunaGreeting />
        </div>
        
        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Message Inbox - Takes 2 columns */}
          <div className="lg:col-span-2">
            <MessageInbox />
          </div>
          
          {/* Context Sidebar */}
          <div className="lg:col-span-1">
            <ContextSidebar 
              onOpenSettings={() => setShowSettings(true)}
              onOpenAINotetaker={() => setAiNotetakerSheetOpen(true)}
            />
          </div>
        </div>
      </div>
      
      {/* Settings Sheet */}
      <LunaSettingsSheet open={showSettings} onOpenChange={setShowSettings} />
      
      {/* AI Notetaker Sheet */}
      <AINotetakerSheet
        open={aiNotetakerSheetOpen}
        onOpenChange={setAiNotetakerSheetOpen}
      />
    </>
  )
}

// =============================================================================
// SKELETON
// =============================================================================

function LunaHomeSkeleton() {
  return (
    <div className="max-w-7xl mx-auto">
      {/* Greeting Skeleton */}
      <div className="mb-6">
        <Skeleton className="h-24 w-full rounded-xl" />
      </div>
      
      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Inbox Skeleton */}
        <div className="lg:col-span-2 space-y-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
        
        {/* Sidebar Skeleton */}
        <div className="lg:col-span-1 space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
    </div>
  )
}
