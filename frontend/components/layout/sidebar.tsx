'use client'

import { usePathname, useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'
import { Icons } from '@/components/icons'
import { Button } from '@/components/ui/button'
import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { Logo, LogoIcon } from '@/components/dealmotion-logo'

interface SidebarProps {
  className?: string
}

// Navigation items with translation keys
const navigationItems = [
  {
    key: 'dashboard',
    href: '/dashboard',
    icon: Icons.home,
    color: 'text-slate-500',
  },
  {
    key: 'prospects',
    href: '/dashboard/prospects',
    icon: Icons.building,
    color: 'text-cyan-500',
  },
  {
    key: 'research',
    href: '/dashboard/research',
    icon: Icons.search,
    color: 'text-blue-500',
  },
  {
    key: 'preparation',
    href: '/dashboard/preparation',
    icon: Icons.fileText,
    color: 'text-green-500',
  },
  {
    key: 'meetings',
    href: '/dashboard/meetings',
    icon: Icons.calendar,
    color: 'text-teal-500',
  },
  {
    key: 'followup',
    href: '/dashboard/followup',
    icon: Icons.mail,
    color: 'text-orange-500',
  },
  {
    key: 'recordings',
    href: '/dashboard/recordings',
    icon: Icons.mic,
    color: 'text-rose-500',
  },
]

const profileItems = [
  {
    key: 'profile',
    href: '/dashboard/profile',
    icon: Icons.user,
    color: 'text-violet-500',
  },
  {
    key: 'companyProfile',
    href: '/dashboard/company-profile',
    icon: Icons.building,
    color: 'text-indigo-500',
  },
  {
    key: 'knowledgeBase',
    href: '/dashboard/knowledge-base',
    icon: Icons.book,
    color: 'text-purple-500',
  },
]

const settingsItems = [
  {
    key: 'settings',
    href: '/dashboard/settings',
    icon: Icons.settings,
    color: 'text-slate-400',
  },
]

export function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname()
  const router = useRouter()
  const [collapsed, setCollapsed] = useState(false)
  const t = useTranslations('navigation')

  const isActive = (href: string) => {
    if (href === '/dashboard') {
      return pathname === '/dashboard'
    }
    return pathname.startsWith(href)
  }

  return (
    <aside
      className={cn(
        'flex flex-col h-screen bg-slate-900 text-white transition-all duration-300 flex-shrink-0',
        collapsed ? 'w-[72px]' : 'w-64',
        className
      )}
    >
      {/* Logo */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-slate-800">
        {!collapsed && (
          <Logo darkMode />
        )}
        {collapsed && (
          <LogoIcon className="mx-auto" />
        )}
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            'h-8 w-8 text-slate-400 hover:text-white hover:bg-slate-800',
            collapsed && 'hidden'
          )}
          onClick={() => setCollapsed(!collapsed)}
        >
          <Icons.panelLeftClose className="h-4 w-4" />
        </Button>
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="mb-4">
          {!collapsed && (
            <p className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Main
            </p>
          )}
          {navigationItems.map((item) => {
            const Icon = item.icon
            const active = isActive(item.href)
            const name = t(item.key)
            return (
              <button
                key={item.key}
                onClick={() => router.push(item.href)}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
                  active
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/50',
                  collapsed && 'justify-center px-2'
                )}
                title={collapsed ? name : undefined}
              >
                <Icon className={cn('h-5 w-5 flex-shrink-0', active ? item.color : '')} />
                {!collapsed && (
                  <span className="truncate">{name}</span>
                )}
              </button>
            )
          })}
        </div>

        {/* Profile Section */}
        <div className="pt-4 border-t border-slate-800">
          {!collapsed && (
            <p className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Profiles
            </p>
          )}
          {profileItems.map((item) => {
            const Icon = item.icon
            const active = isActive(item.href)
            const name = t(item.key)
            return (
              <button
                key={item.key}
                onClick={() => router.push(item.href)}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
                  active
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/50',
                  collapsed && 'justify-center px-2'
                )}
                title={collapsed ? name : undefined}
              >
                <Icon className={cn('h-5 w-5 flex-shrink-0', active ? item.color : '')} />
                {!collapsed && (
                  <span className="truncate">{name}</span>
                )}
              </button>
            )
          })}
        </div>

        {/* Settings Section */}
        <div className="pt-4 border-t border-slate-800">
          {settingsItems.map((item) => {
            const Icon = item.icon
            const active = isActive(item.href)
            const name = t(item.key)
            return (
              <button
                key={item.key}
                onClick={() => router.push(item.href)}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
                  active
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/50',
                  collapsed && 'justify-center px-2'
                )}
                title={collapsed ? name : undefined}
              >
                <Icon className={cn('h-5 w-5 flex-shrink-0', active ? item.color : '')} />
                {!collapsed && (
                  <span className="truncate">{name}</span>
                )}
              </button>
            )
          })}
        </div>
      </nav>

      {/* Collapse Toggle (when collapsed) */}
      {collapsed && (
        <div className="px-3 py-4 border-t border-slate-800">
          <Button
            variant="ghost"
            size="icon"
            className="w-full h-10 text-slate-400 hover:text-white hover:bg-slate-800"
            onClick={() => setCollapsed(false)}
          >
            <Icons.panelLeftOpen className="h-4 w-4" />
          </Button>
        </div>
      )}
    </aside>
  )
}

