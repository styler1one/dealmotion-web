'use client'

import { Sidebar } from './sidebar'
import { Header } from './header'
import type { User } from '@supabase/supabase-js'

interface DashboardLayoutProps {
  children: React.ReactNode
  user: User | null
}

/**
 * DashboardLayout component - provides the visual layout.
 * 
 * Note: Context providers (AutopilotProvider, CoachProvider) are in
 * app/dashboard/layout.tsx to ensure hooks work correctly.
 */
export function DashboardLayout({ children, user }: DashboardLayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        <Header user={user} />
        
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  )
}

