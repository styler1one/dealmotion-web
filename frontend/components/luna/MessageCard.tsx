'use client'

/**
 * Luna Message Card Component
 * SPEC-046-Luna-Unified-AI-Assistant
 * 
 * Displays a single Luna action message with CTA, dismiss, and snooze options.
 */

import React, { useEffect, useState } from 'react'
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
  X,
  Clock,
  ChevronRight,
  Loader2,
  Search,
  FileText,
  Mail,
  MessageSquare,
  Calendar,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react'
import { useLuna } from './LunaProvider'
import type { LunaMessage, SnoozeOption, Surface } from '@/types/luna'

// =============================================================================
// ICON MAPPING
// =============================================================================

const MESSAGE_ICONS: Record<string, React.ReactNode> = {
  start_research: <Search className="w-5 h-5 text-blue-500" />,
  review_research: <FileText className="w-5 h-5 text-blue-500" />,
  prepare_outreach: <MessageSquare className="w-5 h-5 text-purple-500" />,
  first_touch_sent: <CheckCircle2 className="w-5 h-5 text-green-500" />,
  suggest_meeting_creation: <Calendar className="w-5 h-5 text-orange-500" />,
  create_prep: <FileText className="w-5 h-5 text-indigo-500" />,
  prep_ready: <CheckCircle2 className="w-5 h-5 text-green-500" />,
  review_meeting_summary: <FileText className="w-5 h-5 text-teal-500" />,
  review_customer_report: <FileText className="w-5 h-5 text-teal-500" />,
  send_followup_email: <Mail className="w-5 h-5 text-rose-500" />,
  create_action_items: <CheckCircle2 className="w-5 h-5 text-amber-500" />,
  update_crm_notes: <RefreshCw className="w-5 h-5 text-gray-500" />,
}

// =============================================================================
// SNOOZE OPTIONS
// =============================================================================

interface SnoozeMenuProps {
  onSnooze: (option: SnoozeOption) => void
  hasMeeting?: boolean
}

function SnoozeMenu({ onSnooze, hasMeeting }: SnoozeMenuProps) {
  const t = useTranslations('luna')
  
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="text-gray-500 hover:text-gray-700">
          <Clock className="w-4 h-4 mr-1" />
          {t('later')}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => onSnooze('later_today')}>
          {t('snoozeLaterToday')}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onSnooze('tomorrow_morning')}>
          {t('snoozeTomorrow')}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onSnooze('next_working_day')}>
          {t('snoozeNextWorkDay')}
        </DropdownMenuItem>
        {hasMeeting && (
          <DropdownMenuItem onClick={() => onSnooze('after_meeting')}>
            {t('snoozeAfterMeeting')}
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

// =============================================================================
// MESSAGE CARD
// =============================================================================

interface MessageCardProps {
  message: LunaMessage
  surface?: Surface
  onInlineAction?: (message: LunaMessage) => void
}

export function MessageCard({ message, surface = 'home', onInlineAction }: MessageCardProps) {
  const router = useRouter()
  const t = useTranslations('luna')
  const { acceptMessage, dismissMessage, snoozeMessage, markMessageShown } = useLuna()
  
  const [isActing, setIsActing] = useState(false)
  const [hasMarkedShown, setHasMarkedShown] = useState(false)
  
  // Mark as shown on first render
  useEffect(() => {
    if (!hasMarkedShown) {
      markMessageShown(message.id, surface)
      setHasMarkedShown(true)
    }
  }, [message.id, surface, markMessageShown, hasMarkedShown])
  
  const handleAccept = async () => {
    setIsActing(true)
    try {
      // For inline actions, call the callback to open the sheet BEFORE accepting
      if (message.actionType === 'inline' && onInlineAction) {
        onInlineAction(message)
        setIsActing(false)
        return
      }
      
      await acceptMessage(message.id)
      
      // Navigate if action type is navigate
      if (message.actionType === 'navigate' && message.actionRoute) {
        router.push(message.actionRoute)
      }
    } catch {
      setIsActing(false)
    }
  }
  
  const handleDismiss = async () => {
    setIsActing(true)
    try {
      await dismissMessage(message.id)
    } catch {
      setIsActing(false)
    }
  }
  
  const handleSnooze = async (option: SnoozeOption) => {
    setIsActing(true)
    try {
      await snoozeMessage(message.id, option)
    } catch {
      setIsActing(false)
    }
  }
  
  const icon = MESSAGE_ICONS[message.messageType] || <FileText className="w-5 h-5" />
  const isUrgent = message.priority >= 80
  const isExecuting = message.status === 'executing'
  
  return (
    <Card className={`p-4 hover:shadow-md transition-shadow ${isUrgent ? 'border-orange-200 bg-orange-50/50' : ''}`}>
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className="flex-shrink-0 mt-0.5">
          {icon}
        </div>
        
        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium text-gray-900 truncate">
              {message.title}
            </h3>
            {isUrgent && (
              <Badge variant="destructive" className="text-xs">
                {t('urgent')}
              </Badge>
            )}
            {isExecuting && (
              <Badge variant="secondary" className="text-xs">
                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                {t('executing')}
              </Badge>
            )}
          </div>
          
          {message.description && (
            <p className="text-sm text-gray-600 mb-2">
              {message.description}
            </p>
          )}
          
          <p className="text-sm text-gray-500 italic">
            "{message.lunaMessage}"
          </p>
        </div>
        
        {/* Actions */}
        <div className="flex-shrink-0 flex items-center gap-1">
          {!isExecuting && (
            <>
              {/* Snooze */}
              <SnoozeMenu
                onSnooze={handleSnooze}
                hasMeeting={!!message.meetingId}
              />
              
              {/* Dismiss */}
              <Button
                variant="ghost"
                size="icon"
                onClick={handleDismiss}
                disabled={isActing}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-4 h-4" />
              </Button>
            </>
          )}
          
          {/* CTA */}
          <Button
            size="sm"
            onClick={handleAccept}
            disabled={isActing || isExecuting}
            className="ml-2"
          >
            {isActing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                {t('ctaLabel')}
                <ChevronRight className="w-4 h-4 ml-1" />
              </>
            )}
          </Button>
        </div>
      </div>
    </Card>
  )
}

// =============================================================================
// MESSAGE LIST
// =============================================================================

interface MessageListProps {
  messages: LunaMessage[]
  surface?: Surface
  emptyMessage?: string
  onInlineAction?: (message: LunaMessage) => void
}

export function MessageList({ messages, surface = 'home', emptyMessage, onInlineAction }: MessageListProps) {
  const t = useTranslations('luna')
  
  if (messages.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        {emptyMessage || t('noMessages')}
      </div>
    )
  }
  
  return (
    <div className="space-y-3">
      {messages.map(message => (
        <MessageCard
          key={message.id}
          message={message}
          surface={surface}
          onInlineAction={onInlineAction}
        />
      ))}
    </div>
  )
}

// Aliases for explicit naming
export { MessageCard as MessageCardWithInline }
export { MessageList as MessageListWithInline }
