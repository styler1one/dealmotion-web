'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
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
  Infinity,
  Mic,
  Bot
} from 'lucide-react'
import { useBilling } from '@/lib/billing-context'
import { useToast } from '@/components/ui/use-toast'
import { useTranslations } from 'next-intl'
import Link from 'next/link'
import { Logo } from '@/components/dealmotion-logo'

export default function PricingPage() {
  const router = useRouter()
  const { toast } = useToast()
  const { subscription, createCheckoutSession } = useBilling()
  const t = useTranslations('billing')
  const tErrors = useTranslations('errors')
  const [loading, setLoading] = useState<string | null>(null)
  const [isYearly, setIsYearly] = useState(false)
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

  // Pricing data
  const pricing = {
    pro: {
      monthly: { price: 4995, original: 7995 },      // €49.95 launch, €79.95 regular
      yearly: { price: 50900, original: 81500 },     // €509 launch, €815 regular
    },
    proPlus: {
      monthly: { price: 6995, original: 9995 },      // €69.95 launch, €99.95 regular
      yearly: { price: 71300, original: 101900 },    // €713 launch, €1019 regular
    }
  }

  // Format price for display
  const formatPrice = (cents: number) => {
    const euros = cents / 100
    return new Intl.NumberFormat('nl-NL', { 
      style: 'currency', 
      currency: 'EUR',
      minimumFractionDigits: euros % 1 === 0 ? 0 : 2,
      maximumFractionDigits: 2
    }).format(euros)
  }

  // Calculate monthly equivalent for yearly plans
  const getMonthlyEquivalent = (yearlyCents: number) => {
    return formatPrice(Math.round(yearlyCents / 12))
  }

  // Calculate yearly savings
  const getYearlySavings = (plan: 'pro' | 'proPlus') => {
    const monthlyTotal = pricing[plan].monthly.price * 12
    const yearlyPrice = pricing[plan].yearly.price
    return monthlyTotal - yearlyPrice
  }

  // Features for each plan - v4 structure with value-driven descriptions
  const features = {
    free: [
      { text: t('features.v4.value.twoFlows'), included: true },
      { text: t('features.v4.value.prospectIntel'), included: true },
      { text: t('features.v4.value.meetingPrep'), included: true },
      { text: t('features.v4.value.followupAnalysis'), included: true },
      { text: t('pricing.noCardRequired'), included: true },
    ],
    pro: [
      { text: t('features.v4.value.unlimited'), included: true },
      { text: t('features.v4.value.prospectIntel'), included: true },
      { text: t('features.v4.value.contactAnalysis'), included: true },
      { text: t('features.v4.value.meetingPrep'), included: true },
      { text: t('features.v4.value.followupAnalysis'), included: true },
      { text: t('features.v4.value.meetingReport'), included: true },
      { text: t('features.v4.value.dealAnalysis'), included: true },
      { text: t('features.v4.value.emailsDealNotes'), included: true },
      { text: t('features.v4.value.salesCoach'), included: true },
      { text: t('features.v4.aiNotetaker'), included: false, highlight: true },
    ],
    proPlus: [
      { text: t('features.v4.value.unlimited'), included: true },
      { text: t('features.v4.value.prospectIntel'), included: true },
      { text: t('features.v4.value.contactAnalysis'), included: true },
      { text: t('features.v4.value.meetingPrep'), included: true },
      { text: t('features.v4.value.followupAnalysis'), included: true },
      { text: t('features.v4.value.meetingReport'), included: true },
      { text: t('features.v4.value.dealAnalysis'), included: true },
      { text: t('features.v4.value.emailsDealNotes'), included: true },
      { text: t('features.v4.value.salesCoach'), included: true },
      { text: t('features.v4.aiNotetaker'), included: true, highlight: true },
    ],
    enterprise: [
      { text: t('features.v4.everythingProPlus'), included: true },
      { text: t('features.v4.unlimitedUsers'), included: true },
      { text: t('features.v4.value.crmSync'), included: true },
      { text: t('features.v4.value.teamSharing'), included: true },
      { text: t('features.v4.sso'), included: true },
      { text: t('features.v4.dedicatedSupport'), included: true },
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

  const isCurrentPlan = (planId: string) => {
    if (!isLoggedIn) return false
    if (!subscription) return planId === 'free'
    // Check both monthly and yearly variants
    if (planId === 'pro') {
      return subscription.plan_id === 'pro_monthly' || subscription.plan_id === 'pro_yearly'
    }
    if (planId === 'pro_plus') {
      return subscription.plan_id === 'pro_plus_monthly' || subscription.plan_id === 'pro_plus_yearly'
    }
    return subscription.plan_id === planId
  }

  const getActualPlanId = (basePlanId: string) => {
    if (basePlanId === 'pro') {
      return isYearly ? 'pro_yearly' : 'pro_monthly'
    }
    if (basePlanId === 'pro_plus') {
      return isYearly ? 'pro_plus_yearly' : 'pro_plus_monthly'
    }
    return basePlanId
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900">
      {/* Header */}
      <div className="border-b bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <Link 
              href={isLoggedIn ? "/dashboard" : "/"} 
              className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              {isLoggedIn ? t('pricing.backToDashboard') : t('pricing.backToHome')}
            </Link>
            <Link href="/">
              <Logo />
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Title */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-slate-900 dark:text-white mb-4">
            {t('pricing.titleV4')}
          </h1>
          <p className="text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
            {t('pricing.subtitleV4')}
          </p>
        </div>

        {/* Compact: Toggle + Launch Badge + Guarantee - all in one line */}
        <div className="flex flex-col items-center gap-4 mb-8">
          {/* Billing Toggle */}
          <div className="flex items-center gap-4">
            <Label 
              htmlFor="billing-toggle" 
              className={`text-sm font-medium cursor-pointer ${!isYearly ? 'text-slate-900 dark:text-white' : 'text-slate-500'}`}
            >
              {t('pricing.monthly')}
            </Label>
            <Switch
              id="billing-toggle"
              checked={isYearly}
              onCheckedChange={setIsYearly}
              className="data-[state=checked]:bg-indigo-600"
            />
            <Label 
              htmlFor="billing-toggle" 
              className={`text-sm font-medium cursor-pointer flex items-center gap-2 ${isYearly ? 'text-slate-900 dark:text-white' : 'text-slate-500'}`}
            >
              {t('pricing.yearly')}
              <Badge variant="secondary" className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                {t('pricing.save', { percent: '15' })}
              </Badge>
            </Label>
          </div>
          
          {/* Compact trust indicators */}
          <div className="flex flex-wrap items-center justify-center gap-4 text-sm text-slate-600 dark:text-slate-400">
            <span className="flex items-center gap-1">
              <Sparkles className="h-4 w-4 text-indigo-500" />
              <span className="text-indigo-600 dark:text-indigo-400 font-medium">{t('pricing.launchOffer')}</span>
            </span>
            <span className="text-slate-300 dark:text-slate-600">•</span>
            <span className="flex items-center gap-1">
              <span className="text-green-600">✓</span>
              {t('pricing.moneyBackInline')}
            </span>
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
                <CardTitle className="text-lg">{t('plans.v4.free.name')}</CardTitle>
              </div>
              <CardDescription className="text-sm">{t('plans.v4.free.description')}</CardDescription>
              <div className="mt-4">
                <span className="text-3xl font-bold text-slate-900 dark:text-white">€0</span>
                <span className="text-slate-500 text-sm">/{t('pricing.forever')}</span>
              </div>
            </CardHeader>
            <CardContent className="pb-4">
              <ul className="space-y-2">
                {features.free.map((feature, idx) => (
                  <li key={idx} className="flex items-center gap-2 text-sm">
                    <Check className="h-4 w-4 text-emerald-500 flex-shrink-0" />
                    <span className="text-slate-700 dark:text-slate-300">
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

          {/* Pro Plan */}
          <Card className="relative border-2 hover:border-blue-300 dark:hover:border-blue-600 transition-colors">
            <CardHeader className="pb-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30">
                  <Sparkles className="h-5 w-5 text-blue-600" />
                </div>
                <CardTitle className="text-lg">{t('plans.v4.pro.name')}</CardTitle>
              </div>
              <CardDescription className="text-sm">{t('plans.v4.pro.description')}</CardDescription>
              <div className="mt-4">
                <div className="flex items-baseline gap-2">
                  <span className="text-lg text-slate-400 line-through">
                    {isYearly 
                      ? getMonthlyEquivalent(pricing.pro.yearly.original)
                      : formatPrice(pricing.pro.monthly.original)
                    }
                  </span>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-bold text-slate-900 dark:text-white">
                    {isYearly 
                      ? getMonthlyEquivalent(pricing.pro.yearly.price)
                      : formatPrice(pricing.pro.monthly.price)
                    }
                  </span>
                  <span className="text-slate-500 text-sm">/{t('pricing.perMonth')}</span>
                </div>
                {isYearly && (
                  <div className="mt-1">
                    <p className="text-xs text-slate-500">
                      {t('pricing.billedYearly', { amount: formatPrice(pricing.pro.yearly.price) })}
                    </p>
                    <p className="text-xs text-green-600 font-medium">
                      {t('pricing.saveAmount', { amount: formatPrice(getYearlySavings('pro')) })}
                    </p>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent className="pb-4">
              <ul className="space-y-2">
                {features.pro.map((feature, idx) => (
                  <li key={idx} className="flex items-center gap-2 text-sm">
                    {feature.included ? (
                      <Check className="h-4 w-4 text-blue-500 flex-shrink-0" />
                    ) : (
                      <X className={`h-4 w-4 flex-shrink-0 ${feature.highlight ? 'text-slate-400' : 'text-slate-300 dark:text-slate-600'}`} />
                    )}
                    <span className={`${feature.included ? 'text-slate-700 dark:text-slate-300' : 'text-slate-400 dark:text-slate-600'} ${feature.highlight ? 'font-medium' : ''}`}>
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
                onClick={() => handleSelectPlan(getActualPlanId('pro'))}
                disabled={loading === getActualPlanId('pro') || isCurrentPlan('pro')}
              >
                {loading === getActualPlanId('pro') ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : isCurrentPlan('pro') ? (
                  t('pricing.currentPlan')
                ) : !isLoggedIn ? (
                  t('pricing.choosePro')
                ) : (
                  t('pricing.upgrade')
                )}
              </Button>
            </CardFooter>
          </Card>

          {/* Pro+ Plan - Featured */}
          <Card className="relative border-2 border-indigo-500 shadow-lg shadow-indigo-500/10">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2">
              <Badge className="bg-gradient-to-r from-indigo-500 to-purple-500 px-3 text-xs">
                {t('pricing.popular')}
              </Badge>
            </div>
            <CardHeader className="pb-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-900/30">
                  <Crown className="h-5 w-5 text-indigo-600" />
                </div>
                <CardTitle className="text-lg">{t('plans.v4.proPlus.name')}</CardTitle>
              </div>
              <CardDescription className="text-sm">{t('plans.v4.proPlus.description')}</CardDescription>
              <div className="mt-4">
                <div className="flex items-baseline gap-2">
                  <span className="text-lg text-slate-400 line-through">
                    {isYearly 
                      ? getMonthlyEquivalent(pricing.proPlus.yearly.original)
                      : formatPrice(pricing.proPlus.monthly.original)
                    }
                  </span>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-bold text-slate-900 dark:text-white">
                    {isYearly 
                      ? getMonthlyEquivalent(pricing.proPlus.yearly.price)
                      : formatPrice(pricing.proPlus.monthly.price)
                    }
                  </span>
                  <span className="text-slate-500 text-sm">/{t('pricing.perMonth')}</span>
                </div>
                {isYearly && (
                  <div className="mt-1">
                    <p className="text-xs text-slate-500">
                      {t('pricing.billedYearly', { amount: formatPrice(pricing.proPlus.yearly.price) })}
                    </p>
                    <p className="text-xs text-green-600 font-medium">
                      {t('pricing.saveAmount', { amount: formatPrice(getYearlySavings('proPlus')) })}
                    </p>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent className="pb-4">
              {/* AI Notetaker highlight */}
              <div className="mb-4 p-3 bg-indigo-50 dark:bg-indigo-900/20 rounded-lg border border-indigo-200 dark:border-indigo-800">
                <div className="flex items-center gap-2 text-indigo-700 dark:text-indigo-300">
                  <Bot className="h-5 w-5" />
                  <span className="font-semibold text-sm">{t('features.v4.aiNotetakerIncluded')}</span>
                </div>
                <p className="text-xs text-indigo-600 dark:text-indigo-400 mt-1">
                  {t('features.v4.aiNotetakerDescription')}
                </p>
              </div>
              <ul className="space-y-2">
                {features.proPlus.map((feature, idx) => (
                  <li key={idx} className="flex items-center gap-2 text-sm">
                    {feature.included ? (
                      <Check className={`h-4 w-4 flex-shrink-0 ${feature.highlight ? 'text-indigo-500' : 'text-indigo-500'}`} />
                    ) : (
                      <X className="h-4 w-4 text-slate-300 dark:text-slate-600 flex-shrink-0" />
                    )}
                    <span className={`${feature.included ? 'text-slate-700 dark:text-slate-300' : 'text-slate-400 dark:text-slate-600'} ${feature.highlight ? 'font-semibold text-indigo-700 dark:text-indigo-300' : ''}`}>
                      {feature.text}
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter>
              <Button 
                className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700"
                onClick={() => handleSelectPlan(getActualPlanId('pro_plus'))}
                disabled={loading === getActualPlanId('pro_plus') || isCurrentPlan('pro_plus')}
              >
                {loading === getActualPlanId('pro_plus') ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : isCurrentPlan('pro_plus') ? (
                  t('pricing.currentPlan')
                ) : (
                  <>
                    <Infinity className="h-4 w-4 mr-2" />
                    {!isLoggedIn ? t('pricing.chooseProPlus') : t('pricing.goProPlus')}
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
                <CardTitle className="text-lg">{t('plans.v4.enterprise.name')}</CardTitle>
              </div>
              <CardDescription className="text-sm">{t('plans.v4.enterprise.description')}</CardDescription>
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

        {/* Value Proposition - What You Actually Get */}
        <div className="mt-16 max-w-4xl mx-auto">
          <h3 className="text-center text-lg font-semibold text-slate-900 dark:text-white mb-6">
            {t('pricing.value.personalized')}
          </h3>
          <div className="grid md:grid-cols-4 gap-4 text-center">
            <div className="p-4 rounded-xl bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800">
              <div className="text-2xl mb-2">🔍</div>
              <h4 className="font-semibold text-slate-900 dark:text-white text-sm mb-1">{t('pricing.value.research.title')}</h4>
              <p className="text-xs text-slate-600 dark:text-slate-400">{t('pricing.value.research.description')}</p>
            </div>
            <div className="p-4 rounded-xl bg-green-50 dark:bg-green-900/20 border border-green-100 dark:border-green-800">
              <div className="text-2xl mb-2">🎯</div>
              <h4 className="font-semibold text-slate-900 dark:text-white text-sm mb-1">{t('pricing.value.prep.title')}</h4>
              <p className="text-xs text-slate-600 dark:text-slate-400">{t('pricing.value.prep.description')}</p>
            </div>
            <div className="p-4 rounded-xl bg-purple-50 dark:bg-purple-900/20 border border-purple-100 dark:border-purple-800">
              <div className="text-2xl mb-2">🎙️</div>
              <h4 className="font-semibold text-slate-900 dark:text-white text-sm mb-1">{t('pricing.value.meeting.title')}</h4>
              <p className="text-xs text-slate-600 dark:text-slate-400">{t('pricing.value.meeting.description')}</p>
            </div>
            <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-800">
              <div className="text-2xl mb-2">✨</div>
              <h4 className="font-semibold text-slate-900 dark:text-white text-sm mb-1">{t('pricing.value.followup.title')}</h4>
              <p className="text-xs text-slate-600 dark:text-slate-400">{t('pricing.value.followup.description')}</p>
            </div>
          </div>
        </div>

        {/* Testimonial */}
        <div className="mt-12 max-w-2xl mx-auto">
          <div className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700 text-center">
            <p className="text-slate-700 dark:text-slate-300 italic text-lg mb-3">
              "{t('pricing.testimonial.quote')}"
            </p>
            <p className="text-sm text-slate-500">
              — {t('pricing.testimonial.author')}, {t('pricing.testimonial.company')}
            </p>
          </div>
        </div>

        {/* Trust Section */}
        <div className="mt-12 text-center">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t('pricing.trustBadges')}
          </p>
        </div>
      </div>
    </div>
  )
}
