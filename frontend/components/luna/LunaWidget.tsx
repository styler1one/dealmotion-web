'use client'

/**
 * Luna Floating Widget Component
 * SPEC-046-Luna-Unified-AI-Assistant
 * 
 * Floating widget that shows Luna status and pending messages.
 * Three states: minimized, compact, expanded.
 */

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sparkles,
  X,
  ChevronUp,
  ChevronDown,
  ChevronRight,
  Clock,
  FileText,
  Search,
  Mail,
  MessageSquare,
  Calendar,
  CheckCircle2,
  RefreshCw,
  Loader2,
} from 'lucide-react'
import { useLunaOptional, useLuna } from './LunaProvider'

// =============================================================================
// WIDGET STATES
// =============================================================================

type WidgetState = 'minimized' | 'compact' | 'expanded'

// =============================================================================
// ICON MAPPING (for widget)
// =============================================================================

const MESSAGE_ICONS: Record<string, React.ReactNode> = {
  start_research: <Search className="w-4 h-4" />,
  review_research: <FileText className="w-4 h-4" />,
  prepare_outreach: <MessageSquare className="w-4 h-4" />,
  first_touch_sent: <CheckCircle2 className="w-4 h-4" />,
  suggest_meeting_creation: <Calendar className="w-4 h-4" />,
  create_prep: <FileText className="w-4 h-4" />,
  prep_ready: <CheckCircle2 className="w-4 h-4" />,
  review_meeting_summary: <FileText className="w-4 h-4" />,
  review_customer_report: <FileText className="w-4 h-4" />,
  send_followup_email: <Mail className="w-4 h-4" />,
  create_action_items: <CheckCircle2 className="w-4 h-4" />,
  update_crm_notes: <RefreshCw className="w-4 h-4" />,
}

// =============================================================================
// LUNA WIDGET
// =============================================================================

export function LunaWidget() {
  const router = useRouter()
  const t = useTranslations('luna')
  const luna = useLunaOptional()
  
  const [widgetState, setWidgetState] = useState<WidgetState>('compact')
  
  // Don't render if Luna is not available or not enabled
  if (!luna || !luna.isEnabled || !luna.featureFlags?.lunaWidgetEnabled) {
    return null
  }
  
  const { messages, counts, greeting } = luna
  const pendingMessages = messages.filter(m => m.status === 'pending')
  const hasUrgent = counts.urgent > 0
  
  // ==========================================================================
  // MINIMIZED STATE
  // ==========================================================================
  
  if (widgetState === 'minimized') {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <Button
          size="icon"
          onClick={() => setWidgetState('compact')}
          className={`rounded-full w-14 h-14 shadow-lg ${
            hasUrgent ? 'bg-orange-500 hover:bg-orange-600' : 'bg-indigo-500 hover:bg-indigo-600'
          }`}
        >
          <Sparkles className="w-6 h-6" />
          {counts.pending > 0 && (
            <Badge
              className="absolute -top-1 -right-1 h-5 min-w-5 flex items-center justify-center text-xs"
              variant={hasUrgent ? 'destructive' : 'secondary'}
            >
              {counts.pending}
            </Badge>
          )}
        </Button>
      </div>
    )
  }
  
  // ==========================================================================
  // COMPACT STATE
  // ==========================================================================
  
  if (widgetState === 'compact') {
    return (
      <Card className="fixed bottom-4 right-4 z-50 w-80 shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b">
          <div className="flex items-center gap-2">
            <div className={`p-1.5 rounded-full ${hasUrgent ? 'bg-orange-100' : 'bg-indigo-100'}`}>
              <Sparkles className={`w-4 h-4 ${hasUrgent ? 'text-orange-500' : 'text-indigo-500'}`} />
            </div>
            <span className="font-medium text-sm">Luna</span>
            {counts.pending > 0 && (
              <Badge variant={hasUrgent ? 'destructive' : 'secondary'} className="text-xs">
                {counts.pending}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setWidgetState('expanded')}
              className="h-7 w-7"
            >
              <ChevronUp className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setWidgetState('minimized')}
              className="h-7 w-7"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>
        
        {/* Greeting */}
        {greeting && (
          <div className="p-3">
            <p className="text-sm text-gray-600">{greeting.message}</p>
          </div>
        )}
        
        {/* Quick Action */}
        {pendingMessages.length > 0 && (
          <div className="px-3 pb-3">
            <Button
              className="w-full"
              onClick={() => router.push('/dashboard')}
            >
              {t('viewActions')}
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        )}
      </Card>
    )
  }
  
  // ==========================================================================
  // EXPANDED STATE
  // ==========================================================================
  
  return (
    <Card className="fixed bottom-4 right-4 z-50 w-[420px] max-h-[75vh] shadow-2xl flex flex-col border-0 bg-white dark:bg-slate-900">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-800 shrink-0 bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-950/20 dark:to-purple-950/20">
        <div className="flex items-center gap-2.5">
          <div className={`p-2 rounded-lg ${hasUrgent ? 'bg-orange-100 dark:bg-orange-900/30' : 'bg-indigo-100 dark:bg-indigo-900/30'}`}>
            <Sparkles className={`w-4 h-4 ${hasUrgent ? 'text-orange-600 dark:text-orange-400' : 'text-indigo-600 dark:text-indigo-400'}`} />
          </div>
          <div>
            <span className="font-semibold text-slate-900 dark:text-white text-sm">Luna</span>
            {counts.pending > 0 && (
              <div className="flex items-center gap-1.5 mt-0.5">
                <Badge variant={hasUrgent ? 'destructive' : 'secondary'} className="text-xs px-1.5 py-0 h-5">
                  {counts.pending} {t('pending')}
                </Badge>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setWidgetState('compact')}
            className="h-8 w-8 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
          >
            <ChevronDown className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setWidgetState('minimized')}
            className="h-8 w-8 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>
      </div>
      
      {/* Messages - Scrollable */}
      <div className="flex-1 overflow-y-auto overscroll-contain">
        {pendingMessages.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
            <div className="w-16 h-16 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center mb-3">
              <Sparkles className="w-8 h-8 text-indigo-500 dark:text-indigo-400" />
            </div>
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">{t('allCaughtUp')}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">{t('noMessages')}</p>
          </div>
        ) : (
          <div className="p-3 space-y-2.5">
            {pendingMessages.map(message => (
              <WidgetMessageCard
                key={message.id}
                message={message}
                onAction={() => router.push('/dashboard')}
              />
            ))}
          </div>
        )}
      </div>
      
      {/* Footer */}
      {pendingMessages.length > 0 && (
        <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-800 shrink-0 bg-slate-50/50 dark:bg-slate-800/50">
          <Button
            variant="default"
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
            onClick={() => router.push('/dashboard')}
          >
            {t('openLunaHome')}
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      )}
    </Card>
  )
}

