'use client'

/**
 * Proposal Inbox Component
 * SPEC-045 / TASK-048
 * 
 * Displays list of autopilot proposals with filtering.
 */

import React, { useState } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Inbox, Loader2, RefreshCw } from 'lucide-react'
import type { AutopilotProposal, ProposalStatus } from '@/types/autopilot'
import { ProposalCard } from './ProposalCard'
import { useAutopilot } from './AutopilotProvider'

type FilterTab = 'active' | 'proposed' | 'executing' | 'completed'

export function ProposalInbox() {
  const { proposals, counts, isLoading, refreshProposals } = useAutopilot()
  // Default to 'active' (proposed + executing) - hide completed by default
  const [activeTab, setActiveTab] = useState<FilterTab>('active')
  const [isRefreshing, setIsRefreshing] = useState(false)
  
  const handleRefresh = async () => {
    setIsRefreshing(true)
    try {
      await refreshProposals()
    } finally {
      setIsRefreshing(false)
    }
  }
  
  const filteredProposals = proposals.filter(p => {
    if (activeTab === 'active') {
      // Show only proposed and executing - hide completed by default
      return ['proposed', 'executing', 'accepted'].includes(p.status)
    }
    if (activeTab === 'executing') {
      return p.status === 'executing' || p.status === 'accepted'
    }
    if (activeTab === 'completed') {
      return ['completed', 'failed'].includes(p.status)
    }
    return p.status === activeTab
  })
  
  // Sort: proposed first (by priority), then executing, then completed
  const sortedProposals = [...filteredProposals].sort((a, b) => {
    const statusOrder: Record<ProposalStatus, number> = {
      proposed: 0,
      accepted: 1,
      executing: 2,
      failed: 3,
      completed: 4,
      snoozed: 5,
      declined: 6,
      expired: 7,
    }
    
    const statusDiff = statusOrder[a.status] - statusOrder[b.status]
    if (statusDiff !== 0) return statusDiff
    
    // Within same status, sort by priority (descending)
    if (a.priority !== b.priority) return b.priority - a.priority
    
    // Then by created_at (newest first)
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
  
  const pendingCount = counts.proposed
  const executingCount = counts.executing
  const completedCount = counts.completed
  const failedCount = counts.failed
  
  return (
    <Card className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Inbox className="w-5 h-5 text-gray-500" />
          <h2 className="text-lg font-semibold text-gray-900">
            Autopilot Inbox
          </h2>
          {pendingCount > 0 && (
            <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">
              {pendingCount} wachtend
            </Badge>
          )}
        </div>
        
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          disabled={isRefreshing}
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
        </Button>
      </div>
      
      {/* Filter Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as FilterTab)} className="mb-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="active" className="relative">
            Active
            {(pendingCount + executingCount) > 0 && (
              <span className="ml-1 bg-indigo-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                {pendingCount + executingCount}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="proposed" className="relative">
            New
            {pendingCount > 0 && (
              <span className="ml-1 bg-yellow-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                {pendingCount}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="executing">
            In Progress
            {executingCount > 0 && (
              <span className="ml-1 bg-blue-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                {executingCount}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="completed">
            History
            {(completedCount + failedCount) > 0 && (
              <span className="ml-1 bg-gray-400 text-white text-xs px-1.5 py-0.5 rounded-full">
                {completedCount + failedCount}
              </span>
            )}
          </TabsTrigger>
        </TabsList>
      </Tabs>
      
      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
        </div>
      ) : sortedProposals.length === 0 ? (
        <div className="text-center py-12">
          <Inbox className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-1">
            {activeTab === 'all' ? 'Geen voorstellen' : `Geen ${activeTab === 'proposed' ? 'nieuwe' : activeTab === 'executing' ? 'lopende' : activeTab === 'completed' ? 'afgeronde' : 'mislukte'} voorstellen`}
          </h3>
          <p className="text-sm text-gray-500">
            {activeTab === 'all' || activeTab === 'proposed' 
              ? 'Autopilot detecteert automatisch kansen en maakt voorstellen voor je.'
              : 'Bekijk andere tabs voor meer voorstellen.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {sortedProposals.map((proposal) => (
            <ProposalCard key={proposal.id} proposal={proposal} />
          ))}
        </div>
      )}
    </Card>
  )
}
