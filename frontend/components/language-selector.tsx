'use client'

import { useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Icons } from '@/components/icons'
import { locales, localeNames, localeFlags, type Locale } from '@/i18n/config'
import { useSettings } from '@/lib/settings-context'

interface LanguageSelectorProps {
  currentLocale?: Locale
  variant?: 'icon' | 'full'
}

export function LanguageSelector({ currentLocale = 'en', variant = 'icon' }: LanguageSelectorProps) {
  const router = useRouter()
  const [isPending, startTransition] = useTransition()
  const { updateSettings, loaded } = useSettings()

  const handleLocaleChange = async (newLocale: Locale) => {
    // Set cookie for locale preference
    document.cookie = `NEXT_LOCALE=${newLocale};path=/;max-age=31536000` // 1 year
    
    // Also update settings in database if user is logged in
    if (loaded) {
      try {
        await updateSettings({ app_language: newLocale })
      } catch (error) {
        // Settings update failed, but cookie is set so UI will still change
        console.error('Failed to update settings:', error)
      }
    }
    
    // Refresh the page to apply new locale
    startTransition(() => {
      router.refresh()
    })
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button 
          variant="ghost" 
          size={variant === 'icon' ? 'icon' : 'sm'}
          className="h-9 w-9 px-0"
          disabled={isPending}
        >
          {isPending ? (
            <Icons.spinner className="h-4 w-4 animate-spin" />
          ) : variant === 'icon' ? (
            <span className="text-lg">{localeFlags[currentLocale]}</span>
          ) : (
            <span className="flex items-center gap-2">
              <span>{localeFlags[currentLocale]}</span>
              <span className="text-sm">{localeNames[currentLocale]}</span>
            </span>
          )}
          <span className="sr-only">Change language</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        {locales.map((locale) => (
          <DropdownMenuItem
            key={locale}
            onClick={() => handleLocaleChange(locale)}
            className={`flex items-center gap-3 cursor-pointer ${
              locale === currentLocale ? 'bg-accent' : ''
            }`}
          >
            <span className="text-lg">{localeFlags[locale]}</span>
            <span className="flex-1">{localeNames[locale]}</span>
            {locale === currentLocale && (
              <Icons.check className="h-4 w-4 text-primary" />
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
