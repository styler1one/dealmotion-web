'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { CheckCircle2, ArrowRight, Sparkles } from 'lucide-react'
import { useTranslations } from 'next-intl'

export default function BillingSuccessPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [countdown, setCountdown] = useState(5)
  const t = useTranslations('billing')
  const tNav = useTranslations('navigation')

  useEffect(() => {
    // Countdown and redirect
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer)
          router.push('/dashboard')
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [router])

  return (
    <div className="min-h-screen bg-gradient-to-b from-emerald-50 to-white dark:from-slate-950 dark:to-slate-900 flex items-center justify-center p-4">
      <Card className="max-w-md w-full border-emerald-200 dark:border-emerald-800">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 p-3 rounded-full bg-emerald-100 dark:bg-emerald-900/30 w-fit">
            <CheckCircle2 className="h-12 w-12 text-emerald-600" />
          </div>
          <CardTitle className="text-2xl">{t('success.title')} 🎉</CardTitle>
          <CardDescription className="text-base">
            {t('success.description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="bg-emerald-50 dark:bg-emerald-900/20 rounded-lg p-4 text-center">
            <ul className="text-sm text-emerald-600 dark:text-emerald-400 space-y-1">
              <li>✅ {t('features.solo.research')}</li>
              <li>✅ {t('features.solo.prep')}</li>
              <li>✅ {t('features.solo.transcription')}</li>
              <li>✅ {t('features.solo.kb')}</li>
            </ul>
          </div>

          <div className="text-center text-sm text-slate-500 dark:text-slate-400">
            {t('success.redirecting')} ({countdown}s)
          </div>

          <div className="flex flex-col gap-2">
            <Button 
              onClick={() => router.push('/dashboard')}
              className="w-full bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-700 hover:to-green-700 gap-2"
            >
              <Sparkles className="h-4 w-4" />
              {t('success.goToDashboard')}
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Button 
              variant="ghost" 
              onClick={() => router.push('/dashboard/settings')}
              className="w-full"
            >
              {tNav('settings')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
