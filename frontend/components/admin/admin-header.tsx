'use client'

import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { Icons } from '@/components/icons'
import { Button } from '@/components/ui/button'
import Link from 'next/link'
import type { AdminRole } from '@/types/admin'

interface AdminHeaderProps {
  className?: string
  role: AdminRole
  email?: string
}

// Breadcrumb mapping
const pathLabels: Record<string, string> = {
  admin: 'Admin',
  dashboard: 'Dashboard',
  users: 'Users',
  alerts: 'Alerts',
  health: 'System Health',
  billing: 'Billing',
  audit: 'Audit Log',
}

export function AdminHeader({ className, role, email }: AdminHeaderProps) {
  const pathname = usePathname()
  
  // Generate breadcrumbs from pathname
  const segments = pathname.split('/').filter(Boolean)
  const breadcrumbs = segments.map((segment, index) => {
    const href = '/' + segments.slice(0, index + 1).join('/')
    const label = pathLabels[segment] || segment
    const isLast = index === segments.length - 1
    
    // Check if this is a UUID (user detail page)
    const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(segment)
    if (isUuid) {
      return { href, label: 'User Detail', isLast }
    }
    
    return { href, label, isLast }
  })

  return (
    <header className={cn(
      'flex items-center justify-between px-6 py-4 bg-white dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800',
      className
    )}>
      {/* Breadcrumbs */}
      <nav className="flex items-center gap-2 text-sm">
        {breadcrumbs.map((crumb, index) => (
          <div key={crumb.href} className="flex items-center gap-2">
            {index > 0 && (
              <Icons.chevronRight className="h-4 w-4 text-slate-400" />
            )}
            {crumb.isLast ? (
              <span className="font-medium text-slate-900 dark:text-white">
                {crumb.label}
              </span>
            ) : (
              <Link 
                href={crumb.href}
                className="text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
              >
                {crumb.label}
              </Link>
            )}
          </div>
        ))}
      </nav>

      {/* User Info */}
      <div className="flex items-center gap-4">
        <div className="text-right">
          <div className="text-sm font-medium text-slate-900 dark:text-white">
            {email || 'Admin User'}
          </div>
          <div className="text-xs text-slate-500 dark:text-slate-400 capitalize">
            {role.replace('_', ' ')}
          </div>
        </div>
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-teal-400 to-cyan-500 flex items-center justify-center">
          <Icons.user className="h-4 w-4 text-white" />
        </div>
      </div>
    </header>
  )
}

