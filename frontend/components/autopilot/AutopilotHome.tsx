'use client'

/**
 * Autopilot Home Component
 * SPEC-045 / TASK-048
 * 
 * Main home page layout with three zones:
 * 1. Luna Greeting
 * 2. Proposal Inbox
 * 3. Context Sidebar
 */

import React, { useState } from 'react'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { LunaGreeting } from './LunaGreeting'
import { ProposalInbox } from './ProposalInbox'
import { ContextSidebar } from './ContextSidebar'
import { AutopilotSettings } from './AutopilotSettings'
import { useAutopilot } from './AutopilotProvider'

export function AutopilotHome() {
  const { stats, isLoading } = useAutopilot()
  const [showSettings, setShowSettings] = useState(false)
  
  if (isLoading) {
    return <AutopilotHomeSkeleton />
  }
  
  return (
    <>
      <div className="max-w-7xl mx-auto">
        {/* Luna Greeting */}
        <div className="mb-6">
          {stats?.luna_greeting ? (
            <LunaGreeting greeting={stats.luna_greeting} />
          ) : (
            <LunaGreeting
              greeting={{
                mode: 'coach',
                message: 'Welkom! Autopilot zoekt naar kansen in je agenda.',
                emphasis: null,
                action: null,
                action_route: null,
                pending_count: 0,
                urgent_count: 0,
              }}
            />
          )}
        </div>
        
        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Proposal Inbox - Takes 2 columns */}
          <div className="lg:col-span-2">
            <ProposalInbox />
          </div>
          
          {/* Context Sidebar */}
          <div className="lg:col-span-1">
            <ContextSidebar
              stats={stats}
              onOpenSettings={() => setShowSettings(true)}
            />
          </div>
        </div>
      </div>
      
      {/* Settings Sheet */}
      <Sheet open={showSettings} onOpenChange={setShowSettings}>
        <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Autopilot Instellingen</SheetTitle>
          </SheetHeader>
          <div className="mt-6">
            <AutopilotSettings />
          </div>
        </SheetContent>
      </Sheet>
    </>
  )
}


function AutopilotHomeSkeleton() {
  return (
    <div className="max-w-7xl mx-auto">
      {/* Luna Greeting Skeleton */}
      <div className="mb-6">
        <Skeleton className="h-24 w-full rounded-xl" />
      </div>
      
      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Inbox Skeleton */}
        <div className="lg:col-span-2 space-y-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
        
        {/* Sidebar Skeleton */}
        <div className="lg:col-span-1 space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      </div>
    </div>
  )
}
