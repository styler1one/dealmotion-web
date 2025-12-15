'use client'

/**
 * Context Sidebar Component
 * SPEC-045 / TASK-048
 * 
 * Shows context information: profile, flows, upcoming meetings.
 */

import React from 'react'
import { useRouter } from 'next/navigation'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Calendar, Clock, Building2, User, Settings } from 'lucide-react'
import type { UpcomingMeeting, AutopilotStats } from '@/types/autopilot'
import { formatDistanceToNow, format } from 'date-fns'
import { nl } from 'date-fns/locale'

interface ContextSidebarProps {
  stats: AutopilotStats | null
  onOpenSettings?: () => void
}

export function ContextSidebar({ stats, onOpenSettings }: ContextSidebarProps) {
  const router = useRouter()
  
  const upcomingMeetings = stats?.upcoming_meetings || []
  
  return (
    <div className="space-y-4">
      {/* Quick Stats */}
      <Card className="p-4">
        <h3 className="text-sm font-medium text-gray-500 mb-3">Vandaag</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="text-center p-3 bg-gray-50 rounded-lg">
            <div className="text-2xl font-bold text-gray-900">
              {stats?.completed_today || 0}
            </div>
            <div className="text-xs text-gray-500">Afgerond</div>
          </div>
          <div className="text-center p-3 bg-gray-50 rounded-lg">
            <div className="text-2xl font-bold text-gray-900">
              {stats?.pending_count || 0}
            </div>
            <div className="text-xs text-gray-500">Wachtend</div>
          </div>
        </div>
      </Card>
      
      {/* Upcoming Meetings */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-500 flex items-center gap-2">
            <Calendar className="w-4 h-4" />
            Komende meetings
          </h3>
        </div>
        
        {upcomingMeetings.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">
            Geen meetings gepland
          </p>
        ) : (
          <div className="space-y-3">
            {upcomingMeetings.slice(0, 3).map((meeting) => (
              <MeetingItem
                key={meeting.id}
                meeting={meeting}
                onClick={() => {
                  if (meeting.has_prep && meeting.prospect_id) {
                    router.push(`/dashboard/preparation?prospect=${meeting.prospect_id}`)
                  } else {
                    router.push(`/dashboard/meetings`)
                  }
                }}
              />
            ))}
          </div>
        )}
        
        {upcomingMeetings.length > 3 && (
          <Button
            variant="ghost"
            size="sm"
            className="w-full mt-2"
            onClick={() => router.push('/dashboard/meetings')}
          >
            Bekijk alle meetings
          </Button>
        )}
      </Card>
      
      {/* Settings Link */}
      {onOpenSettings && (
        <Card className="p-4">
          <Button
            variant="outline"
            className="w-full"
            onClick={onOpenSettings}
          >
            <Settings className="w-4 h-4 mr-2" />
            Autopilot instellingen
          </Button>
        </Card>
      )}
    </div>
  )
}


interface MeetingItemProps {
  meeting: UpcomingMeeting
  onClick: () => void
}

function MeetingItem({ meeting, onClick }: MeetingItemProps) {
  const startTime = new Date(meeting.start_time)
  const isUrgent = meeting.starts_in_hours < 2
  
  return (
    <button
      onClick={onClick}
      className="w-full text-left p-3 rounded-lg border border-gray-100 hover:border-gray-200 hover:bg-gray-50 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-gray-900 truncate text-sm">
            {meeting.company || meeting.title}
          </p>
          <div className="flex items-center gap-2 mt-1">
            <Clock className="w-3 h-3 text-gray-400" />
            <span className="text-xs text-gray-500">
              {format(startTime, 'HH:mm', { locale: nl })}
            </span>
            {isUrgent && (
              <Badge variant="destructive" className="text-xs px-1.5 py-0">
                Binnenkort
              </Badge>
            )}
          </div>
        </div>
        
        <div className="flex-shrink-0">
          {meeting.has_prep ? (
            <Badge variant="secondary" className="bg-green-100 text-green-800 text-xs">
              Prep ✓
            </Badge>
          ) : (
            <Badge variant="secondary" className="bg-yellow-100 text-yellow-800 text-xs">
              Geen prep
            </Badge>
          )}
        </div>
      </div>
    </button>
  )
}
