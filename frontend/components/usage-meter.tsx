'use client'

import { cn } from '@/lib/utils'

interface UsageMeterProps {
  label: string
  used: number
  limit: number
  unlimited?: boolean
  showUpgrade?: boolean
  onUpgrade?: () => void
  className?: string
}

export function UsageMeter({
  label,
  used,
  limit,
  unlimited = false,
  showUpgrade = true,
  onUpgrade,
  className,
}: UsageMeterProps) {
  const percentage = unlimited ? 0 : limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 100
  const isWarning = !unlimited && percentage >= 80
  const isExceeded = !unlimited && percentage >= 100

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-slate-700 dark:text-slate-300">{label}</span>
        <span className={cn(
          "tabular-nums",
          isExceeded ? "text-red-600 dark:text-red-400 font-semibold" :
          isWarning ? "text-amber-600 dark:text-amber-400" :
          "text-slate-600 dark:text-slate-400"
        )}>
          {unlimited ? (
            <span className="text-emerald-600 dark:text-emerald-400">∞ Onbeperkt</span>
          ) : (
            <>
              {used} / {limit}
              {isExceeded && " ⚠️"}
            </>
          )}
        </span>
      </div>
      
      {!unlimited && (
        <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-300",
              isExceeded ? "bg-red-500" :
              isWarning ? "bg-amber-500" :
              "bg-emerald-500"
            )}
            style={{ width: `${percentage}%` }}
          />
        </div>
      )}
      
      {isExceeded && showUpgrade && onUpgrade && (
        <button
          onClick={onUpgrade}
          className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
        >
          Upgrade voor onbeperkt →
        </button>
      )}
    </div>
  )
}

interface UsageOverviewProps {
  research: { used: number; limit: number; unlimited: boolean }
  preparation: { used: number; limit: number; unlimited: boolean }
  followup: { used: number; limit: number; unlimited: boolean }
  onUpgrade?: () => void
  className?: string
}

export function UsageOverview({
  research,
  preparation,
  followup,
  onUpgrade,
  className,
}: UsageOverviewProps) {
  const anyExceeded = 
    (!research.unlimited && research.used >= research.limit) ||
    (!preparation.unlimited && preparation.used >= preparation.limit) ||
    (!followup.unlimited && followup.used >= followup.limit)

  return (
    <div className={cn("space-y-4", className)}>
      <UsageMeter
        label="Research"
        used={research.used}
        limit={research.limit}
        unlimited={research.unlimited}
        showUpgrade={false}
      />
      <UsageMeter
        label="Preparation"
        used={preparation.used}
        limit={preparation.limit}
        unlimited={preparation.unlimited}
        showUpgrade={false}
      />
      <UsageMeter
        label="Follow-up"
        used={followup.used}
        limit={followup.limit}
        unlimited={followup.unlimited}
        showUpgrade={false}
      />
      
      {anyExceeded && onUpgrade && (
        <button
          onClick={onUpgrade}
          className="w-full mt-2 px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-indigo-600 rounded-lg hover:from-blue-700 hover:to-indigo-700 transition-all"
        >
          Upgrade voor onbeperkt →
        </button>
      )}
    </div>
  )
}

