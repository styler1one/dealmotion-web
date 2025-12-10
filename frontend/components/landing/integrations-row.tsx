'use client'

import { useTranslations } from 'next-intl'
import { Icons } from '@/components/icons'

type IconKey = 'google' | 'microsoft' | 'fireflies' | 'teams' | 'zoom' | 'slack' | 'salesforce' | 'hubspot'

const integrations: Array<{ name: string; icon: IconKey; available: boolean }> = [
  { name: 'Google Calendar', icon: 'google', available: true },
  { name: 'Microsoft 365', icon: 'microsoft', available: true },
  { name: 'Fireflies.ai', icon: 'fireflies', available: true },
  { name: 'Teams', icon: 'teams', available: true },
  { name: 'Zoom', icon: 'zoom', available: false },
  { name: 'Slack', icon: 'slack', available: false },
  { name: 'Salesforce', icon: 'salesforce', available: false },
  { name: 'HubSpot', icon: 'hubspot', available: false },
]

export function IntegrationsRow() {
  const t = useTranslations('homepage.integrations')

  const getIcon = (iconName: IconKey) => {
    const iconMap: Record<IconKey, React.ComponentType<{ className?: string }>> = {
      google: Icons.google,
      microsoft: Icons.microsoft,
      fireflies: Icons.fireflies,
      teams: Icons.teams,
      zoom: Icons.zoom,
      slack: Icons.slack,
      salesforce: Icons.salesforce,
      hubspot: Icons.hubspot,
    }
    return iconMap[iconName]
  }

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
          {integrations.map((integration) => {
            const Icon = getIcon(integration.icon)
            return (
              <div 
                key={integration.name}
                className="flex flex-col items-center gap-2 group"
              >
                <div className={`
                  w-16 h-16 rounded-xl flex items-center justify-center transition-all
                  ${integration.available 
                    ? 'bg-slate-100 dark:bg-slate-800 group-hover:bg-slate-200 dark:group-hover:bg-slate-700 group-hover:scale-105' 
                    : 'bg-slate-50 dark:bg-slate-800/50 opacity-50'
                  }
                `}>
                  <Icon className="h-8 w-8" />
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
            )
          })}
        </div>
      </div>
    </section>
  )
}

