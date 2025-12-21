'use client'

/**
 * Proposal Card Component
 * SPEC-045 / TASK-048
 * 
 * Displays a single autopilot proposal with actions.
 * Supports inline modals/sheets for actions:
 * - add_contacts: ContactSearchModal
 * - create_prep: PreparationForm in Sheet
 * - meeting_analysis: FollowupUploadForm in Sheet
 */

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Check, X, Clock, RefreshCw, Loader2, UserPlus, FileText, Mic, Calendar } from 'lucide-react'
import type { AutopilotProposal } from '@/types/autopilot'
import {
  PROPOSAL_STATUS_COLORS,
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_TYPE_ICONS,
  SNOOZE_OPTIONS,
} from '@/types/autopilot'
import { useAutopilot } from './AutopilotProvider'
import { ContactSearchModal } from '@/components/contacts/contact-search-modal'
import { PreparationForm } from '@/components/forms/PreparationForm'
import { FollowupUploadForm } from '@/components/forms/FollowupUploadForm'
import { MeetingRequestSheet } from './MeetingRequestSheet'

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
  const { acceptProposal, completeProposal, declineProposal, snoozeProposal, retryProposal, refreshProposals } = useAutopilot()
  const [isProcessing, setIsProcessing] = useState(false)
  
  // Sheet/Modal states for inline actions
  const [showContactModal, setShowContactModal] = useState(false)
  const [showPrepSheet, setShowPrepSheet] = useState(false)
  const [showFollowupSheet, setShowFollowupSheet] = useState(false)
  const [showMeetingSheet, setShowMeetingSheet] = useState(false)
  
  const isActionable = proposal.status === 'proposed'
  const isFailed = proposal.status === 'failed'
  const isExecuting = proposal.status === 'executing' || proposal.status === 'accepted'
  
  // Extract context data for inline actions
  const flowStep = proposal.context_data?.flow_step as string | undefined
  const researchId = proposal.context_data?.research_id as string | undefined
  const prospectId = proposal.context_data?.prospect_id as string | undefined
  const companyName = proposal.context_data?.company_name as string | undefined
  const contactId = proposal.context_data?.contact_id as string | undefined
  const prepId = proposal.context_data?.prep_id as string | undefined
  
  // Determine which inline action to use
  const isAddContactsAction = flowStep === 'add_contacts'
  const isCreatePrepAction = flowStep === 'create_prep'
  const isMeetingAnalysisAction = flowStep === 'meeting_analysis'
  const isPlanMeetingAction = flowStep === 'plan_meeting'
  const hasInlineAction = isAddContactsAction || isCreatePrepAction || isMeetingAnalysisAction || isPlanMeetingAction
  
  const handleAccept = async () => {
    // For inline actions, open the appropriate modal/sheet
    if (isAddContactsAction && researchId) {
      setShowContactModal(true)
      return
    }
    
    if (isCreatePrepAction) {
      setShowPrepSheet(true)
      return
    }
    
    if (isMeetingAnalysisAction) {
      setShowFollowupSheet(true)
      return
    }
    
    if (isPlanMeetingAction && prospectId && prepId) {
      setShowMeetingSheet(true)
      return
    }
    
    // Default: trigger backend execution
    setIsProcessing(true)
    try {
      await acceptProposal(proposal.id)
    } finally {
      setIsProcessing(false)
    }
  }
  
  // Called when inline action is completed successfully
  const handleInlineActionComplete = async () => {
    setShowContactModal(false)
    setShowPrepSheet(false)
    setShowFollowupSheet(false)
    setShowMeetingSheet(false)
    
    // Mark proposal as completed directly (skip Inngest execution)
    setIsProcessing(true)
    try {
      await completeProposal(proposal.id)
      await refreshProposals()
    } finally {
      setIsProcessing(false)
    }
  }
  
  // Get the appropriate button label and icon for inline actions
  const getActionButton = () => {
    if (isAddContactsAction) {
      return { icon: <UserPlus className="w-4 h-4 mr-1" />, label: 'Voeg contact toe' }
    }
    if (isCreatePrepAction) {
      return { icon: <FileText className="w-4 h-4 mr-1" />, label: 'Maak prep' }
    }
    if (isMeetingAnalysisAction) {
      return { icon: <Mic className="w-4 h-4 mr-1" />, label: 'Upload recording' }
    }
    if (isPlanMeetingAction) {
      return { icon: <Calendar className="w-4 h-4 mr-1" />, label: 'Plan meeting' }
    }
    return { icon: <Check className="w-4 h-4 mr-1" />, label: 'Ja, doe maar' }
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
        
        <div className="flex items-start gap-2 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
          <span className="text-lg">💬</span>
          <p className="text-sm text-gray-700 dark:text-gray-300 italic">{proposal.luna_message}</p>
        </div>
        
        {/* Why this proposal - explanation */}
        {proposal.proposal_reason && (
          <div className="mt-2 flex items-start gap-2 text-xs text-gray-500 dark:text-gray-400">
            <span className="font-medium">Why?</span>
            <span>{proposal.proposal_reason}</span>
          </div>
        )}
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
      
      {/* Contact Search Modal for add_contacts proposals */}
      {isAddContactsAction && researchId && (
        <ContactSearchModal
          isOpen={showContactModal}
          onClose={() => setShowContactModal(false)}
          companyName={companyName || 'Onbekend'}
          researchId={researchId}
          onContactAdded={handleInlineActionComplete}
        />
      )}
      
      {/* Preparation Sheet for create_prep proposals */}
      <Sheet open={showPrepSheet} onOpenChange={setShowPrepSheet}>
        <SheetContent side="right" className="sm:max-w-md overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-600" />
              Prep maken
            </SheetTitle>
            <SheetDescription>
              Maak een meeting prep voor {companyName || 'dit bedrijf'}
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4">
            <PreparationForm
              initialCompanyName={companyName || ''}
              initialProspectId={prospectId}
              initialSelectedContactIds={contactId ? [contactId] : []}
              onSuccess={() => handleInlineActionComplete()}
              onCancel={() => setShowPrepSheet(false)}
              isSheet={true}
            />
          </div>
        </SheetContent>
      </Sheet>
      
      {/* Follow-up Upload Sheet for meeting_analysis proposals */}
      <Sheet open={showFollowupSheet} onOpenChange={setShowFollowupSheet}>
        <SheetContent side="right" className="sm:max-w-md overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Mic className="w-5 h-5 text-orange-600" />
              Meeting analyse
            </SheetTitle>
            <SheetDescription>
              Upload een recording of transcript voor {companyName || 'dit bedrijf'}
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4">
            <FollowupUploadForm
              initialProspectCompany={companyName || ''}
              onSuccess={() => handleInlineActionComplete()}
              onCancel={() => setShowFollowupSheet(false)}
              isSheet={true}
            />
          </div>
        </SheetContent>
      </Sheet>
      
      {/* Meeting Request Sheet for plan_meeting proposals */}
      <Sheet open={showMeetingSheet} onOpenChange={setShowMeetingSheet}>
        <SheetContent side="right" className="sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Calendar className="w-5 h-5 text-green-600" />
              Meeting plannen
            </SheetTitle>
            <SheetDescription>
              Plan een meeting met {companyName || 'dit bedrijf'}
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4">
            {prospectId && prepId && (
              <MeetingRequestSheet
                prospectId={prospectId}
                prepId={prepId}
                companyName={companyName || 'Onbekend'}
                onComplete={() => handleInlineActionComplete()}
                onCancel={() => setShowMeetingSheet(false)}
              />
            )}
          </div>
        </SheetContent>
      </Sheet>
      
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
                  {getActionButton().icon}
                  {getActionButton().label}
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
        
        {proposal.status === 'completed' && proposal.artifacts && proposal.artifacts.length > 0 && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              // Find the best artifact to navigate to
              const redirectArtifact = proposal.artifacts.find(a => a.type === 'redirect')
              if (redirectArtifact && redirectArtifact.route) {
                router.push(redirectArtifact.route)
                return
              }
              
              // Navigate to the first content artifact
              const artifact = proposal.artifacts.find(a => a.type !== 'redirect')
              if (artifact) {
                if (artifact.type === 'research') {
                  router.push(`/dashboard/research/${artifact.id}`)
                } else if (artifact.type === 'prep') {
                  router.push(`/dashboard/preparation/${artifact.id}`)
                } else if (artifact.type === 'followup') {
                  router.push(`/dashboard/followup/${artifact.id}`)
                }
              }
            }}
            className="flex-1"
          >
            {proposal.artifacts.some(a => a.type === 'redirect') ? 'Ga naar pagina' : 'Bekijk resultaat'}
          </Button>
        )}
      </div>
    </Card>
  )
}
