'use client'

/**
 * Home Page - Luna Unified AI Assistant
 * SPEC-046-Luna-Unified-AI-Assistant
 * 
 * The main home page with Luna's unified assistant.
 * Falls back to Autopilot if Luna is not enabled.
 * 
 * NEW: Redirects new users to onboarding if they haven't completed it yet.
 * NEW: Links affiliate after OAuth signup (affiliate data stored in localStorage/cookie).
 */

import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useRouter, useSearchParams } from 'next/navigation'
import { useEffect, useState, useRef } from 'react'
import { DashboardLayout } from '@/components/layout'
import { AutopilotHome } from '@/components/autopilot'
import { LunaHome, useLunaOptional } from '@/components/luna'
import { Icons } from '@/components/icons'
import { linkAffiliateAfterOAuth, getStoredAffiliateData } from '@/lib/affiliate'
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
  const searchParams = useSearchParams()
  const supabase = createClientComponentClient()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const affiliateLinkAttempted = useRef(false)

  useEffect(() => {
    const loadUser = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      setUser(user)
      
      if (!user) {
        router.push('/login')
        return
      }
      
      const { data: session } = await supabase.auth.getSession()
      const accessToken = session?.session?.access_token
      
      // Try to link affiliate after OAuth (only once per session)
      // This handles the case where user signed up via OAuth and had an affiliate code stored
      // Safe: linkAffiliateAfterOAuth returns early if no affiliate data exists
      if (accessToken && !affiliateLinkAttempted.current) {
        affiliateLinkAttempted.current = true
        const affiliateData = getStoredAffiliateData()
        if (affiliateData?.code) {
          // Fire and forget - don't block the dashboard loading
          // Only call API if there's actually an affiliate code
          linkAffiliateAfterOAuth(accessToken).catch(err => {
            console.error('[Dashboard] Error linking affiliate:', err)
          })
        }
      }
      
      // Skip onboarding check if just completed onboarding
      const onboardingComplete = searchParams.get('onboarding') === 'complete'
      if (onboardingComplete) {
        setLoading(false)
        return
      }
      
      // Check if user needs onboarding (no sales profile)
      try {
        if (accessToken) {
          const response = await fetch(
            `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/sales/check`,
            {
              method: 'GET',
              headers: {
                'Authorization': `Bearer ${accessToken}`,
              },
            }
          )
          
          if (response.ok) {
            const data = await response.json()
            // Redirect to onboarding if no profile exists
            if (!data.exists) {
              router.push('/onboarding')
              return
            }
          }
        }
      } catch (err) {
        // If check fails, continue to dashboard (don't block user)
        console.error('[Dashboard] Error checking profile:', err)
      }
      
      setLoading(false)
    }
    loadUser()
  }, [supabase, router, searchParams])

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
