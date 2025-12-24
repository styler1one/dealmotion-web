'use client'

import { usePathname, useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'
import { Icons } from '@/components/icons'
import { Button } from '@/components/ui/button'
import { useState } from 'react'
import { LogoIcon } from '@/components/dealmotion-logo'
import type { AdminRole } from '@/types/admin'

interface AdminSidebarProps {
  className?: string
  role: AdminRole
}

// Navigation items
const navigationItems = [
  {
    key: 'dashboard',
    label: 'Dashboard',
    href: '/admin/dashboard',
    icon: Icons.home,
    color: 'text-slate-400',
    roles: ['super_admin', 'admin', 'support', 'viewer'] as AdminRole[],
  },
  {
    key: 'users',
    label: 'Users',
    href: '/admin/users',
    icon: Icons.users,
    color: 'text-blue-400',
    roles: ['super_admin', 'admin', 'support', 'viewer'] as AdminRole[],
  },
  {
    key: 'alerts',
    label: 'Alerts',
    href: '/admin/alerts',
    icon: Icons.alertTriangle,
    color: 'text-yellow-400',
    roles: ['super_admin', 'admin', 'support', 'viewer'] as AdminRole[],
  },
  {
    key: 'health',
    label: 'System Health',
    href: '/admin/health',
    icon: Icons.activity,
    color: 'text-green-400',
    roles: ['super_admin', 'admin', 'support', 'viewer'] as AdminRole[],
  },
  {
    key: 'billing',
    label: 'Billing',
    href: '/admin/billing',
    icon: Icons.creditCard,
    color: 'text-purple-400',
    roles: ['super_admin', 'admin'] as AdminRole[],
  },
  {
    key: 'affiliates',
    label: 'Affiliates',
    href: '/admin/affiliates',
    icon: Icons.gift,
    color: 'text-pink-400',
    roles: ['super_admin', 'admin'] as AdminRole[],
  },
  {
    key: 'audit',
    label: 'Audit Log',
    href: '/admin/audit',
    icon: Icons.fileText,
    color: 'text-slate-400',
    roles: ['super_admin', 'admin'] as AdminRole[],
  },
]

export function AdminSidebar({ className, role }: AdminSidebarProps) {
  const pathname = usePathname()
  const router = useRouter()
  const [collapsed, setCollapsed] = useState(false)

  const isActive = (href: string) => {
    if (href === '/admin/dashboard') {
      return pathname === '/admin' || pathname === '/admin/dashboard'
    }
    return pathname.startsWith(href)
  }

  // Filter items based on role
  const visibleItems = navigationItems.filter(item => item.roles.includes(role))

  const getRoleBadge = () => {
    const roleColors: Record<AdminRole, string> = {
      super_admin: 'bg-red-500/20 text-red-300',
      admin: 'bg-blue-500/20 text-blue-300',
      support: 'bg-green-500/20 text-green-300',
      viewer: 'bg-slate-500/20 text-slate-300',
    }
    const roleLabels: Record<AdminRole, string> = {
      super_admin: 'Super Admin',
      admin: 'Admin',
      support: 'Support',
      viewer: 'Viewer',
    }
    return (
      <span className={cn('text-[10px] px-2 py-0.5 rounded-full font-medium', roleColors[role])}>
        {roleLabels[role]}
      </span>
    )
  }

  return (
    <aside
      className={cn(
        'flex flex-col h-screen bg-slate-900 text-white transition-all duration-300 flex-shrink-0 border-r border-slate-800',
        collapsed ? 'w-[72px]' : 'w-64',
        className
      )}
    >
      {/* Logo */}
      <div className={cn(
        'flex items-center gap-3 p-4 border-b border-slate-800',
        collapsed ? 'justify-center' : 'justify-between'
      )}>
        <button
          onClick={() => router.push('/admin/dashboard')}
          className="flex items-center gap-2 hover:opacity-80 transition-opacity"
        >
          <LogoIcon className="w-8 h-8" />
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-bold text-lg tracking-tight">Admin</span>
              {getRoleBadge()}
            </div>
          )}
        </button>
        
        {!collapsed && (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setCollapsed(true)}
            className="text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <Icons.chevronLeft className="h-4 w-4" />
          </Button>
        )}
      </div>

      {collapsed && (
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setCollapsed(false)}
          className="mx-auto mt-2 text-slate-400 hover:text-white hover:bg-slate-800"
        >
          <Icons.chevronRight className="h-4 w-4" />
        </Button>
      )}

      {/* Navigation */}
      <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
        {visibleItems.map((item) => {
          const Icon = item.icon
          const active = isActive(item.href)
          
          return (
            <Button
              key={item.key}
              variant="ghost"
              onClick={() => router.push(item.href)}
              className={cn(
                'w-full justify-start gap-3 h-10 font-medium transition-all',
                collapsed ? 'px-3' : 'px-3',
                active
                  ? 'bg-slate-800 text-white hover:bg-slate-700'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              )}
            >
              <Icon className={cn('h-5 w-5 flex-shrink-0', active && item.color)} />
              {!collapsed && <span>{item.label}</span>}
            </Button>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-2 border-t border-slate-800">
        <Button
          variant="ghost"
          onClick={() => router.push('/dashboard')}
          className={cn(
            'w-full justify-start gap-3 h-10 text-slate-400 hover:text-white hover:bg-slate-800',
            collapsed ? 'px-3' : 'px-3'
          )}
        >
          <Icons.arrowLeft className="h-5 w-5 flex-shrink-0" />
          {!collapsed && <span>Back to App</span>}
        </Button>
      </div>
    </aside>
  )
}

