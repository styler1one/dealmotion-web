'use client'

/**
 * Home Page - Luna Unified AI Assistant
 * SPEC-046-Luna-Unified-AI-Assistant
 * 
 * The main home page with Luna's unified assistant.
 * Falls back to Autopilot if Luna is not enabled.
 */

import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { DashboardLayout } from '@/components/layout'
import { AutopilotHome } from '@/components/autopilot'
import { LunaHome, useLunaOptional } from '@/components/luna'
import { Icons } from '@/components/icons'
import type { User } from '@supabase/supabase-js'

function HomeContent() {
  const luna = useLunaOptional()
  
  // Show Luna Home if Luna is enabled
  if (luna?.isEnabled) {
    return <LunaHome />
  }
  
  // Fallback to Autopilot Home
  return <AutopilotHome />
}

export default function HomePage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadUser = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      setUser(user)
      
      if (!user) {
        router.push('/login')
        return
      }
      
      setLoading(false)
    }
    loadUser()
  }, [supabase, router])

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <div className="text-center">
          <Icons.spinner className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-sm text-slate-500 dark:text-slate-400">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <DashboardLayout user={user}>
      <div className="p-4 lg:p-6">
        <HomeContent />
      </div>
    </DashboardLayout>
  )
}
