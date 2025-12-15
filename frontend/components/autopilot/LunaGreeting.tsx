'use client'

/**
 * Luna Greeting Component
 * SPEC-045 / TASK-048
 * 
 * Displays Luna's dynamic greeting based on context.
 */

import React from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import type { LunaGreeting as LunaGreetingType } from '@/types/autopilot'
import { LUNA_MODE_ICONS } from '@/types/autopilot'

interface LunaGreetingProps {
  greeting: LunaGreetingType
}

export function LunaGreeting({ greeting }: LunaGreetingProps) {
  const router = useRouter()
  
  const modeStyles = {
    morning: 'bg-gradient-to-r from-amber-50 to-orange-50 border-amber-200',
    proposal: 'bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200',
    urgency: 'bg-gradient-to-r from-red-50 to-orange-50 border-red-200',
    celebration: 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-200',
    coach: 'bg-gradient-to-r from-purple-50 to-pink-50 border-purple-200',
  }
  
  const handleAction = () => {
    if (greeting.action_route) {
      router.push(greeting.action_route)
    }
  }
  
  return (
    <Card className={`p-6 border ${modeStyles[greeting.mode]}`}>
      <div className="flex items-start gap-4">
        {/* Luna Avatar */}
        <div className="flex-shrink-0">
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg">
            <span className="text-2xl">🌙</span>
          </div>
        </div>
        
        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-gray-900">Luna</span>
            <span className="text-lg">{LUNA_MODE_ICONS[greeting.mode]}</span>
          </div>
          
          <p className="text-gray-700 text-base leading-relaxed">
            {greeting.message}
          </p>
          
          {greeting.emphasis && (
            <p className="text-sm text-gray-500 mt-1">
              {greeting.emphasis}
            </p>
          )}
          
          {greeting.action && greeting.action_route && (
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={handleAction}
            >
              {greeting.action}
            </Button>
          )}
        </div>
        
        {/* Stats Badge */}
        {greeting.pending_count > 0 && (
          <div className="flex-shrink-0">
            <div className="flex flex-col items-center gap-1">
              <div className="bg-yellow-100 text-yellow-800 text-sm font-medium px-3 py-1 rounded-full">
                {greeting.pending_count} wachtend
              </div>
              {greeting.urgent_count > 0 && (
                <div className="bg-red-100 text-red-800 text-xs font-medium px-2 py-0.5 rounded-full">
                  {greeting.urgent_count} urgent
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}
