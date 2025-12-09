'use client'

import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { XCircle, ArrowLeft, MessageCircle } from 'lucide-react'
import { useTranslations } from 'next-intl'
import Link from 'next/link'

export default function BillingCancelPage() {
  const router = useRouter()
  const t = useTranslations('billing')
  const tNav = useTranslations('navigation')

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900 flex items-center justify-center p-4">
      <Card className="max-w-md w-full">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 p-3 rounded-full bg-slate-100 dark:bg-slate-800 w-fit">
            <XCircle className="h-12 w-12 text-slate-400" />
          </div>
          <CardTitle className="text-2xl">{t('cancel.title')}</CardTitle>
          <CardDescription className="text-base">
            {t('cancel.description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex flex-col gap-2">
            <Button 
              onClick={() => router.push('/pricing')}
              className="w-full gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              {t('cancel.backToPricing')}
            </Button>
            <Button 
              variant="outline" 
              onClick={() => router.push('/dashboard')}
              className="w-full"
            >
              {tNav('dashboard')}
            </Button>
          </div>

          <div className="text-center pt-4 border-t">
            <Link 
              href="mailto:support@dealmotion.ai" 
              className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
            >
              <MessageCircle className="h-4 w-4" />
              {t('pricing.contactUs')}
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
