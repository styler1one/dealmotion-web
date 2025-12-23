'use client'

import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { ArrowLeft, FileText } from 'lucide-react'
import Link from 'next/link'
import { Logo } from '@/components/dealmotion-logo'

export default function TermsPage() {
  const router = useRouter()
  const t = useTranslations('legal.terms')
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
            <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30">
              <FileText className="h-6 w-6 text-blue-600 dark:text-blue-400" />
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
          
          {/* Definitions */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('definitions.title')}</h2>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li><strong>"{t('definitions.service')}"</strong>: {t('definitions.serviceDesc')}</li>
              <li><strong>"{t('definitions.user')}"</strong>: {t('definitions.userDesc')}</li>
              <li><strong>"{t('definitions.content')}"</strong>: {t('definitions.contentDesc')}</li>
              <li><strong>"{t('definitions.subscription')}"</strong>: {t('definitions.subscriptionDesc')}</li>
            </ul>
          </section>
          
          {/* Service Description */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('service.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('service.intro')}</p>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li>{t('service.feature1')}</li>
              <li>{t('service.feature2')}</li>
              <li>{t('service.feature3')}</li>
              <li>{t('service.feature4')}</li>
              <li>{t('service.feature5')}</li>
            </ul>
          </section>
          
          {/* Account Registration */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('account.title')}</h2>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li>{t('account.item1')}</li>
              <li>{t('account.item2')}</li>
              <li>{t('account.item3')}</li>
              <li>{t('account.item4')}</li>
            </ul>
          </section>
          
          {/* User Responsibilities */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('responsibilities.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('responsibilities.intro')}</p>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li>{t('responsibilities.item1')}</li>
              <li>{t('responsibilities.item2')}</li>
              <li>{t('responsibilities.item3')}</li>
              <li>{t('responsibilities.item4')}</li>
            </ul>
          </section>
          
          {/* Acceptable Use */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('acceptableUse.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('acceptableUse.intro')}</p>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li>{t('acceptableUse.prohibited1')}</li>
              <li>{t('acceptableUse.prohibited2')}</li>
              <li>{t('acceptableUse.prohibited3')}</li>
              <li>{t('acceptableUse.prohibited4')}</li>
              <li>{t('acceptableUse.prohibited5')}</li>
            </ul>
          </section>
          
          {/* Subscription & Payment */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('payment.title')}</h2>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li>{t('payment.item1')}</li>
              <li>{t('payment.item2')}</li>
              <li>{t('payment.item3')}</li>
              <li>{t('payment.item4')}</li>
              <li>{t('payment.item5')}</li>
            </ul>
          </section>
          
          {/* Data & Content */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('data.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('data.intro')}</p>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li>{t('data.item1')}</li>
              <li>{t('data.item2')}</li>
              <li>{t('data.item3')}</li>
            </ul>
          </section>
          
          {/* Intellectual Property */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('ip.title')}</h2>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li>{t('ip.item1')}</li>
              <li>{t('ip.item2')}</li>
              <li>{t('ip.item3')}</li>
            </ul>
          </section>
          
          {/* AI Generated Content */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('ai.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('ai.intro')}</p>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li>{t('ai.item1')}</li>
              <li>{t('ai.item2')}</li>
              <li>{t('ai.item3')}</li>
            </ul>
          </section>
          
          {/* Liability Limitation */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('liability.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('liability.intro')}</p>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li>{t('liability.item1')}</li>
              <li>{t('liability.item2')}</li>
              <li>{t('liability.item3')}</li>
            </ul>
          </section>
          
          {/* Termination */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('termination.title')}</h2>
            <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2">
              <li>{t('termination.item1')}</li>
              <li>{t('termination.item2')}</li>
              <li>{t('termination.item3')}</li>
              <li>{t('termination.item4')}</li>
            </ul>
          </section>
          
          {/* Governing Law */}
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">{t('law.title')}</h2>
            <p className="text-slate-600 dark:text-slate-300 mb-4">{t('law.text')}</p>
            <p className="text-slate-600 dark:text-slate-300">{t('law.disputes')}</p>
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
              <a href="mailto:legal@dealmotion.ai" className="text-blue-600 hover:underline">legal@dealmotion.ai</a>
            </p>
          </section>
        </div>
      </main>
      
      {/* Footer */}
      <footer className="border-t border-slate-200 dark:border-slate-800 py-6">
        <div className="max-w-4xl mx-auto px-4 flex items-center justify-between text-sm text-slate-500">
          <span>© {new Date().getFullYear()} DealMotion B.V.</span>
          <div className="flex items-center gap-4">
            <Link href="/privacy" className="hover:text-slate-900 dark:hover:text-white">
              {t('seeAlso.privacy')}
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}

