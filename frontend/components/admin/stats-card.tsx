'use client'

import { cn } from '@/lib/utils'
import { Icons } from '@/components/icons'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface StatsCardProps {
  title: string
  value: string | number
  description?: string
  icon?: keyof typeof Icons
  iconColor?: string
  trend?: {
    value: number
    label: string
    isPositive?: boolean
  }
  className?: string
}

export function StatsCard({
  title,
  value,
  description,
  icon,
  iconColor = 'text-teal-500',
  trend,
  className,
}: StatsCardProps) {
  const Icon = icon ? Icons[icon] : null

  return (
    <Card className={cn('relative overflow-hidden', className)}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-slate-500 dark:text-slate-400">
          {title}
        </CardTitle>
        {Icon && (
          <div className={cn('p-2 rounded-lg bg-slate-100 dark:bg-slate-800', iconColor)}>
            <Icon className="h-4 w-4" />
          </div>
        )}
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline gap-2">
          <div className="text-2xl font-bold text-slate-900 dark:text-white">
            {value}
          </div>
          {trend && (
            <div className={cn(
              'flex items-center gap-0.5 text-xs font-medium',
              trend.isPositive ? 'text-green-500' : 'text-red-500'
            )}>
              {trend.isPositive ? (
                <Icons.trendingUp className="h-3 w-3" />
              ) : (
                <Icons.trendingDown className="h-3 w-3" />
              )}
              <span>{trend.value > 0 ? '+' : ''}{trend.value}{trend.label}</span>
            </div>
          )}
        </div>
        {description && (
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            {description}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

// Health Score Card variant
interface HealthScoreCardProps {
  score: number
  status: 'healthy' | 'at_risk' | 'critical'
  breakdown?: {
    label: string
    value: number
    max: number
  }[]
  className?: string
}

export function HealthScoreCard({
  score,
  status,
  breakdown,
  className,
}: HealthScoreCardProps) {
  const statusColors = {
    healthy: 'text-green-500 bg-green-500/10',
    at_risk: 'text-yellow-500 bg-yellow-500/10',
    critical: 'text-red-500 bg-red-500/10',
  }

  const statusLabels = {
    healthy: 'Healthy',
    at_risk: 'At Risk',
    critical: 'Critical',
  }

  return (
    <Card className={cn('relative overflow-hidden', className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-slate-500 dark:text-slate-400">
          Health Score
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4">
          <div className={cn(
            'w-16 h-16 rounded-full flex items-center justify-center text-2xl font-bold',
            statusColors[status]
          )}>
            {score}
          </div>
          <div>
            <div className={cn(
              'text-sm font-medium capitalize',
              status === 'healthy' ? 'text-green-500' : 
              status === 'at_risk' ? 'text-yellow-500' : 'text-red-500'
            )}>
              {statusLabels[status]}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Based on activity & engagement
            </p>
          </div>
        </div>

        {breakdown && breakdown.length > 0 && (
          <div className="mt-4 space-y-2">
            {breakdown.map((item) => (
              <div key={item.label} className="flex items-center gap-2">
                <span className="text-xs text-slate-500 w-24">{item.label}</span>
                <div className="flex-1 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-teal-500 rounded-full transition-all"
                    style={{ width: `${(item.value / item.max) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-slate-500 w-12 text-right">
                  {item.value}/{item.max}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// Alert Badge for dashboard
interface AlertBadgeProps {
  count: number
  severity?: 'info' | 'warning' | 'error' | 'critical'
}

export function AlertBadge({ count, severity = 'warning' }: AlertBadgeProps) {
  const severityColors = {
    info: 'bg-blue-500',
    warning: 'bg-yellow-500',
    error: 'bg-orange-500',
    critical: 'bg-red-500',
  }

  if (count === 0) return null

  return (
    <span className={cn(
      'inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-medium text-white',
      severityColors[severity]
    )}>
      {count > 99 ? '99+' : count}
    </span>
  )
}

