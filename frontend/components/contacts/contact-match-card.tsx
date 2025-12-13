'use client'

import { cn } from '@/lib/utils'
import { Icons } from '@/components/icons'

export interface ContactMatch {
  name: string
  title?: string | null
  company?: string | null
  location?: string | null
  linkedin_url?: string | null
  headline?: string | null
  confidence: number
  match_reason: string
  from_research?: boolean  // True if this match came from research data
}

interface ContactMatchCardProps {
  match: ContactMatch
  isSelected: boolean
  onSelect: () => void
}

export function ContactMatchCard({ match, isSelected, onSelect }: ContactMatchCardProps) {
  // Confidence color coding
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/30'
    if (confidence >= 0.5) return 'text-amber-600 dark:text-amber-400 bg-amber-100 dark:bg-amber-900/30'
    return 'text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/30'
  }

  const getConfidenceEmoji = (confidence: number) => {
    if (confidence >= 0.8) return '🟢'
    if (confidence >= 0.5) return '🟡'
    return '🔴'
  }

  const confidencePercent = Math.round(match.confidence * 100)

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full text-left p-4 rounded-lg border transition-all",
        "hover:border-blue-300 hover:bg-blue-50/50 dark:hover:bg-blue-900/20",
        isSelected
          ? "border-blue-500 bg-blue-50 dark:bg-blue-900/30 ring-2 ring-blue-500/30"
          : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Name and confidence badge */}
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="font-medium text-slate-900 dark:text-white truncate">
              👤 {match.name}
            </span>
            <span className={cn(
              "text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0",
              getConfidenceColor(match.confidence)
            )}>
              {getConfidenceEmoji(match.confidence)} {confidencePercent}%
            </span>
            {match.from_research && (
              <span className="text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400">
                📋 Research
              </span>
            )}
          </div>

          {/* Title and company */}
          {(match.title || match.company) && (
            <div className="text-sm text-slate-600 dark:text-slate-400 truncate">
              {match.title}
              {match.title && match.company && ' @ '}
              {match.company}
            </div>
          )}

          {/* Location */}
          {match.location && (
            <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-500 mt-1">
              <span>📍</span>
              <span>{match.location}</span>
            </div>
          )}

          {/* Headline */}
          {match.headline && (
            <div className="text-xs text-slate-500 dark:text-slate-500 mt-2 line-clamp-2 italic">
              "{match.headline}"
            </div>
          )}

          {/* Match reason */}
          <div className="flex items-center gap-1 text-xs text-slate-500 mt-2">
            {match.confidence >= 0.8 ? (
              <Icons.check className="h-3 w-3 text-green-500" />
            ) : (
              <Icons.info className="h-3 w-3 text-amber-500" />
            )}
            <span>{match.match_reason}</span>
          </div>
        </div>

        {/* Select indicator */}
        <div className={cn(
          "flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors",
          isSelected
            ? "border-blue-500 bg-blue-500"
            : "border-slate-300 dark:border-slate-600"
        )}>
          {isSelected && <Icons.check className="h-3 w-3 text-white" />}
        </div>
      </div>

      {/* LinkedIn URL preview */}
      {match.linkedin_url && (
        <div className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 mt-2 truncate">
          <Icons.link className="h-3 w-3 flex-shrink-0" />
          <span className="truncate">{match.linkedin_url}</span>
        </div>
      )}
    </button>
  )
}

