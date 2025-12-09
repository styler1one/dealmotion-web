'use client'

import { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'

type IconName = keyof typeof Icons

interface EmptyStateProps {
  /** Icon to display */
  icon?: IconName
  /** Main title */
  title: string
  /** Description text */
  description?: string
  /** Primary action button */
  action?: {
    label: string
    onClick: () => void
    icon?: IconName
  }
  /** Secondary action button */
  secondaryAction?: {
    label: string
    onClick: () => void
  }
  /** Additional content below buttons */
  children?: ReactNode
  /** Size variant */
  size?: 'sm' | 'md' | 'lg'
  /** Additional CSS classes */
  className?: string
}

/**
 * Empty state component for when there's no data to display
 * 
 * @example
 * ```tsx
 * <EmptyState
 *   icon="search"
 *   title="No research briefs yet"
 *   description="Start by researching your first prospect"
 *   action={{
 *     label: "Start Research",
 *     onClick: () => router.push('/dashboard/research'),
 *     icon: "plus"
 *   }}
 * />
 * ```
 */
export function EmptyState({
  icon = 'inbox',
  title,
  description,
  action,
  secondaryAction,
  children,
  size = 'md',
  className,
}: EmptyStateProps) {
  const Icon = Icons[icon]
  const ActionIcon = action?.icon ? Icons[action.icon] : null

  const sizeClasses = {
    sm: {
      container: 'py-8',
      iconWrapper: 'w-12 h-12',
      icon: 'h-6 w-6',
      title: 'text-base',
      description: 'text-sm',
    },
    md: {
      container: 'py-12',
      iconWrapper: 'w-16 h-16',
      icon: 'h-8 w-8',
      title: 'text-lg',
      description: 'text-sm',
    },
    lg: {
      container: 'py-16',
      iconWrapper: 'w-20 h-20',
      icon: 'h-10 w-10',
      title: 'text-xl',
      description: 'text-base',
    },
  }

  const sizes = sizeClasses[size]

  return (
    <div className={cn(
      'flex flex-col items-center justify-center text-center',
      sizes.container,
      className
    )}>
      {/* Icon */}
      <div className={cn(
        'rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mb-4',
        sizes.iconWrapper
      )}>
        <Icon className={cn('text-slate-400 dark:text-slate-500', sizes.icon)} />
      </div>

      {/* Title */}
      <h3 className={cn(
        'font-semibold text-slate-900 dark:text-white mb-2',
        sizes.title
      )}>
        {title}
      </h3>

      {/* Description */}
      {description && (
        <p className={cn(
          'text-slate-500 dark:text-slate-400 max-w-sm mb-6',
          sizes.description
        )}>
          {description}
        </p>
      )}

      {/* Actions */}
      {(action || secondaryAction) && (
        <div className="flex items-center gap-3">
          {action && (
            <Button onClick={action.onClick}>
              {ActionIcon && <ActionIcon className="h-4 w-4 mr-2" />}
              {action.label}
            </Button>
          )}
          {secondaryAction && (
            <Button variant="outline" onClick={secondaryAction.onClick}>
              {secondaryAction.label}
            </Button>
          )}
        </div>
      )}

      {/* Additional content */}
      {children && (
        <div className="mt-6">
          {children}
        </div>
      )}
    </div>
  )
}

/**
 * Pre-configured empty states for common use cases
 */

export function NoResultsState({
  searchTerm,
  onClear,
}: {
  searchTerm?: string
  onClear?: () => void
}) {
  return (
    <EmptyState
      icon="search"
      title="No results found"
      description={
        searchTerm
          ? `No results for "${searchTerm}". Try adjusting your search.`
          : 'Try adjusting your filters or search terms.'
      }
      action={onClear ? { label: 'Clear search', onClick: onClear } : undefined}
      size="sm"
    />
  )
}

export function NoProspectsState({ onAdd }: { onAdd: () => void }) {
  return (
    <EmptyState
      icon="users"
      title="No prospects yet"
      description="Start by researching your first prospect company"
      action={{
        label: 'Start Research',
        onClick: onAdd,
        icon: 'search',
      }}
    />
  )
}

export function NoResearchState({ onAdd }: { onAdd: () => void }) {
  return (
    <EmptyState
      icon="search"
      title="No research briefs"
      description="Research a prospect to get AI-powered insights"
      action={{
        label: 'New Research',
        onClick: onAdd,
        icon: 'plus',
      }}
    />
  )
}

export function NoPreparationsState({ onAdd }: { onAdd: () => void }) {
  return (
    <EmptyState
      icon="fileText"
      title="No meeting preparations"
      description="Prepare for your next meeting with AI assistance"
      action={{
        label: 'New Preparation',
        onClick: onAdd,
        icon: 'plus',
      }}
    />
  )
}

export function NoFollowupsState({ onAdd }: { onAdd: () => void }) {
  return (
    <EmptyState
      icon="mail"
      title="No follow-ups yet"
      description="Upload a meeting recording to generate follow-up content"
      action={{
        label: 'Upload Recording',
        onClick: onAdd,
        icon: 'upload',
      }}
    />
  )
}

export function NoDocumentsState({ onAdd }: { onAdd: () => void }) {
  return (
    <EmptyState
      icon="fileText"
      title="No documents"
      description="Upload documents to your knowledge base for AI context"
      action={{
        label: 'Upload Document',
        onClick: onAdd,
        icon: 'upload',
      }}
    />
  )
}

export function NoContactsState({ onAdd }: { onAdd: () => void }) {
  return (
    <EmptyState
      icon="userPlus"
      title="No contacts added"
      description="Add contact persons for personalized meeting preparation"
      action={{
        label: 'Add Contact',
        onClick: onAdd,
        icon: 'plus',
      }}
      size="sm"
    />
  )
}

export function ErrorState({
  title = 'Something went wrong',
  description = 'An error occurred while loading data',
  onRetry,
}: {
  title?: string
  description?: string
  onRetry?: () => void
}) {
  return (
    <EmptyState
      icon="alertCircle"
      title={title}
      description={description}
      action={onRetry ? { label: 'Try again', onClick: onRetry, icon: 'refresh' } : undefined}
    />
  )
}

export function LoadingState({ message = 'Loading...' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Icons.spinner className="h-8 w-8 animate-spin text-blue-600 mb-4" />
      <p className="text-sm text-slate-500 dark:text-slate-400">{message}</p>
    </div>
  )
}

