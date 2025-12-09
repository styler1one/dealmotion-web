'use client'

import { cn } from '@/lib/utils'
import { Icons } from '@/components/icons'

// ===========================================
// Types
// ===========================================

type StatusType = 
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'active'
  | 'inactive'
  | 'draft'
  | 'published'
  | 'archived'

type BadgeSize = 'sm' | 'md' | 'lg'

interface StatusBadgeProps {
  status: StatusType | string
  /** Custom label (defaults to capitalized status) */
  label?: string
  /** Size variant */
  size?: BadgeSize
  /** Show icon */
  showIcon?: boolean
  /** Show animated indicator for processing states */
  animated?: boolean
  /** Additional CSS classes */
  className?: string
}

// ===========================================
// Status Configuration
// ===========================================

const statusConfig: Record<StatusType, {
  label: string
  bgColor: string
  textColor: string
  icon: keyof typeof Icons
  animate?: boolean
}> = {
  pending: {
    label: 'Pending',
    bgColor: 'bg-amber-100 dark:bg-amber-900/30',
    textColor: 'text-amber-700 dark:text-amber-400',
    icon: 'clock',
  },
  processing: {
    label: 'Processing',
    bgColor: 'bg-blue-100 dark:bg-blue-900/30',
    textColor: 'text-blue-700 dark:text-blue-400',
    icon: 'spinner',
    animate: true,
  },
  completed: {
    label: 'Completed',
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    textColor: 'text-green-700 dark:text-green-400',
    icon: 'checkCircle',
  },
  failed: {
    label: 'Failed',
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    textColor: 'text-red-700 dark:text-red-400',
    icon: 'alertCircle',
  },
  cancelled: {
    label: 'Cancelled',
    bgColor: 'bg-slate-100 dark:bg-slate-800',
    textColor: 'text-slate-600 dark:text-slate-400',
    icon: 'x',
  },
  active: {
    label: 'Active',
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    textColor: 'text-green-700 dark:text-green-400',
    icon: 'check',
  },
  inactive: {
    label: 'Inactive',
    bgColor: 'bg-slate-100 dark:bg-slate-800',
    textColor: 'text-slate-600 dark:text-slate-400',
    icon: 'circle',
  },
  draft: {
    label: 'Draft',
    bgColor: 'bg-slate-100 dark:bg-slate-800',
    textColor: 'text-slate-600 dark:text-slate-400',
    icon: 'edit',
  },
  published: {
    label: 'Published',
    bgColor: 'bg-purple-100 dark:bg-purple-900/30',
    textColor: 'text-purple-700 dark:text-purple-400',
    icon: 'globe',
  },
  archived: {
    label: 'Archived',
    bgColor: 'bg-slate-100 dark:bg-slate-800',
    textColor: 'text-slate-500 dark:text-slate-500',
    icon: 'folderOpen',
  },
}

// Default config for unknown statuses
const defaultConfig = {
  label: 'Unknown',
  bgColor: 'bg-slate-100 dark:bg-slate-800',
  textColor: 'text-slate-600 dark:text-slate-400',
  icon: 'circle' as keyof typeof Icons,
}

// ===========================================
// Size Configuration
// ===========================================

const sizeConfig: Record<BadgeSize, {
  padding: string
  text: string
  icon: string
  gap: string
}> = {
  sm: {
    padding: 'px-1.5 py-0.5',
    text: 'text-xs',
    icon: 'h-3 w-3',
    gap: 'gap-1',
  },
  md: {
    padding: 'px-2 py-1',
    text: 'text-xs',
    icon: 'h-3.5 w-3.5',
    gap: 'gap-1.5',
  },
  lg: {
    padding: 'px-2.5 py-1.5',
    text: 'text-sm',
    icon: 'h-4 w-4',
    gap: 'gap-2',
  },
}

// ===========================================
// Component
// ===========================================

/**
 * Status badge component for displaying status indicators
 * 
 * @example
 * ```tsx
 * <StatusBadge status="completed" />
 * <StatusBadge status="processing" showIcon animated />
 * <StatusBadge status="failed" size="lg" />
 * ```
 */
