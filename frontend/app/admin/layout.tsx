'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { AdminSidebar } from '@/components/admin/admin-sidebar'
import { AdminHeader } from '@/components/admin/admin-header'
import { adminApi } from '@/lib/admin-api'
import { Icons } from '@/components/icons'
import type { AdminRole, AdminCheckResponse } from '@/types/admin'

interface AdminLayoutProps {
  children: React.ReactNode
}

export default function AdminLayout({ children }: AdminLayoutProps) {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const [loading, setLoading] = useState(true)
  const [adminData, setAdminData] = useState<AdminCheckResponse | null>(null)
  const [email, setEmail] = useState<string>('')

  useEffect(() => {
    const checkAdminAccess = async () => {
      try {
        // Check if user is logged in
        const { data: { session } } = await supabase.auth.getSession()
        
        if (!session) {
          router.push('/login?redirect=/admin')
          return
        }

        setEmail(session.user.email || '')

        // Check admin access
        const data = await adminApi.checkAccess()
        
        if (!data.isAdmin) {
          // Not an admin, redirect to dashboard
          router.push('/dashboard')
          return
        }

        setAdminData(data)
      } catch (error) {
        console.error('Admin access check failed:', error)
        // Redirect to dashboard if admin check fails
        router.push('/dashboard')
      } finally {
        setLoading(false)
      }
    }

    checkAdminAccess()
  }, [router, supabase])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-100 dark:bg-slate-950">
        <div className="flex flex-col items-center gap-4">
          <Icons.spinner className="h-8 w-8 animate-spin text-teal-500" />
          <p className="text-slate-500 dark:text-slate-400">Verifying admin access...</p>
        </div>
      </div>
    )
  }

  if (!adminData) {
    return null
  }

  return (
    <div className="flex h-screen bg-slate-100 dark:bg-slate-950">
      <AdminSidebar role={adminData.role} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <AdminHeader role={adminData.role} email={email} />
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}

