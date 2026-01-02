'use client'

import { CoachProvider, CoachWidget } from '@/components/coach'
import { AutopilotProvider } from '@/components/autopilot'

/**
 * Dashboard Layout
 * 
 * Wraps ALL dashboard pages with necessary context providers.
 * This ensures hooks like useAutopilot() work correctly.
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <AutopilotProvider>
      <CoachProvider>
        {children}
        <CoachWidget />
      </CoachProvider>
    </AutopilotProvider>
  )
}

