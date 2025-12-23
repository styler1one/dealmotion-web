'use client'

import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Shield, ExternalLink } from 'lucide-react'
import Link from 'next/link'
import { Logo } from '@/components/dealmotion-logo'

export default function PrivacyPolicyPage() {
  const router = useRouter()
  const t = useTranslations('legal.privacy')
  const tCommon = useTranslations('common')
  
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <Logo className="h-8" />
          </Link>
          <Button variant="ghost" onClick={() => router.back()} className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            {tCommon('back')}
          </Button>
        </div>
      </header>
      
      {/* Content */}
      <main className="max-w-4xl mx-auto px-4 py-12">
        {/* Page Title */}
        <div className="mb-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 rounded-lg bg-teal-100 dark:bg-teal-900/30">
              <Shield className="h-6 w-6 text-teal-600 dark:text-teal-400" />
            </div>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-white">
              {t('title')}
            </h1>
          </div>
          <p className="text-slate-500 dark:text-slate-400">
            {t('lastUpdated')}: {t('lastUpdatedDate')}
          </p>
        </div>
        
        {/* Content Sections */}
        <div className="prose prose-slate dark:prose-invert max-w-none">
          {/* Introduction */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('intro.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300">{t('intro.text')}</p>
          </section>
          
          {/* Controller */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('controller.title')}</h2>
            <div className="bg-slate-100 dark:bg-slate-800 rounded-lg p-4">
              <p className="text-slate-600 dark:text-slate-300 mb-2"><strong>{t('controller.company')}</strong></p>
              <p className="text-slate-600 dark:text-slate-300 mb-1">{t('controller.address')}</p>
              <p className="text-slate-600 dark:text-slate-300 mb-1">{t('controller.country')}</p>
              <p className="text-slate-600 dark:text-slate-300">{t('controller.email')}: <a href="mailto:privacy@dealmotion.ai" className="text-blue-600 hover:underline">privacy@dealmotion.ai</a></p>
            </div>
          </section>
          
          {/* Data Collected */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('dataCollected.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('dataCollected.intro')}</p>
            
            <h3 className="text-lg font-medium text-slate-800 dark:text-slate-200 mb-2">{t('dataCollected.account.title')}</h3>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 mb-4 space-y-1">
              <li>{t('dataCollected.account.item1')}</li>
              <li>{t('dataCollected.account.item2')}</li>
              <li>{t('dataCollected.account.item3')}</li>
            </ul>
            
            <h3 className="text-lg font-medium text-slate-800 dark:text-slate-200 mb-2">{t('dataCollected.content.title')}</h3>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 mb-4 space-y-1">
              <li>{t('dataCollected.content.item1')}</li>
              <li>{t('dataCollected.content.item2')}</li>
              <li>{t('dataCollected.content.item3')}</li>
              <li>{t('dataCollected.content.item4')}</li>
            </ul>
            
            <h3 className="text-lg font-medium text-slate-800 dark:text-slate-200 mb-2">{t('dataCollected.technical.title')}</h3>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-1">
              <li>{t('dataCollected.technical.item1')}</li>
              <li>{t('dataCollected.technical.item2')}</li>
              <li>{t('dataCollected.technical.item3')}</li>
            </ul>
          </section>
          
          {/* Purposes */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('purposes.title')}</h2>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li>{t('purposes.item1')}</li>
              <li>{t('purposes.item2')}</li>
              <li>{t('purposes.item3')}</li>
              <li>{t('purposes.item4')}</li>
              <li>{t('purposes.item5')}</li>
            </ul>
          </section>
          
          {/* Legal Basis */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('legalBasis.title')}</h2>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li><strong>{t('legalBasis.contract')}</strong>: {t('legalBasis.contractDesc')}</li>
              <li><strong>{t('legalBasis.consent')}</strong>: {t('legalBasis.consentDesc')}</li>
              <li><strong>{t('legalBasis.legitimate')}</strong>: {t('legalBasis.legitimateDesc')}</li>
              <li><strong>{t('legalBasis.legal')}</strong>: {t('legalBasis.legalDesc')}</li>
            </ul>
          </section>
          
          {/* Retention */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('retention.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('retention.intro')}</p>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li>{t('retention.account')}</li>
              <li>{t('retention.content')}</li>
              <li>{t('retention.billing')}</li>
              <li>{t('retention.logs')}</li>
            </ul>
          </section>
          
          {/* Your Rights */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('rights.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('rights.intro')}</p>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li><strong>{t('rights.access')}</strong>: {t('rights.accessDesc')}</li>
              <li><strong>{t('rights.rectification')}</strong>: {t('rights.rectificationDesc')}</li>
              <li><strong>{t('rights.erasure')}</strong>: {t('rights.erasureDesc')}</li>
              <li><strong>{t('rights.portability')}</strong>: {t('rights.portabilityDesc')}</li>
              <li><strong>{t('rights.objection')}</strong>: {t('rights.objectionDesc')}</li>
              <li><strong>{t('rights.withdraw')}</strong>: {t('rights.withdrawDesc')}</li>
            </ul>
            <p className="text-slate-600 dark:text-slate-300 mt-4">{t('rights.howTo')}</p>
          </section>
          
          {/* International Transfers */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('transfers.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('transfers.intro')}</p>
            <p className="text-slate-600 dark:text-slate-300">{t('transfers.safeguards')}</p>
          </section>
          
          {/* Subprocessors */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('subprocessors.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('subprocessors.intro')}</p>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
                <thead className="bg-slate-100 dark:bg-slate-800">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 dark:text-slate-400">{t('subprocessors.name')}</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 dark:text-slate-400">{t('subprocessors.purpose')}</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 dark:text-slate-400">{t('subprocessors.location')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  <tr><td className="px-4 py-2 text-sm">Supabase</td><td className="px-4 py-2 text-sm">{t('subprocessors.supabase')}</td><td className="px-4 py-2 text-sm">EU (Frankfurt)</td></tr>
                  <tr><td className="px-4 py-2 text-sm">Vercel</td><td className="px-4 py-2 text-sm">{t('subprocessors.vercel')}</td><td className="px-4 py-2 text-sm">EU/US</td></tr>
                  <tr><td className="px-4 py-2 text-sm">Railway</td><td className="px-4 py-2 text-sm">{t('subprocessors.railway')}</td><td className="px-4 py-2 text-sm">EU</td></tr>
                  <tr><td className="px-4 py-2 text-sm">Stripe</td><td className="px-4 py-2 text-sm">{t('subprocessors.stripe')}</td><td className="px-4 py-2 text-sm">US (DPF)</td></tr>
                  <tr><td className="px-4 py-2 text-sm">Anthropic (Claude)</td><td className="px-4 py-2 text-sm">{t('subprocessors.anthropic')}</td><td className="px-4 py-2 text-sm">US (DPF)</td></tr>
                  <tr><td className="px-4 py-2 text-sm">Google AI (Gemini)</td><td className="px-4 py-2 text-sm">{t('subprocessors.google')}</td><td className="px-4 py-2 text-sm">US (DPF)</td></tr>
                  <tr><td className="px-4 py-2 text-sm">Pinecone</td><td className="px-4 py-2 text-sm">{t('subprocessors.pinecone')}</td><td className="px-4 py-2 text-sm">US (DPF)</td></tr>
                  <tr><td className="px-4 py-2 text-sm">Deepgram</td><td className="px-4 py-2 text-sm">{t('subprocessors.deepgram')}</td><td className="px-4 py-2 text-sm">US (DPF)</td></tr>
                  <tr><td className="px-4 py-2 text-sm">Inngest</td><td className="px-4 py-2 text-sm">{t('subprocessors.inngest')}</td><td className="px-4 py-2 text-sm">US (DPF)</td></tr>
                  <tr><td className="px-4 py-2 text-sm">Sentry</td><td className="px-4 py-2 text-sm">{t('subprocessors.sentry')}</td><td className="px-4 py-2 text-sm">US (DPF)</td></tr>
                </tbody>
              </table>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">{t('subprocessors.dpfNote')}</p>
          </section>
          
          {/* Security */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('security.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('security.intro')}</p>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li>{t('security.encryption')}</li>
              <li>{t('security.access')}</li>
              <li>{t('security.monitoring')}</li>
              <li>{t('security.testing')}</li>
            </ul>
          </section>
          
          {/* Cookies */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('cookies.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('cookies.intro')}</p>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li><strong>{t('cookies.essential')}</strong>: {t('cookies.essentialDesc')}</li>
              <li><strong>{t('cookies.preferences')}</strong>: {t('cookies.preferencesDesc')}</li>
            </ul>
            <p className="text-slate-600 dark:text-slate-300 mt-4">{t('cookies.noTracking')}</p>
          </section>
          
          {/* Complaints */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('complaints.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('complaints.intro')}</p>
            <div className="bg-slate-100 dark:bg-slate-800 rounded-lg p-4">
              <p className="text-slate-600 dark:text-slate-300 font-medium">{t('complaints.authority')}</p>
              <p className="text-slate-600 dark:text-slate-300">{t('complaints.authorityName')}</p>
              <a href="https://autoriteitpersoonsgegevens.nl" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline flex items-center gap-1">
                {t('complaints.authorityWebsite')} <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </section>
          
          {/* Changes */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('changes.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300">{t('changes.text')}</p>
          </section>
          
          {/* Contact */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('contact.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300">{t('contact.text')}</p>
            <p className="text-slate-600 dark:text-slate-300 mt-2">
              <a href="mailto:privacy@dealmotion.ai" className="text-blue-600 hover:underline">privacy@dealmotion.ai</a>
            </p>
          </section>
        </div>
      </main>
      
      {/* Footer */}
      <footer className="border-t border-slate-200 dark:border-slate-800 py-6">
        <div className="max-w-4xl mx-auto px-4 flex items-center justify-between text-sm text-slate-500">
          <span>© {new Date().getFullYear()} DealMotion B.V.</span>
          <div className="flex items-center gap-4">
            <Link href="/terms" className="hover:text-slate-900 dark:hover:text-white">
              {t('seeAlso.terms')}
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}

