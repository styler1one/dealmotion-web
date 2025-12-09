'use client'

/**
 * AI Sales Coach "Luna" - Expanded State
 * TASK-029 / SPEC-028
 * 
 * Full panel with all suggestions, stats, and settings.
 */

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useCoach } from './CoachProvider'
import { useCoachInsights, getScoreColor, getScoreLabel } from '@/hooks/useCoachInsights'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { Progress } from '@/components/ui/progress'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { SNOOZE_OPTIONS, type Suggestion } from '@/types/coach'

export function CoachExpanded() {
  const router = useRouter()
  const { 
    suggestions, 
    stats,
    setWidgetState, 
    dismissSuggestion, 
    snoozeSuggestion,
    clickSuggestion,
    updateSettings,
  } = useCoach()
  const { tip, score, recommendations, predictions } = useCoachInsights()
  const t = useTranslations('coach')
  
  const pendingSuggestions = suggestions.filter(s => !s.action_taken)
  const prioritySuggestion = pendingSuggestions.find(s => s.priority >= 80)
  const regularSuggestions = pendingSuggestions.filter(s => s.priority < 80)
  
  // Calculate progress
  const todayTotal = stats?.today.total_completed || 0
  const dailyGoal = 5 // Target: 5 actions per day
  const progressPercent = Math.min(100, (todayTotal / dailyGoal) * 100)
  
  return (
    <div 
      className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-700 w-[calc(100vw-2rem)] sm:w-96 max-w-96 max-h-[85vh] sm:max-h-[80vh] overflow-hidden animate-in slide-in-from-bottom-4 duration-300"
      role="dialog"
      aria-label={t('name')}
      aria-modal="true"
    >
      {/* Header */}
      <div className="sticky top-0 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl">🧠</span>
          <div>
            <span className="font-semibold text-slate-900 dark:text-white">{t('name')}</span>
            <span className="text-xs text-slate-500 dark:text-slate-400 ml-2">{t('tagline')}</span>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0"
          onClick={() => setWidgetState('minimized')}
          aria-label={t('widget.close')}
        >
          <Icons.x className="h-4 w-4" />
        </Button>
      </div>
      
      {/* Content - Scrollable */}
      <div className="overflow-y-auto max-h-[calc(80vh-120px)] p-4 space-y-4">
        
        {/* Priority Suggestion */}
        {prioritySuggestion && (
          <div className="bg-gradient-to-br from-orange-50 to-red-50 dark:from-orange-950 dark:to-red-950 rounded-lg p-4 border-2 border-orange-200 dark:border-orange-800">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-orange-600 dark:text-orange-400 uppercase">
                🔴 {t('sections.priority')}
              </span>
            </div>
            <SuggestionCard 
              suggestion={prioritySuggestion}
              onAction={async () => {
                if (prioritySuggestion.action_route) {
                  await clickSuggestion(prioritySuggestion.id)
                  router.push(prioritySuggestion.action_route)
                }
              }}
              onDismiss={() => dismissSuggestion(prioritySuggestion.id)}
              onSnooze={(mins) => {
                const until = new Date(Date.now() + mins * 60 * 1000)
                snoozeSuggestion(prioritySuggestion.id, until)
              }}
            />
          </div>
        )}
        
        {/* Regular Suggestions */}
        {regularSuggestions.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                💡 {t('sections.suggestions')} ({regularSuggestions.length})
              </span>
            </div>
            <div className="space-y-2">
              {regularSuggestions.slice(0, 5).map((suggestion) => (
                <SuggestionCard
                  key={suggestion.id}
                  suggestion={suggestion}
                  compact
                  onAction={async () => {
                    if (suggestion.action_route) {
                      await clickSuggestion(suggestion.id)
                      router.push(suggestion.action_route)
                    }
                  }}
                  onDismiss={() => dismissSuggestion(suggestion.id)}
                  onSnooze={(mins) => {
                    const until = new Date(Date.now() + mins * 60 * 1000)
                    snoozeSuggestion(suggestion.id, until)
                  }}
                />
              ))}
            </div>
          </div>
        )}
        
        {/* No Suggestions */}
        {pendingSuggestions.length === 0 && (
          <div className="text-center py-6">
            <span className="text-4xl mb-2 block">✨</span>
            <p className="font-medium text-slate-900 dark:text-white">
              {t('widget.allCaughtUp')}
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {t('widget.greatWork')}
            </p>
          </div>
        )}
        
        {/* Today's Progress */}
        {stats && (
          <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                📊 {t('sections.progress')}
              </span>
            </div>
            
            {/* Stats Grid */}
            <div className="grid grid-cols-4 gap-2 mb-3">
              <StatBox 
                label={t('stats.research')} 
                value={stats.today.research_completed} 
                icon="🔍"
              />
              <StatBox 
                label={t('stats.preps')} 
                value={stats.today.preps_completed} 
                icon="📋"
              />
              <StatBox 
                label={t('stats.followups')} 
                value={stats.today.followups_completed} 
                icon="🎙️"
              />
              <StatBox 
                label="Actions" 
                value={stats.today.actions_generated} 
                icon="✨"
              />
            </div>
            
            {/* Progress Bar */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-500 dark:text-slate-400">
                <span>{stats.today.total_completed} {t('stats.completed')}</span>
                <span>{Math.round(progressPercent)}%</span>
              </div>
              <Progress value={progressPercent} className="h-2" />
            </div>
          </div>
        )}
        
        {/* Success Score */}
        {score > 0 && (
          <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                🏆 {t('sections.score')}
              </span>
              <span className={`text-lg font-bold ${getScoreColor(score)}`}>
                {score}%
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {getScoreLabel(score)}
            </p>
          </div>
        )}
        
        {/* Tip of the Day */}
        {tip && (
          <div className="bg-indigo-50 dark:bg-indigo-950 rounded-lg p-4 border border-indigo-200 dark:border-indigo-800">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">{tip.icon}</span>
              <span className="text-sm font-semibold text-indigo-700 dark:text-indigo-300">
                {tip.title}
              </span>
              {tip.is_personalized && (
                <span className="text-xs bg-indigo-200 dark:bg-indigo-800 text-indigo-700 dark:text-indigo-300 px-1.5 py-0.5 rounded">
                  AI
                </span>
              )}
            </div>
            <p className="text-sm text-indigo-900 dark:text-indigo-100">
              {tip.content}
            </p>
          </div>
        )}
        
        {/* Predictions */}
        {predictions.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                🔮 {t('sections.predictions')}
              </span>
            </div>
            {predictions.map((prediction, idx) => (
              <div 
                key={idx}
                className="flex items-start gap-2 p-3 bg-purple-50 dark:bg-purple-950 rounded-lg border border-purple-200 dark:border-purple-800 cursor-pointer hover:border-purple-400 dark:hover:border-purple-600 transition-colors"
                onClick={() => prediction.action_route && router.push(prediction.action_route)}
              >
                <span className="text-lg">{prediction.icon}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-purple-900 dark:text-purple-100">
                    {prediction.title}
                  </p>
                  <p className="text-xs text-purple-700 dark:text-purple-300 mt-0.5">
                    {prediction.message}
                  </p>
                </div>
                {prediction.action_route && (
                  <Icons.chevronRight className="h-4 w-4 text-purple-400 flex-shrink-0" />
                )}
              </div>
            ))}
          </div>
        )}
        
        {/* Recommendations */}
        {recommendations.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                📝 {t('sections.recommendations')}
              </span>
            </div>
            {recommendations.slice(0, 2).map((rec, idx) => (
              <div 
                key={idx}
                className={`p-3 rounded-lg border ${
                  rec.priority === 'high' 
                    ? 'bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800' 
                    : 'bg-amber-50 dark:bg-amber-950 border-amber-200 dark:border-amber-800'
                }`}
              >
                <p className={`text-sm ${
                  rec.priority === 'high'
                    ? 'text-red-900 dark:text-red-100'
                    : 'text-amber-900 dark:text-amber-100'
                }`}>
                  {rec.message}
                </p>
              </div>
            ))}
          </div>
        )}
        
      </div>
      
      {/* Footer */}
      <div className="sticky bottom-0 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-700 px-4 py-3 flex items-center justify-between">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push('/dashboard/settings')}
        >
          <Icons.settings className="h-4 w-4 mr-1" />
          {t('widget.settings')}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => updateSettings({ is_enabled: false })}
          className="text-slate-400"
        >
          {t('widget.hideForToday')}
        </Button>
      </div>
    </div>
  )
}