export function StatusBadge({
  status,
  label,
  size = 'md',
  showIcon = true,
  animated = true,
  className,
}: StatusBadgeProps) {
  const config = statusConfig[status as StatusType] || {
    ...defaultConfig,
    label: status.charAt(0).toUpperCase() + status.slice(1),
  }
  const sizes = sizeConfig[size]
  const Icon = Icons[config.icon]
  const shouldAnimate = animated && config.animate

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full font-medium',
        sizes.padding,
        sizes.text,
        sizes.gap,
        config.bgColor,
        config.textColor,
        className
      )}
    >
      {showIcon && (
        <Icon className={cn(sizes.icon, shouldAnimate && 'animate-spin')} />
      )}
      {label || config.label}
    </span>
  )
}

// ===========================================
// Specialized Status Badges
// ===========================================

/**
 * Research status badge with appropriate colors
 */
export function ResearchStatusBadge({ 
  status, 
  ...props 
}: Omit<StatusBadgeProps, 'status'> & { status: string }) {
  const statusMap: Record<string, StatusType> = {
    'pending': 'pending',
    'processing': 'processing',
    'researching': 'processing',
    'completed': 'completed',
    'failed': 'failed',
    'error': 'failed',
  }
  
  return <StatusBadge status={statusMap[status] || status} {...props} />
}

/**
 * Subscription status badge
 */
export function SubscriptionStatusBadge({
  status,
  ...props
}: Omit<StatusBadgeProps, 'status'> & { status: string }) {
  const statusMap: Record<string, StatusType> = {
    'active': 'active',
    'trialing': 'active',
    'past_due': 'failed',
    'canceled': 'cancelled',
    'unpaid': 'failed',
    'incomplete': 'pending',
    'incomplete_expired': 'cancelled',
    'paused': 'inactive',
  }
  
  const labelMap: Record<string, string> = {
    'trialing': 'Trial',
    'past_due': 'Past Due',
    'incomplete_expired': 'Expired',
  }
  
  return (
    <StatusBadge 
      status={statusMap[status] || status} 
      label={labelMap[status]}
      {...props} 
    />
  )
}

/**
 * Plan badge for subscription plans
 */
export function PlanBadge({ 
  plan, 
  className 
}: { 
  plan: 'free' | 'solo' | 'teams' | string
  className?: string 
}) {
  const planConfig: Record<string, { label: string; bgColor: string; textColor: string }> = {
    free: {
      label: 'Free',
      bgColor: 'bg-slate-100 dark:bg-slate-800',
      textColor: 'text-slate-600 dark:text-slate-400',
    },
    solo: {
      label: 'Solo',
      bgColor: 'bg-blue-100 dark:bg-blue-900/30',
      textColor: 'text-blue-700 dark:text-blue-400',
    },
    teams: {
      label: 'Teams',
      bgColor: 'bg-purple-100 dark:bg-purple-900/30',
      textColor: 'text-purple-700 dark:text-purple-400',
    },
  }
  
  const config = planConfig[plan] || planConfig.free
  
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium',
        config.bgColor,
        config.textColor,
        className
      )}
    >
      {config.label}
    </span>
  )
}

/**
 * Dot indicator for simple status
 */
export function StatusDot({ 
  status,
  size = 'md',
  className,
}: { 
  status: 'success' | 'warning' | 'error' | 'info' | 'neutral'
  size?: 'sm' | 'md' | 'lg'
  className?: string
}) {
  const colorMap = {
    success: 'bg-green-500',
    warning: 'bg-amber-500',
    error: 'bg-red-500',
    info: 'bg-blue-500',
    neutral: 'bg-slate-400',
  }
  
  const sizeMap = {
    sm: 'h-1.5 w-1.5',
    md: 'h-2 w-2',
    lg: 'h-2.5 w-2.5',
  }
  
  return (
    <span
      className={cn(
        'inline-block rounded-full',
        colorMap[status],
        sizeMap[size],
        className
      )}
    />
  )
}

