'use client'

/**
 * AI Sales Coach "Luna" - Compact State
 * TASK-029 / SPEC-028
 * 
 * Shows the top priority suggestion with action buttons.
 */

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useCoach } from './CoachProvider'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { SNOOZE_OPTIONS } from '@/types/coach'

export function CoachCompact() {
  const router = useRouter()
  const { 
    suggestions, 
    setWidgetState, 
    dismissSuggestion, 
    snoozeSuggestion,
    clickSuggestion 
  } = useCoach()
  const t = useTranslations('coach')
  const [isActing, setIsActing] = useState(false)
  
  // Get top priority suggestion
  const topSuggestion = suggestions.find(s => !s.action_taken)
  
  if (!topSuggestion) {
    // No suggestions - show minimal state
    return (
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl border border-slate-200 dark:border-slate-700 p-4 w-80">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">🧠</span>
            <span className="font-semibold text-slate-900 dark:text-white">{t('name')}</span>
          </div>
          <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={() => setWidgetState('expanded')}
            title={t('widget.expand')}
          >
            <Icons.maximize className="h-4 w-4" />
          </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => setWidgetState('minimized')}
            >
              <Icons.x className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
          {t('widget.allCaughtUp')}
        </p>
      </div>
    )
  }
  
  const handleAction = async () => {
    if (topSuggestion.action_route) {
      setIsActing(true)
      await clickSuggestion(topSuggestion.id)
      router.push(topSuggestion.action_route)
    }
  }
  
  const handleDismiss = async () => {
    await dismissSuggestion(topSuggestion.id)
  }
  
  const handleSnooze = async (minutes: number) => {
    const until = new Date(Date.now() + minutes * 60 * 1000)
    await snoozeSuggestion(topSuggestion.id, until)
  }
  
  return (
    <div 
      className="bg-white dark:bg-slate-900 rounded-xl shadow-xl border border-slate-200 dark:border-slate-700 p-4 w-[calc(100vw-2rem)] sm:w-80 max-w-80 animate-in slide-in-from-bottom-4 duration-300"
      role="dialog"
      aria-label={t('name')}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">🧠</span>
          <span className="font-semibold text-slate-900 dark:text-white">{t('name')}</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={() => setWidgetState('expanded')}
            aria-label={t('widget.expand')}
            title={t('widget.expand')}
          >
            <Icons.maximize className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={() => setWidgetState('minimized')}
            aria-label={t('widget.collapse')}
          >
            <Icons.x className="h-4 w-4" />
          </Button>
        </div>
      </div>
      
      {/* Suggestion */}
      <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3 mb-3">
        <div className="flex items-start gap-2">
          <span className="text-lg flex-shrink-0">{topSuggestion.icon}</span>
          <div className="min-w-0 flex-1">
            <p className="font-medium text-slate-900 dark:text-white text-sm">
              {topSuggestion.title}
            </p>
            {topSuggestion.reason && (
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                {topSuggestion.reason}
              </p>
            )}
          </div>
        </div>
      </div>
      
      {/* Actions */}
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          className="flex-1 bg-indigo-600 hover:bg-indigo-700"
          onClick={handleAction}
          disabled={isActing || !topSuggestion.action_route}
        >
          {isActing ? (
            <Icons.spinner className="h-4 w-4 animate-spin mr-1" />
          ) : null}
          {topSuggestion.action_label || t('actions.doIt')}
        </Button>
        
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              {t('actions.later')}
              <Icons.chevronDown className="h-3 w-3 ml-1" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {SNOOZE_OPTIONS.map((option) => (
              <DropdownMenuItem 
                key={option.label}
                onClick={() => handleSnooze(option.duration)}
              >
                {t(`actions.snooze${option.label.replace(/\s/g, '')}`)}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        
        <Button
          variant="ghost"
          size="sm"
          onClick={handleDismiss}
          className="text-slate-400 hover:text-slate-600"
        >
          {t('actions.skip')}
        </Button>
      </div>
    </div>
  )
}

