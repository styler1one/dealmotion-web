'use client'

import { useTranslations } from 'next-intl'
import { Icons } from '@/components/icons'

const integrations = [
  { name: 'Google Calendar', available: true },
  { name: 'Outlook', available: false },
  { name: 'Zoom', available: false },
  { name: 'Teams', available: false },
  { name: 'Slack', available: false },
  { name: 'Salesforce', available: false },
  { name: 'HubSpot', available: false },
] as const

export function IntegrationsRow() {
  const t = useTranslations('homepage.integrations')

  return (
    <section className="py-16 px-4 bg-white dark:bg-slate-900 border-y dark:border-slate-800">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-10">
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
            {t('title')}
          </h2>
          <p className="text-slate-600 dark:text-slate-400">
            {t('subtitle')}
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-6 md:gap-10">
          {integrations.map((integration) => (
            <div 
              key={integration.name}
              className="flex flex-col items-center gap-2 group"
            >
              <div className={`
                w-16 h-16 rounded-xl flex items-center justify-center transition-all
                ${integration.available 
                  ? 'bg-slate-100 dark:bg-slate-800 group-hover:bg-slate-200 dark:group-hover:bg-slate-700' 
                  : 'bg-slate-50 dark:bg-slate-800/50 opacity-50'
                }
              `}>
                {/* Placeholder icon - in production these would be real logos */}
                <Icons.link className={`h-8 w-8 ${integration.available ? 'text-slate-700 dark:text-slate-300' : 'text-slate-400 dark:text-slate-600'}`} />
              </div>
              <div className="text-center">
                <span className={`text-sm font-medium ${integration.available ? 'text-slate-900 dark:text-white' : 'text-slate-400 dark:text-slate-600'}`}>
                  {integration.name}
                </span>
                {!integration.available && (
                  <span className="block text-xs text-slate-400 dark:text-slate-500">
                    {t('comingSoon')}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