// =============================================================================
// WIDGET MESSAGE CARD (Compact, optimized for widget)
// =============================================================================

interface WidgetMessageCardProps {
  message: import('@/types/luna').LunaMessage
  onAction: () => void
}

function WidgetMessageCard({ message, onAction }: WidgetMessageCardProps) {
  const router = useRouter()
  const t = useTranslations('luna')
  const { acceptMessage, dismissMessage, snoozeMessage, markMessageShown } = useLuna()
  
  const [isActing, setIsActing] = useState(false)
  const [hasMarkedShown, setHasMarkedShown] = useState(false)
  
  // Mark as shown on first render
  useEffect(() => {
    if (!hasMarkedShown) {
      markMessageShown(message.id, 'widget')
      setHasMarkedShown(true)
    }
  }, [message.id, markMessageShown, hasMarkedShown])
  
  const handleAccept = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setIsActing(true)
    try {
      // For inline actions, navigate to dashboard to handle
      if (message.actionType === 'inline') {
        onAction()
        setIsActing(false)
        return
      }
      
      await acceptMessage(message.id)
      
      // Navigate if action type is navigate
      if (message.actionType === 'navigate' && message.actionRoute) {
        router.push(message.actionRoute)
      } else {
        onAction()
      }
    } catch {
      setIsActing(false)
    }
  }
  
  const handleDismiss = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setIsActing(true)
    try {
      await dismissMessage(message.id)
    } catch {
      setIsActing(false)
    }
  }
  
  const handleSnooze = async (option: import('@/types/luna').SnoozeOption) => {
    setIsActing(true)
    try {
      await snoozeMessage(message.id, option)
    } catch {
      setIsActing(false)
    }
  }
  
  const isUrgent = message.priority >= 80
  const isExecuting = message.status === 'executing'
  
  // Get icon and color based on message type
  const getIconConfig = () => {
    if (message.messageType.includes('research')) {
      return { icon: <Search className="w-4 h-4" />, color: 'text-blue-600 dark:text-blue-400' }
    }
    if (message.messageType.includes('prep')) {
      return { icon: <FileText className="w-4 h-4" />, color: 'text-indigo-600 dark:text-indigo-400' }
    }
    if (message.messageType.includes('followup') || message.messageType.includes('email')) {
      return { icon: <Mail className="w-4 h-4" />, color: 'text-orange-600 dark:text-orange-400' }
    }
    if (message.messageType.includes('outreach')) {
      return { icon: <MessageSquare className="w-4 h-4" />, color: 'text-purple-600 dark:text-purple-400' }
    }
    const defaultIcon = MESSAGE_ICONS[message.messageType] || <FileText className="w-4 h-4" />
    return { icon: defaultIcon, color: 'text-slate-600 dark:text-slate-400' }
  }
  
  const { icon, color: iconColor } = getIconConfig()
  
  return (
    <div
      className={`
        group relative rounded-lg border transition-all cursor-pointer
        ${isUrgent 
          ? 'border-orange-200 dark:border-orange-800 bg-orange-50/50 dark:bg-orange-950/20 hover:border-orange-300 dark:hover:border-orange-700 hover:shadow-md' 
          : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300 dark:hover:border-slate-700 hover:shadow-sm'
        }
      `}
      onClick={handleAccept}
    >
      <div className="p-3">
        {/* Header Row */}
        <div className="flex items-start gap-3 mb-2">
          {/* Icon */}
          <div className={`flex-shrink-0 mt-0.5 p-1.5 rounded-md bg-slate-100 dark:bg-slate-800 ${iconColor}`}>
            {icon}
          </div>
          
          {/* Title and Badges */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2 mb-1">
              <h4 className="font-semibold text-sm text-slate-900 dark:text-white leading-tight line-clamp-2">
                {message.title}
              </h4>
              <div className="flex items-center gap-1 flex-shrink-0">
                {isUrgent && (
                  <Badge variant="destructive" className="text-[10px] px-1.5 py-0 h-4">
                    {t('urgent')}
                  </Badge>
                )}
                {isExecuting && (
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4">
                    <Loader2 className="w-2.5 h-2.5 mr-0.5 animate-spin" />
                    {t('executing')}
                  </Badge>
                )}
              </div>
            </div>
            
            {/* Description */}
            {message.description && (
              <p className="text-xs text-slate-600 dark:text-slate-400 mb-2 line-clamp-2 leading-relaxed">
                {message.description}
              </p>
            )}
            
            {/* Luna Message */}
            <p className="text-xs text-slate-500 dark:text-slate-500 italic line-clamp-2 leading-relaxed">
              "{message.lunaMessage}"
            </p>
          </div>
        </div>
        
        {/* Actions Row */}
        <div className="flex items-center justify-between gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-1">
            {!isExecuting && (
              <>
                {/* Snooze - Compact */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-7 px-2 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                    >
                      <Clock className="w-3 h-3 mr-1" />
                      {t('later')}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" onClick={(e) => e.stopPropagation()}>
                    <DropdownMenuItem onClick={() => handleSnooze('later_today')}>
                      {t('snoozeLaterToday')}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleSnooze('tomorrow_morning')}>
                      {t('snoozeTomorrow')}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleSnooze('next_working_day')}>
                      {t('snoozeNextWorkDay')}
                    </DropdownMenuItem>
                    {message.meetingId && (
                      <DropdownMenuItem onClick={() => handleSnooze('after_meeting')}>
                        {t('snoozeAfterMeeting')}
                      </DropdownMenuItem>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
                
                {/* Dismiss */}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleDismiss}
                  disabled={isActing}
                  className="h-7 w-7 text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"
                >
                  <X className="w-3.5 h-3.5" />
                </Button>
              </>
            )}
          </div>
          
          {/* CTA Button */}
          <Button
            size="sm"
            onClick={handleAccept}
            disabled={isActing || isExecuting}
            className={`
              h-7 px-3 text-xs font-medium
              ${isUrgent 
                ? 'bg-orange-600 hover:bg-orange-700 text-white' 
                : 'bg-indigo-600 hover:bg-indigo-700 text-white'
              }
            `}
          >
            {isActing ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <>
                {t('ctaLabel')}
                <ChevronRight className="w-3 h-3 ml-1" />
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
