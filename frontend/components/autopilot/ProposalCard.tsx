'use client'

/**
 * Proposal Card Component
 * SPEC-045 / TASK-048
 * 
 * Displays a single autopilot proposal with actions.
 */

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Check, X, Clock, MoreHorizontal, RefreshCw, Loader2 } from 'lucide-react'
import type { AutopilotProposal } from '@/types/autopilot'
import {
  PROPOSAL_STATUS_COLORS,
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_TYPE_ICONS,
  SNOOZE_OPTIONS,
} from '@/types/autopilot'
import { useAutopilot } from './AutopilotProvider'

// Simple relative time formatter (native JS, no external deps)
function formatRelativeTime(date: Date): string {
  const now = new Date()
  const diffMs = date.getTime() - now.getTime()
  const diffMinutes = Math.round(diffMs / (1000 * 60))
  const diffHours = Math.round(diffMs / (1000 * 60 * 60))
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24))
  
  // Future dates
  if (diffMs > 0) {
    if (diffMinutes < 60) return `over ${diffMinutes} minuten`
    if (diffHours < 24) return `over ${diffHours} uur`
    return `over ${diffDays} dagen`
  }
  
  // Past dates
  const absDiffMinutes = Math.abs(diffMinutes)
  const absDiffHours = Math.abs(diffHours)
  const absDiffDays = Math.abs(diffDays)
  
  if (absDiffMinutes < 1) return 'zojuist'
  if (absDiffMinutes < 60) return `${absDiffMinutes} minuten geleden`
  if (absDiffHours < 24) return `${absDiffHours} uur geleden`
  return `${absDiffDays} dagen geleden`
}

interface ProposalCardProps {
  proposal: AutopilotProposal
}

export function ProposalCard({ proposal }: ProposalCardProps) {
  const router = useRouter()
  const { acceptProposal, declineProposal, snoozeProposal, retryProposal } = useAutopilot()
  const [isProcessing, setIsProcessing] = useState(false)
  
  const isActionable = proposal.status === 'proposed'
  const isFailed = proposal.status === 'failed'
  const isExecuting = proposal.status === 'executing' || proposal.status === 'accepted'
  
  const handleAccept = async () => {
    setIsProcessing(true)
    try {
      await acceptProposal(proposal.id)
    } finally {
      setIsProcessing(false)
    }
  }
  
  const handleDecline = async () => {
    setIsProcessing(true)
    try {
      await declineProposal(proposal.id)
    } finally {
      setIsProcessing(false)
    }
  }
  
  const handleSnooze = async (option: typeof SNOOZE_OPTIONS[0]) => {
    setIsProcessing(true)
    try {
      await snoozeProposal(proposal.id, option.getValue())
    } finally {
      setIsProcessing(false)
    }
  }
  
  const handleRetry = async () => {
    setIsProcessing(true)
    try {
      await retryProposal(proposal.id)
    } finally {
      setIsProcessing(false)
    }
  }
  
  const getTimeLabel = () => {
    if (proposal.expires_at) {
      const expiresAt = new Date(proposal.expires_at)
      if (expiresAt > new Date()) {
        return `Verloopt ${formatRelativeTime(expiresAt)}`
      }
    }
    return formatRelativeTime(new Date(proposal.created_at))
  }
  
  const getPriorityIndicator = () => {
    if (proposal.priority >= 90) {
      return <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" title="Zeer urgent" />
    }
    if (proposal.priority >= 80) {
      return <span className="w-2 h-2 bg-orange-500 rounded-full" title="Urgent" />
    }
    if (proposal.priority >= 70) {
      return <span className="w-2 h-2 bg-yellow-500 rounded-full" title="Belangrijk" />
    }
    return null
  }
  
  return (
    <Card className={`p-4 transition-all hover:shadow-md ${isExecuting ? 'border-blue-200 bg-blue-50/30' : ''} ${isFailed ? 'border-red-200 bg-red-50/30' : ''}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex items-center gap-2">
          <Badge className={PROPOSAL_STATUS_COLORS[proposal.status]}>
            {PROPOSAL_STATUS_LABELS[proposal.status]}
          </Badge>
          {getPriorityIndicator()}
        </div>
        <span className="text-xs text-gray-500">{getTimeLabel()}</span>
      </div>
      
      {/* Content */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xl">{PROPOSAL_TYPE_ICONS[proposal.proposal_type]}</span>
          <h3 className="font-medium text-gray-900">{proposal.title}</h3>
        </div>
        
        {proposal.description && (
          <p className="text-sm text-gray-500 mb-2">{proposal.description}</p>
        )}
        
        <div className="flex items-start gap-2 p-3 bg-gray-50 rounded-lg">
          <span className="text-lg">💬</span>
          <p className="text-sm text-gray-700 italic">{proposal.luna_message}</p>
        </div>
      </div>
      
      {/* Error message for failed proposals */}
      {isFailed && proposal.execution_error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-700">
            <strong>Fout:</strong> {proposal.execution_error}
          </p>
        </div>
      )}
      
      {/* Executing indicator */}
      {isExecuting && (
        <div className="mb-4 flex items-center gap-2 text-blue-600">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">Bezig met uitvoeren...</span>
        </div>
      )}
      
      {/* Actions */}
      <div className="flex items-center gap-2">
        {isActionable && (
          <>
            <Button
              size="sm"
              onClick={handleAccept}
              disabled={isProcessing}
              className="flex-1"
            >
              {isProcessing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <Check className="w-4 h-4 mr-1" />
                  Ja, doe maar
                </>
              )}
            </Button>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" disabled={isProcessing}>
                  <Clock className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {SNOOZE_OPTIONS.map((option) => (
                  <DropdownMenuItem
                    key={option.label}
                    onClick={() => handleSnooze(option)}
                  >
                    {option.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDecline}
              disabled={isProcessing}
            >
              <X className="w-4 h-4" />
            </Button>
          </>
        )}
        
        {isFailed && (
          <>
            <Button
              size="sm"
              variant="outline"
              onClick={handleRetry}
              disabled={isProcessing}
              className="flex-1"
            >
              {isProcessing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <RefreshCw className="w-4 h-4 mr-1" />
                  Opnieuw proberen
                </>
              )}
            </Button>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDecline}
              disabled={isProcessing}
            >
              <X className="w-4 h-4" />
            </Button>
          </>
        )}
        
        {proposal.status === 'completed' && proposal.artifacts.length > 0 && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              // Navigate to the first artifact
              const artifact = proposal.artifacts[0]
              if (artifact.type === 'research') {
                router.push(`/dashboard/research/${artifact.id}`)
              } else if (artifact.type === 'prep') {
                router.push(`/dashboard/preparation/${artifact.id}`)
              } else if (artifact.type === 'followup') {
                router.push(`/dashboard/followup/${artifact.id}`)
              }
            }}
            className="flex-1"
          >
            Bekijk resultaat
          </Button>
        )}
      </div>
    </Card>
  )
}
