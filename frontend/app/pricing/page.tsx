'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { 
  Check, 
  X, 
  Sparkles, 
  Loader2,
  ArrowLeft,
  Zap,
  Crown,
  Building2,
  Heart,
  ExternalLink,
  Infinity
} from 'lucide-react'
import { useBilling } from '@/lib/billing-context'
import { useToast } from '@/components/ui/use-toast'
import { useTranslations } from 'next-intl'
import Link from 'next/link'
import { Logo } from '@/components/dealmotion-logo'
import { api } from '@/lib/api'

export default function PricingPage() {
  const router = useRouter()
  const { toast } = useToast()
  const { subscription, createCheckoutSession } = useBilling()
  const t = useTranslations('billing')
  const tErrors = useTranslations('errors')
  const [loading, setLoading] = useState<string | null>(null)
  const [flowPackLoading, setFlowPackLoading] = useState(false)
  const [isLoggedIn, setIsLoggedIn] = useState<boolean | null>(null)
  const supabase = createClientComponentClient()

  // Check if user is logged in
  useEffect(() => {
    const checkAuth = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      setIsLoggedIn(!!user)
    }
    checkAuth()
  }, [supabase])

  // v3 Features - all plans include KB and transcription
  const features = {
    free: [
      { text: t('features.v3.flows', { count: '2' }), included: true },
      { text: t('features.v3.kb'), included: true },
      { text: t('features.v3.transcription'), included: true },
      { text: t('features.v3.contacts'), included: true },
      { text: t('features.v3.pdf'), included: true },
      { text: t('features.v3.user', { count: '1' }), included: true },
      { text: t('features.v3.flowPacks'), included: true },
      { text: t('features.v3.crm'), included: false },
    ],
    proSolo: [
      { text: t('features.v3.flows', { count: '5' }), included: true },
      { text: t('features.v3.kb'), included: true },
      { text: t('features.v3.transcription'), included: true },
      { text: t('features.v3.contacts'), included: true },
      { text: t('features.v3.pdf'), included: true },
      { text: t('features.v3.user', { count: '1' }), included: true },
      { text: t('features.v3.flowPacks'), included: true },
      { text: t('features.v3.support'), included: true },
      { text: t('features.v3.crm'), included: false },
    ],
    unlimitedSolo: [
      { text: t('features.v3.flowsUnlimited'), included: true },
      { text: t('features.v3.kb'), included: true },
      { text: t('features.v3.transcription'), included: true },
      { text: t('features.v3.contacts'), included: true },
      { text: t('features.v3.pdf'), included: true },
      { text: t('features.v3.user', { count: '1' }), included: true },
      { text: t('features.v3.prioritySupport'), included: true },
      { text: t('features.v3.crm'), included: false },
    ],
    enterprise: [
      { text: t('features.v3.flowsUnlimited'), included: true },
      { text: t('features.v3.usersUnlimited'), included: true },
      { text: t('features.v3.crmDynamics'), included: true },
      { text: t('features.v3.crmSalesforce'), included: true },
      { text: t('features.v3.crmHubspot'), included: true },
      { text: t('features.v3.crmPipedrive'), included: true },
      { text: t('features.v3.crmZoho'), included: true },
      { text: t('features.v3.sso'), included: true },
      { text: t('features.v3.dedicatedSupport'), included: true },
    ],
  }

  const handleSelectPlan = async (planId: string) => {
    // If not logged in, redirect to signup
    if (!isLoggedIn) {
      router.push(`/signup?plan=${planId}`)
      return
    }

    if (planId === 'free') {
      toast({
        title: t('plans.free.name'),
        description: t('pricing.alreadyFree'),
      })
      return
    }

    if (planId === 'enterprise') {
      window.location.href = 'mailto:sales@dealmotion.ai?subject=Enterprise%20Plan%20Request'
      return
    }

    setLoading(planId)
    try {
      const checkoutUrl = await createCheckoutSession(planId)
      if (checkoutUrl) {
        window.location.href = checkoutUrl
      }
    } catch (error) {
      console.error('Checkout failed:', error)
      toast({
        title: tErrors('generic'),
        description: t('checkoutError'),
        variant: 'destructive',
      })
    } finally {
      setLoading(null)
    }
  }

  const handleDonation = () => {
    // Donation link is public - no auth required
    const donationUrl = process.env.NEXT_PUBLIC_STRIPE_DONATION_LINK
    if (donationUrl) {
      window.open(donationUrl, '_blank')
    } else {
      toast({
        title: tErrors('generic'),
        description: t('donationNotConfigured'),
        variant: 'destructive',
      })
    }
  }

  const handleFlowPackPurchase = async () => {
    // Must be logged in to buy flow packs
    if (!isLoggedIn) {
      router.push('/signup')
      return
    }

    setFlowPackLoading(true)
    try {
      const { data, error } = await api.post<{ checkout_url: string }>('/api/v1/billing/flow-packs/checkout', {
        pack_id: 'pack_5',
        success_url: `${window.location.origin}/billing/success`,
        cancel_url: `${window.location.origin}/pricing`,
      })

      if (error || !data?.checkout_url) {
        throw new Error('Failed to create checkout')
      }

      window.location.href = data.checkout_url
    } catch (error) {
      console.error('Flow pack checkout failed:', error)
      toast({
        title: tErrors('generic'),
        description: t('flowPacks.checkoutError'),
        variant: 'destructive',
      })
    } finally {
      setFlowPackLoading(false)
    }
  }

  const isCurrentPlan = (planId: string) => {
    // If not logged in, no plan is "current"
    if (!isLoggedIn) return false
    if (!subscription) return planId === 'free'
    return subscription.plan_id === planId
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900">
      {/* Header */}
      <div className="border-b bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <Link href="/dashboard" className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors">
              <ArrowLeft className="h-4 w-4" />
              {t('pricing.backToDashboard')}
            </Link>
            <Link href="/">
              <Logo />
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Title */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-slate-900 dark:text-white mb-4">
            {t('pricing.titleV2')}
          </h1>
          <p className="text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
            {t('pricing.subtitleV2')}
          </p>
          {/* Flow explanation */}
          <div className="mt-6 inline-flex items-center gap-2 px-4 py-2 bg-blue-50 dark:bg-blue-900/20 rounded-full text-sm text-blue-700 dark:text-blue-300">
            <Sparkles className="h-4 w-4" />
            {t('pricing.flowExplanation')}
          </div>
        </div>

        {/* Pricing Cards - 4 columns */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-6xl mx-auto">
          {/* Free Plan */}
          <Card className="relative border-2 hover:border-slate-300 dark:hover:border-slate-600 transition-colors">
            <CardHeader className="pb-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800">
                  <Zap className="h-5 w-5 text-slate-600 dark:text-slate-400" />
                </div>
                <CardTitle className="text-lg">{t('plans.free.name')}</CardTitle>
              </div>
              <CardDescription className="text-sm">{t('plans.v2.free.description')}</CardDescription>
              <div className="mt-4">
                <span className="text-3xl font-bold text-slate-900 dark:text-white">€0</span>
                <span className="text-slate-500 text-sm">{t('perMonth')}</span>
              </div>
            </CardHeader>
            <CardContent className="pb-4">
              <ul className="space-y-2">
                {features.free.map((feature, idx) => (
                  <li key={idx} className="flex items-center gap-2 text-sm">
                    {feature.included ? (
                      <Check className="h-4 w-4 text-emerald-500 flex-shrink-0" />
                    ) : (
                      <X className="h-4 w-4 text-slate-300 dark:text-slate-600 flex-shrink-0" />
                    )}
                    <span className={feature.included ? 'text-slate-700 dark:text-slate-300' : 'text-slate-400 dark:text-slate-600'}>
                      {feature.text}
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter className="flex flex-col gap-2">
              <Button 
                variant="outline" 
                className="w-full"
                disabled={isCurrentPlan('free')}
                onClick={() => !isLoggedIn && router.push('/signup')}
              >
                {!isLoggedIn 
                  ? t('pricing.getStarted')
                  : isCurrentPlan('free') 
                    ? t('pricing.currentPlan') 
                    : t('pricing.startFree')
                }
              </Button>
              {/* Donation button visible for everyone */}
              <Button 
                variant="ghost" 
                size="sm"
                className="w-full text-pink-600 hover:text-pink-700 hover:bg-pink-50 dark:hover:bg-pink-900/20"
                onClick={handleDonation}
              >
                <Heart className="h-4 w-4 mr-2" />
                {t('pricing.donate')}
              </Button>
            </CardFooter>
          </Card>

          {/* Pro Solo Plan */}
          <Card className="relative border-2 hover:border-blue-300 dark:hover:border-blue-600 transition-colors">
            <CardHeader className="pb-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30">
                  <Sparkles className="h-5 w-5 text-blue-600" />
                </div>
                <CardTitle className="text-lg">{t('plans.v3.proSolo.name')}</CardTitle>
              </div>
              <CardDescription className="text-sm">{t('plans.v3.proSolo.description')}</CardDescription>
              <div className="mt-4">
                <span className="text-3xl font-bold text-slate-900 dark:text-white">€9,95</span>
                <span className="text-slate-500 text-sm">{t('perMonth')}</span>
              </div>
            </CardHeader>
            <CardContent className="pb-4">
              <ul className="space-y-2">
                {features.proSolo.map((feature, idx) => (
                  <li key={idx} className="flex items-center gap-2 text-sm">
                    {feature.included ? (
                      <Check className="h-4 w-4 text-blue-500 flex-shrink-0" />
                    ) : (
                      <X className="h-4 w-4 text-slate-300 dark:text-slate-600 flex-shrink-0" />
                    )}
                    <span className={feature.included ? 'text-slate-700 dark:text-slate-300' : 'text-slate-400 dark:text-slate-600'}>
                      {feature.text}
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter>
              <Button 
                className="w-full"
                variant="outline"
                onClick={() => handleSelectPlan('light_solo')}
                disabled={loading === 'light_solo' || isCurrentPlan('light_solo')}
              >
                {loading === 'light_solo' ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : !isLoggedIn ? (
                  t('pricing.getStarted')
                ) : isCurrentPlan('light_solo') ? (
                  t('pricing.currentPlan')
                ) : (
                  t('pricing.upgrade')
                )}
              </Button>
            </CardFooter>
          </Card>

          {/* Unlimited Solo Plan - Featured */}
          <Card className="relative border-2 border-indigo-500 shadow-lg shadow-indigo-500/10">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2">
              <Badge className="bg-gradient-to-r from-indigo-500 to-purple-500 px-3 text-xs">
                {t('pricing.earlyAdopter')}
              </Badge>
            </div>
            <CardHeader className="pb-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-900/30">
                  <Crown className="h-5 w-5 text-indigo-600" />
                </div>
                <CardTitle className="text-lg">{t('plans.v3.unlimitedSolo.name')}</CardTitle>
              </div>
              <CardDescription className="text-sm">{t('plans.v3.unlimitedSolo.description')}</CardDescription>
              <div className="mt-4">
                <span className="text-lg text-slate-400 line-through">€99,95</span>
                <span className="text-3xl font-bold text-slate-900 dark:text-white ml-2">€49,95</span>
                <span className="text-slate-500 text-sm">{t('perMonth')}</span>
              </div>
            </CardHeader>
            <CardContent className="pb-4">
              <ul className="space-y-2">
                {features.unlimitedSolo.map((feature, idx) => (
                  <li key={idx} className="flex items-center gap-2 text-sm">
                    {feature.included ? (
                      <Check className="h-4 w-4 text-indigo-500 flex-shrink-0" />
                    ) : (
                      <X className="h-4 w-4 text-slate-300 dark:text-slate-600 flex-shrink-0" />
                    )}
                    <span className={feature.included ? 'text-slate-700 dark:text-slate-300' : 'text-slate-400 dark:text-slate-600'}>
                      {feature.text}
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter>
              <Button 
                className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700"
                onClick={() => handleSelectPlan('unlimited_solo')}
                disabled={loading === 'unlimited_solo' || isCurrentPlan('unlimited_solo')}
              >
                {loading === 'unlimited_solo' ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : !isLoggedIn ? (
                  <>
                    <Infinity className="h-4 w-4 mr-2" />
                    {t('pricing.getStarted')}
                  </>
                ) : isCurrentPlan('unlimited_solo') ? (
                  t('pricing.currentPlan')
                ) : (
                  <>
                    <Infinity className="h-4 w-4 mr-2" />
                    {t('pricing.goUnlimited')}
                  </>
                )}
              </Button>
            </CardFooter>
          </Card>

          {/* Enterprise Plan */}
          <Card className="relative border-2 hover:border-purple-300 dark:hover:border-purple-600 transition-colors">
            <CardHeader className="pb-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-900/30">
                  <Building2 className="h-5 w-5 text-purple-600" />
                </div>
                <CardTitle className="text-lg">{t('plans.v3.enterprise.name')}</CardTitle>
              </div>
              <CardDescription className="text-sm">{t('plans.v3.enterprise.description')}</CardDescription>
              <div className="mt-4">
                <span className="text-xl font-bold text-slate-900 dark:text-white">{t('pricing.contactSales')}</span>
              </div>
            </CardHeader>
            <CardContent className="pb-4">
              <ul className="space-y-2">
                {features.enterprise.map((feature, idx) => (
                  <li key={idx} className="flex items-center gap-2 text-sm">
                    <Check className="h-4 w-4 text-purple-500 flex-shrink-0" />
                    <span className="text-slate-700 dark:text-slate-300">{feature.text}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter>
              <Button 
                variant="outline" 
                className="w-full border-purple-300 hover:bg-purple-50 dark:hover:bg-purple-900/20"
                onClick={() => handleSelectPlan('enterprise')}
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                {t('pricing.contactUs')}
              </Button>
            </CardFooter>
          </Card>
        </div>

        {/* What is a Flow? */}
        <div className="mt-16 max-w-2xl mx-auto text-center">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-4">
            {t('pricing.whatIsFlow')}
          </h2>
          <div className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-6">
            <div className="flex items-center justify-center gap-4 text-sm">
              <div className="flex items-center gap-2 px-3 py-2 bg-white dark:bg-slate-800 rounded-lg shadow-sm">
                <span className="font-semibold text-blue-600">1</span>
                <span>{t('pricing.flowStep1')}</span>
              </div>
              <span className="text-slate-400">+</span>
              <div className="flex items-center gap-2 px-3 py-2 bg-white dark:bg-slate-800 rounded-lg shadow-sm">
                <span className="font-semibold text-green-600">1</span>
                <span>{t('pricing.flowStep2')}</span>
              </div>
              <span className="text-slate-400">+</span>
              <div className="flex items-center gap-2 px-3 py-2 bg-white dark:bg-slate-800 rounded-lg shadow-sm">
                <span className="font-semibold text-purple-600">1</span>
                <span>{t('pricing.flowStep3')}</span>
              </div>
              <span className="text-slate-400">=</span>
              <div className="flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-blue-500 to-purple-500 text-white rounded-lg shadow-sm font-semibold">
                1 Flow
              </div>
            </div>
            <p className="mt-4 text-sm text-slate-600 dark:text-slate-400">
              {t('pricing.flowDescription')}
            </p>
          </div>
        </div>

        {/* Flow Pack Section */}
        <div className="mt-16 max-w-md mx-auto">
          <Card className="border-2 border-dashed border-slate-300 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50">
            <CardHeader className="text-center pb-2">
              <div className="flex items-center justify-center gap-2 mb-2">
                <Zap className="h-5 w-5 text-amber-500" />
                <CardTitle className="text-lg">{t('flowPacks.title')}</CardTitle>
              </div>
              <CardDescription>{t('flowPacks.description')}</CardDescription>
            </CardHeader>
            <CardContent className="text-center">
              <div className="inline-flex items-baseline gap-1">
                <span className="text-2xl font-bold text-slate-900 dark:text-white">€9,95</span>
                <span className="text-slate-500 text-sm">/ 5 flows</span>
              </div>
              <p className="text-xs text-slate-500 mt-1">{t('flowPacks.pack5.pricePerFlow')}</p>
            </CardContent>
            <CardFooter className="justify-center">
              <Button 
                variant="outline"
                className="border-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900/20"
                onClick={() => handleFlowPackPurchase()}
                disabled={flowPackLoading}
              >
                {flowPackLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Zap className="h-4 w-4 mr-2 text-amber-500" />
                )}
                {t('flowPacks.buy')}
              </Button>
            </CardFooter>
          </Card>
        </div>

        {/* Trust Section */}
        <div className="mt-16 text-center">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t('pricing.trustBadges')}
          </p>
        </div>
      </div>
    </div>
  )
}
