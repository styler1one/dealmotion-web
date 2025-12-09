'use client'

import { Sidebar } from './sidebar'
import { Header } from './header'
import { CoachProvider, CoachWidget } from '@/components/coach'
import type { User } from '@supabase/supabase-js'

interface DashboardLayoutProps {
  children: React.ReactNode
  user: User | null
}

export function DashboardLayout({ children, user }: DashboardLayoutProps) {
  return (
    <CoachProvider>
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
        
        {/* AI Sales Coach Widget */}
        <CoachWidget />
      </div>
    </CoachProvider>
  )
}

