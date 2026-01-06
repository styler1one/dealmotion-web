'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { useTranslations, useLocale } from 'next-intl'
import { LanguageSelector } from '@/components/language-selector'
import { type Locale } from '@/i18n/config'
import { Logo, LogoIcon } from '@/components/dealmotion-logo'
import {
  HowItWorks,
  IntegrationsRow,
  AIContextSection,
  MeetingAnalysisShowcase,
  AINotetakerSection,
  MobileAppTeaser,
  PainPointsSection,
  DayInTheLife,
  HeroShowcase,
} from '@/components/landing'

export default function Home() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const [loading, setLoading] = useState(true)
  const t = useTranslations('homepage')
  const locale = useLocale() as Locale

  useEffect(() => {
    const checkUser = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      if (user) {
        router.push('/dashboard')
      }
      setLoading(false)
    }
    checkUser()
  }, [supabase, router])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center dark:bg-slate-900">
        <Icons.spinner className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-950">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b dark:border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Logo />
            <div className="flex items-center gap-2 sm:gap-4">
              <LanguageSelector currentLocale={locale} />
              <Button variant="ghost" onClick={() => router.push('/login')}>
                {t('nav.login')}
              </Button>
              <Button onClick={() => router.push('/signup')} className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700">
                {t('nav.getStarted')}
              </Button>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="text-center max-w-4xl mx-auto">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 text-sm font-medium mb-6">
              <Icons.sparkles className="h-4 w-4" />
              {t('hero.badge')}
            </div>
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight text-slate-900 dark:text-white mb-6">
              {t('hero.title')}{' '}
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-violet-600">
                {t('hero.titleHighlight')}
              </span>
            </h1>
            <p className="text-xl text-slate-600 dark:text-slate-300 mb-10 max-w-2xl mx-auto">
              {t('hero.description')}
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Button 
                size="lg" 
                onClick={() => router.push('/signup')}
                className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 text-lg px-8 h-14"
              >
                {t('hero.startFree')}
                <Icons.arrowRight className="ml-2 h-5 w-5" />
              </Button>
              <Button 
                size="lg" 
                variant="outline"
                onClick={() => router.push('/pricing')}
                className="text-lg px-8 h-14"
              >
                {t('hero.viewPricing')}
              </Button>
            </div>
          </div>

          {/* Hero Showcase - Interactive Carousel */}
          <div className="mt-16 relative">
            <div className="absolute inset-0 bg-gradient-to-t from-white dark:from-slate-900 via-transparent to-transparent z-10 pointer-events-none" />
            <HeroShowcase />
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-4 bg-white dark:bg-slate-900">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-4">
              {t('features.title')}
            </h2>
            <p className="text-lg text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">
              {t('features.description')}
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {/* Feature 1: Research */}
            <div className="group p-6 rounded-2xl border dark:border-slate-800 bg-white dark:bg-slate-800 hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
              <div className="w-12 h-12 rounded-xl bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Icons.search className="h-6 w-6 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2 text-slate-900 dark:text-white">{t('features.research.title')}</h3>
              <p className="text-slate-600 dark:text-slate-300 text-sm">
                {t('features.research.description')}
              </p>
            </div>

            {/* Feature 2: Outreach */}
            <div className="group p-6 rounded-2xl border dark:border-slate-800 bg-white dark:bg-slate-800 hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
              <div className="w-12 h-12 rounded-xl bg-rose-100 dark:bg-rose-900/30 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Icons.send className="h-6 w-6 text-rose-600 dark:text-rose-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2 text-slate-900 dark:text-white">{t('features.outreach.title')}</h3>
              <p className="text-slate-600 dark:text-slate-300 text-sm">
                {t('features.outreach.description')}
              </p>
            </div>

            {/* Feature 3: Preparation */}
            <div className="group p-6 rounded-2xl border dark:border-slate-800 bg-white dark:bg-slate-800 hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
              <div className="w-12 h-12 rounded-xl bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Icons.fileText className="h-6 w-6 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2 text-slate-900 dark:text-white">{t('features.preparation.title')}</h3>
              <p className="text-slate-600 dark:text-slate-300 text-sm">
                {t('features.preparation.description')}
              </p>
            </div>

            {/* Feature 3: AI Notetaker */}
            <div className="group p-6 rounded-2xl border-2 border-violet-200 dark:border-violet-800 bg-gradient-to-br from-violet-50 to-white dark:from-violet-900/20 dark:to-slate-800 hover:shadow-lg transition-all duration-300 hover:-translate-y-1 relative overflow-hidden">
              <div className="absolute top-2 right-2 px-2 py-0.5 rounded-full bg-violet-100 dark:bg-violet-900/50 text-violet-600 dark:text-violet-400 text-xs font-medium">
                NEW
              </div>
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Icons.sparkles className="h-6 w-6 text-white" />
              </div>
              <h3 className="text-lg font-semibold mb-2 text-slate-900 dark:text-white">{t('features.aiNotetaker.title')}</h3>
              <p className="text-slate-600 dark:text-slate-300 text-sm">
                {t('features.aiNotetaker.description')}
              </p>
            </div>

            {/* Feature 4: Follow-up */}
            <div className="group p-6 rounded-2xl border dark:border-slate-800 bg-white dark:bg-slate-800 hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
              <div className="w-12 h-12 rounded-xl bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Icons.mail className="h-6 w-6 text-orange-600 dark:text-orange-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2 text-slate-900 dark:text-white">{t('features.followup.title')}</h3>
              <p className="text-slate-600 dark:text-slate-300 text-sm">
                {t('features.followup.description')}
              </p>
            </div>

            {/* Feature 4: AI Sales Coach */}
            <div className="group p-6 rounded-2xl border dark:border-slate-800 bg-white dark:bg-slate-800 hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
              <div className="w-12 h-12 rounded-xl bg-pink-100 dark:bg-pink-900/30 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Icons.sparkles className="h-6 w-6 text-pink-600 dark:text-pink-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2 text-slate-900 dark:text-white">{t('features.aiCoach.title')}</h3>
              <p className="text-slate-600 dark:text-slate-300 text-sm">
                {t('features.aiCoach.description')}
              </p>
            </div>

            {/* Feature 5: Knowledge Base */}
            <div className="group p-6 rounded-2xl border dark:border-slate-800 bg-white dark:bg-slate-800 hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
              <div className="w-12 h-12 rounded-xl bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Icons.book className="h-6 w-6 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2 text-slate-900 dark:text-white">{t('features.knowledgeBase.title')}</h3>
              <p className="text-slate-600 dark:text-slate-300 text-sm">
                {t('features.knowledgeBase.description')}
              </p>
            </div>

            {/* Feature 6: Contact Analysis */}
            <div className="group p-6 rounded-2xl border dark:border-slate-800 bg-white dark:bg-slate-800 hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
              <div className="w-12 h-12 rounded-xl bg-cyan-100 dark:bg-cyan-900/30 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Icons.users className="h-6 w-6 text-cyan-600 dark:text-cyan-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2 text-slate-900 dark:text-white">{t('features.contactAnalysis.title')}</h3>
              <p className="text-slate-600 dark:text-slate-300 text-sm">
                {t('features.contactAnalysis.description')}
              </p>
            </div>

            {/* Feature 8: Meetings Calendar */}
            <div className="group p-6 rounded-2xl border dark:border-slate-800 bg-white dark:bg-slate-800 hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
              <div className="w-12 h-12 rounded-xl bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Icons.calendar className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2 text-slate-900 dark:text-white">{t('features.meetingsCalendar.title')}</h3>
              <p className="text-slate-600 dark:text-slate-300 text-sm">
                {t('features.meetingsCalendar.description')}
              </p>
            </div>

            {/* Feature 8: In-Person Meetings */}
            <div className="group p-6 rounded-2xl border dark:border-slate-800 bg-white dark:bg-slate-800 hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
              <div className="w-12 h-12 rounded-xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Icons.mic className="h-6 w-6 text-amber-600 dark:text-amber-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2 text-slate-900 dark:text-white">{t('features.inPersonMeetings.title')}</h3>
              <p className="text-slate-600 dark:text-slate-300 text-sm">
                {t('features.inPersonMeetings.description')}
              </p>
            </div>

            {/* Feature 9: Smart Integrations */}
            <div className="group p-6 rounded-2xl border dark:border-slate-800 bg-white dark:bg-slate-800 hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
              <div className="w-12 h-12 rounded-xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Icons.link className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2 text-slate-900 dark:text-white">{t('features.smartIntegrations.title')}</h3>
              <p className="text-slate-600 dark:text-slate-300 text-sm">
                {t('features.smartIntegrations.description')}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <HowItWorks />

      {/* AI That Knows You */}
      <AIContextSection />

      {/* Meeting Analysis Showcase */}
      <MeetingAnalysisShowcase />

      {/* AI Notetaker - Auto Recording */}
      <AINotetakerSection />

      {/* Integrations */}
      <IntegrationsRow />

      {/* Pain Points Before/After */}
      <PainPointsSection />

      {/* Mobile App Teaser */}
      <MobileAppTeaser />

      {/* Day in the Life */}
      <DayInTheLife />

      {/* Social Proof */}
      <section className="py-16 px-4 bg-slate-50 dark:bg-slate-800">
        <div className="max-w-7xl mx-auto text-center">
          <div className="inline-flex items-center gap-3 px-6 py-3 rounded-full bg-white dark:bg-slate-900 shadow-sm border dark:border-slate-700">
            <Icons.users className="h-5 w-5 text-blue-600" />
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
              {t('socialProof.usedBy')}
            </p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4 bg-gradient-to-r from-blue-600 to-violet-600">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">
            {t('cta.title')}
          </h2>
          <p className="text-xl text-blue-100 mb-10">
            {t('cta.description')}
          </p>
          <Button 
            size="lg" 
            variant="secondary"
            onClick={() => router.push('/signup')}
            className="text-lg px-8 h-14 bg-white text-blue-600 hover:bg-blue-50"
          >
            {t('cta.button')}
            <Icons.arrowRight className="ml-2 h-5 w-5" />
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-4 bg-slate-900 text-slate-400">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <Logo darkMode />
            <p className="text-sm">
              © {new Date().getFullYear()} DealMotion. {t('footer.rights')}
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