// =============================================================================
// SUB-COMPONENTS
// =============================================================================

interface SuggestionCardProps {
  suggestion: Suggestion
  compact?: boolean
  onAction: () => void
  onDismiss: () => void
  onSnooze: (minutes: number) => void
}

function SuggestionCard({ suggestion, compact, onAction, onDismiss, onSnooze }: SuggestionCardProps) {
  const t = useTranslations('coach')
  const [isActing, setIsActing] = useState(false)
  
  const handleAction = async () => {
    setIsActing(true)
    await onAction()
  }
  
  if (compact) {
    return (
      <div className="flex items-center gap-3 p-3 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-indigo-300 dark:hover:border-indigo-700 transition-colors group">
        <span className="text-lg flex-shrink-0">{suggestion.icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
            {suggestion.title}
          </p>
        </div>
        <Button
          size="sm"
          variant="ghost"
          className="opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={handleAction}
          disabled={isActing || !suggestion.action_route}
        >
          {isActing ? <Icons.spinner className="h-4 w-4 animate-spin" /> : <Icons.chevronRight className="h-4 w-4" />}
        </Button>
      </div>
    )
  }
  
  return (
    <div className="space-y-3">
      <div className="flex items-start gap-2">
        <span className="text-lg flex-shrink-0">{suggestion.icon}</span>
        <div className="min-w-0 flex-1">
          <p className="font-medium text-slate-900 dark:text-white">
            {suggestion.title}
          </p>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">
            {suggestion.description}
          </p>
          {suggestion.reason && (
            <p className="text-xs text-slate-500 dark:text-slate-500 mt-1">
              {suggestion.reason}
            </p>
          )}
        </div>
      </div>
      
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          className="flex-1 bg-indigo-600 hover:bg-indigo-700"
          onClick={handleAction}
          disabled={isActing || !suggestion.action_route}
        >
          {isActing && <Icons.spinner className="h-4 w-4 animate-spin mr-1" />}
          {suggestion.action_label || t('actions.doIt')}
        </Button>
        
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              <Icons.clock className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {SNOOZE_OPTIONS.map((option) => (
              <DropdownMenuItem 
                key={option.label}
                onClick={() => onSnooze(option.duration)}
              >
                {option.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        
        <Button
          variant="ghost"
          size="sm"
          onClick={onDismiss}
          className="text-slate-400 hover:text-slate-600"
        >
          <Icons.x className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}


interface StatBoxProps {
  label: string
  value: number
  icon: string
}

function StatBox({ label, value, icon }: StatBoxProps) {
  return (
    <div className="text-center p-2 bg-white dark:bg-slate-700 rounded-lg">
      <span className="text-lg block">{icon}</span>
      <span className="text-lg font-bold text-slate-900 dark:text-white">{value}</span>
      <span className="text-xs text-slate-500 dark:text-slate-400 block truncate">{label}</span>
    </div>
  )
}

