'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { ThemeToggle } from '@/components/theme-toggle'
import { LanguageSelector } from '@/components/language-selector'
import { CreditWidget } from '@/components/credit-widget'
import { cn } from '@/lib/utils'
import { useLocale, useTranslations } from 'next-intl'
import type { Locale } from '@/i18n/config'
import type { User } from '@supabase/supabase-js'

interface HeaderProps {
  user: User | null
  className?: string
}

export function Header({ user, className }: HeaderProps) {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const locale = useLocale() as Locale
  const t = useTranslations('navigation')

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    router.push('/login')
  }

  return (
    <header className={cn('h-16 border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm sticky top-0 z-40', className)}>
      <div className="h-full px-6 flex items-center justify-between">
        {/* Left side - can add breadcrumbs here */}
        <div className="flex items-center gap-4">
          {/* Mobile menu button - shown on small screens */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label={t('mobileMenu')}
          >
            <Icons.menu className="h-5 w-5" aria-hidden="true" />
          </Button>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3">
          {/* Credit Balance Widget */}
          <CreditWidget />

          {/* Language Selector */}
          <LanguageSelector currentLocale={locale} />

          {/* Theme Toggle */}
          <ThemeToggle />

          {/* Notifications */}
          <Button variant="ghost" size="icon" className="relative" aria-label={t('notifications')}>
            <Icons.bell className="h-5 w-5" aria-hidden="true" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" aria-hidden="true" />
            <span className="sr-only">{t('notificationsCount', { count: 1 })}</span>
          </Button>

          {/* User Dropdown */}
          <div className="relative">
            <Button
              variant="ghost"
              className="flex items-center gap-2 px-2"
              onClick={() => setDropdownOpen(!dropdownOpen)}
            >
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white font-medium text-sm">
                {user?.email?.charAt(0).toUpperCase() || 'U'}
              </div>
              <span className="hidden md:block text-sm font-medium max-w-[150px] truncate text-slate-900 dark:text-white">
                {user?.email?.split('@')[0] || 'User'}
              </span>
              <Icons.chevronDown className="h-4 w-4 text-muted-foreground" />
            </Button>

            {/* Dropdown Menu */}
            {dropdownOpen && (
              <>
                <div 
                  className="fixed inset-0 z-40" 
                  onClick={() => setDropdownOpen(false)}
                />
                <div className="absolute right-0 mt-2 w-56 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-lg z-50 animate-scale-in">
                  <div className="p-3 border-b border-slate-200 dark:border-slate-700">
                    <p className="text-sm font-medium text-slate-900 dark:text-white">{user?.email?.split('@')[0]}</p>
                    <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
                  </div>
                  <div className="p-1">
                    <button
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left rounded-md text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                      onClick={() => {
                        router.push('/dashboard/profile')
                        setDropdownOpen(false)
                      }}
                    >
                      <Icons.user className="h-4 w-4" />
                      {t('profile')}
                    </button>
                    <button
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left rounded-md text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                      onClick={() => {
                        router.push('/dashboard/company-profile')
                        setDropdownOpen(false)
                      }}
                    >
                      <Icons.building className="h-4 w-4" />
                      {t('companyProfile')}
                    </button>
                    <button
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left rounded-md text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                      onClick={() => {
                        router.push('/dashboard/settings')
                        setDropdownOpen(false)
                      }}
                    >
                      <Icons.settings className="h-4 w-4" />
                      {t('settings')}
                    </button>
                  </div>
                  <div className="p-1 border-t border-slate-200 dark:border-slate-700">
                    <button
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 text-red-600 dark:text-red-400 transition-colors"
                      onClick={handleSignOut}
                    >
                      <Icons.logOut className="h-4 w-4" />
                      {t('logout')}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}

