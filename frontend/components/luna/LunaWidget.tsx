'use client'

/**
 * Luna Floating Widget Component
 * SPEC-046-Luna-Unified-AI-Assistant
 * 
 * Floating widget that shows Luna status and pending messages.
 * Three states: minimized, compact, expanded.
 */

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Sparkles,
  X,
  ChevronUp,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { useLunaOptional } from './LunaProvider'
import { MessageCard } from './MessageCard'

// =============================================================================
// WIDGET STATES
// =============================================================================

type WidgetState = 'minimized' | 'compact' | 'expanded'

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
    <Card className="fixed bottom-4 right-4 z-50 w-96 max-h-[70vh] shadow-xl flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b shrink-0">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded-full ${hasUrgent ? 'bg-orange-100' : 'bg-indigo-100'}`}>
            <Sparkles className={`w-4 h-4 ${hasUrgent ? 'text-orange-500' : 'text-indigo-500'}`} />
          </div>
          <span className="font-medium">Luna</span>
          {counts.pending > 0 && (
            <Badge variant={hasUrgent ? 'destructive' : 'secondary'}>
              {counts.pending} {t('pending')}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setWidgetState('compact')}
            className="h-7 w-7"
          >
            <ChevronDown className="w-4 h-4" />
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
      
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3">
        {pendingMessages.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Sparkles className="w-8 h-8 mx-auto mb-2 text-gray-300" />
            <p className="text-sm">{t('allCaughtUp')}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {pendingMessages.slice(0, 3).map(message => (
              <MessageCard
                key={message.id}
                message={message}
                surface="widget"
              />
            ))}
            
            {pendingMessages.length > 3 && (
              <Button
                variant="outline"
                className="w-full mt-2"
                onClick={() => router.push('/dashboard')}
              >
                {t('viewAllActions', { count: pendingMessages.length })}
              </Button>
            )}
          </div>
        )}
      </div>
      
      {/* Footer */}
      <div className="p-3 border-t shrink-0">
        <Button
          variant="outline"
          className="w-full"
          onClick={() => router.push('/dashboard')}
        >
          {t('openLunaHome')}
        </Button>
      </div>
    </Card>
  )
}
