'use client'

import * as React from 'react'
import { useTheme } from 'next-themes'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'

export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme()
  const [mounted, setMounted] = React.useState(false)

  // Avoid hydration mismatch
  React.useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return (
      <Button variant="ghost" size="sm" className="h-9 w-9 p-0">
        <div className="h-4 w-4" />
      </Button>
    )
  }

  const isDark = resolvedTheme === 'dark'

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      className="h-9 w-9 p-0 hover:bg-slate-100 dark:hover:bg-slate-800"
      title={isDark ? 'Licht thema' : 'Donker thema'}
    >
      {isDark ? (
        <Icons.sun className="h-4 w-4 text-yellow-500" />
      ) : (
        <Icons.moon className="h-4 w-4 text-slate-600" />
      )}
      <span className="sr-only">Wissel thema</span>
    </Button>
  )
}
