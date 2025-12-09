'use client'

import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'
import { useTranslations } from 'next-intl'
import type { ActionType, ActionTypeInfo, FollowupAction } from '@/types/followup-actions'
import { isActionGenerating, isActionCompleted, isActionError } from '@/types/followup-actions'

interface ActionCardProps {
  actionType: ActionTypeInfo
  existingAction?: FollowupAction
  onGenerate: (type: ActionType) => void
  onView: (action: FollowupAction) => void
  disabled?: boolean
  isCurrentlyGenerating?: boolean // True when this specific type is being generated
}

export function ActionCard({
  actionType,
  existingAction,
  onGenerate,
  onView,
  disabled = false,
  isCurrentlyGenerating = false,
}: ActionCardProps) {
  const t = useTranslations('followup.actions')
  
  // Show generating if we're actively generating OR if the action has generating status
  const isGenerating = isCurrentlyGenerating || (existingAction ? isActionGenerating(existingAction) : false)
  const isCompleted = existingAction ? isActionCompleted(existingAction) : false
  const hasError = existingAction ? isActionError(existingAction) : false

  // Completed cards are always clickable to view content
  // Only disable if: we're generating AND this card is not completed
  const isClickDisabled = isGenerating || (disabled && !isCompleted)

  const handleClick = () => {
    if (isCompleted && existingAction) {
      onView(existingAction)
    } else if (!isGenerating && !disabled) {
      onGenerate(actionType.type)
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={isClickDisabled}
      className={cn(
        'flex flex-col items-center p-4 rounded-xl border-2 transition-all text-center min-h-[120px]',
        'hover:shadow-md hover:scale-[1.02]',
        isCompleted && 'border-green-300 dark:border-green-700 bg-green-50/50 dark:bg-green-900/20',
        isGenerating && 'border-amber-300 dark:border-amber-700 bg-amber-50/50 dark:bg-amber-900/20',
        hasError && 'border-red-300 dark:border-red-700 bg-red-50/50 dark:bg-red-900/20',
        !isCompleted && !isGenerating && !hasError && 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900',
        isClickDisabled && 'opacity-50 cursor-not-allowed',
      )}
    >
      {/* Icon */}
      <span className="text-3xl mb-2">{actionType.icon}</span>
      
      {/* Label */}
      <span className="font-medium text-sm text-slate-900 dark:text-white mb-1">
        {actionType.label}
      </span>
      
      {/* Status badge */}
      {isCompleted && (
        <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
          <Icons.check className="h-3 w-3" />
          {t('generated')}
        </span>
      )}
      
      {isGenerating && (
        <span className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
          <Icons.spinner className="h-3 w-3 animate-spin" />
          {t('generating')}
        </span>
      )}
      
      {hasError && (
        <span className="text-xs text-red-600 dark:text-red-400 flex items-center gap-1">
          <Icons.alertCircle className="h-3 w-3" />
          {t('error')}
        </span>
      )}
      
      {!isCompleted && !isGenerating && !hasError && (
        <span className="text-xs text-slate-500 dark:text-slate-400">
          {t('clickToGenerate')}
        </span>
      )}
    </button>
  )
}

interface ActionsGridProps {
  actionTypes: ActionTypeInfo[]
  existingActions: FollowupAction[]
  onGenerate: (type: ActionType) => void
  onView: (action: FollowupAction) => void
  disabled?: boolean
  generatingType?: ActionType | null // The type currently being generated
}

export function ActionsGrid({
  actionTypes,
  existingActions,
  onGenerate,
  onView,
  disabled = false,
  generatingType = null,
}: ActionsGridProps) {
  // Create a map of existing actions by type
  const actionsByType = new Map(
    existingActions.map(a => [a.action_type, a])
  )

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {actionTypes.map((actionType) => (
        <ActionCard
          key={actionType.type}
          actionType={actionType}
          existingAction={actionsByType.get(actionType.type)}
          onGenerate={onGenerate}
          onView={onView}
          disabled={disabled}
          isCurrentlyGenerating={generatingType === actionType.type}
        />
      ))}
    </div>
  )
}

