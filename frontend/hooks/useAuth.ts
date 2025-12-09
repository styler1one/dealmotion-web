'use client'

import { useState, useEffect, useCallback } from 'react'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useRouter } from 'next/navigation'
import type { User } from '@/types'

interface UseAuthOptions {
  /** Redirect to login if not authenticated */
  requireAuth?: boolean
  /** Path to redirect to when not authenticated */
  redirectTo?: string
}

interface UseAuthReturn {
  /** The current user, or null if not authenticated */
  user: User | null
  /** Whether the auth state is still loading */
  loading: boolean
  /** Whether the user is authenticated */
  isAuthenticated: boolean
  /** The Supabase client instance */
  supabase: ReturnType<typeof createClientComponentClient>
  /** Sign out the current user */
  signOut: () => Promise<void>
  /** Refresh the user data */
  refreshUser: () => Promise<void>
  /** Get the current access token */
  getAccessToken: () => Promise<string | null>
}

/**
 * Hook for managing authentication state.
 * 
 * @example
 * ```tsx
 * // Basic usage
 * const { user, loading } = useAuth()
 * 
 * // With required auth (redirects to login if not authenticated)
 * const { user, loading } = useAuth({ requireAuth: true })
 * 
 * // Custom redirect path
 * const { user, loading } = useAuth({ requireAuth: true, redirectTo: '/custom-login' })
 * ```
 */
export function useAuth(options: UseAuthOptions = {}): UseAuthReturn {
  const { requireAuth = false, redirectTo = '/login' } = options
  
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()
  const supabase = createClientComponentClient()

  const refreshUser = useCallback(async () => {
    try {
      const { data: { user: authUser } } = await supabase.auth.getUser()
      
      if (authUser) {
        setUser({
          id: authUser.id,
          email: authUser.email || '',
          created_at: authUser.created_at,
          user_metadata: authUser.user_metadata as User['user_metadata'],
          app_metadata: authUser.app_metadata as User['app_metadata'],
        })
      } else {
        setUser(null)
        if (requireAuth) {
          router.push(redirectTo)
        }
      }
    } catch (error) {
      console.error('Error fetching user:', error)
      setUser(null)
      if (requireAuth) {
        router.push(redirectTo)
      }
    } finally {
      setLoading(false)
    }
  }, [supabase, requireAuth, redirectTo, router])

  const signOut = useCallback(async () => {
    try {
      await supabase.auth.signOut()
      setUser(null)
      router.push('/login')
      router.refresh()
    } catch (error) {
      console.error('Error signing out:', error)
      throw error
    }
  }, [supabase, router])

  const getAccessToken = useCallback(async (): Promise<string | null> => {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      return session?.access_token || null
    } catch (error) {
      console.error('Error getting access token:', error)
      return null
    }
  }, [supabase])

  // Initial load
  useEffect(() => {
    refreshUser()
  }, [refreshUser])

  // Listen for auth state changes
  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if (event === 'SIGNED_IN' && session?.user) {
          setUser({
            id: session.user.id,
            email: session.user.email || '',
            created_at: session.user.created_at,
            user_metadata: session.user.user_metadata as User['user_metadata'],
            app_metadata: session.user.app_metadata as User['app_metadata'],
          })
          setLoading(false)
        } else if (event === 'SIGNED_OUT') {
          setUser(null)
          setLoading(false)
          if (requireAuth) {
            router.push(redirectTo)
          }
        } else if (event === 'TOKEN_REFRESHED' && session?.user) {
          // Update user data on token refresh
          setUser({
            id: session.user.id,
            email: session.user.email || '',
            created_at: session.user.created_at,
            user_metadata: session.user.user_metadata as User['user_metadata'],
            app_metadata: session.user.app_metadata as User['app_metadata'],
          })
        }
      }
    )

    return () => {
      subscription.unsubscribe()
    }
  }, [supabase, requireAuth, redirectTo, router])

  return {
    user,
    loading,
    isAuthenticated: !!user,
    supabase,
    signOut,
    refreshUser,
    getAccessToken,
  }
}

/**
 * Hook that requires authentication.
 * Automatically redirects to login if not authenticated.
 * 
 * @example
 * ```tsx
 * const { user, loading } = useRequireAuth()
 * 
 * if (loading) return <Spinner />
 * // user is guaranteed to be non-null here
 * ```
 */
export function useRequireAuth(redirectTo = '/login'): UseAuthReturn {
  return useAuth({ requireAuth: true, redirectTo })
}

