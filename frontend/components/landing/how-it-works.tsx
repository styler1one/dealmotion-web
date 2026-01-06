'use client'

import { useTranslations } from 'next-intl'
import { Icons } from '@/components/icons'

const steps = [
  { icon: 'calendar', color: 'indigo', key: 'calendar' },
  { icon: 'search', color: 'blue', key: 'research' },
  { icon: 'send', color: 'rose', key: 'outreach' },
  { icon: 'fileText', color: 'green', key: 'prep' },
  { icon: 'mic', color: 'amber', key: 'meeting' },
  { icon: 'barChart', color: 'purple', key: 'analysis' },
  { icon: 'mail', color: 'orange', key: 'followup' },
] as const

export function HowItWorks() {
  const t = useTranslations('homepage.howItWorks')

  const getIcon = (iconName: string) => {
    const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
      calendar: Icons.calendar,
      search: Icons.search,
      send: Icons.send,
      fileText: Icons.fileText,
      mic: Icons.mic,
      barChart: Icons.barChart,
      mail: Icons.mail,
    }
    return iconMap[iconName] || Icons.circle
  }

  const getColorClasses = (color: string) => {
    const colorMap: Record<string, { bg: string; text: string; border: string }> = {
      indigo: { bg: 'bg-indigo-100 dark:bg-indigo-900/30', text: 'text-indigo-600 dark:text-indigo-400', border: 'border-indigo-200 dark:border-indigo-800' },
      blue: { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-600 dark:text-blue-400', border: 'border-blue-200 dark:border-blue-800' },
      rose: { bg: 'bg-rose-100 dark:bg-rose-900/30', text: 'text-rose-600 dark:text-rose-400', border: 'border-rose-200 dark:border-rose-800' },
      green: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-600 dark:text-green-400', border: 'border-green-200 dark:border-green-800' },
      amber: { bg: 'bg-amber-100 dark:bg-amber-900/30', text: 'text-amber-600 dark:text-amber-400', border: 'border-amber-200 dark:border-amber-800' },
      purple: { bg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-600 dark:text-purple-400', border: 'border-purple-200 dark:border-purple-800' },
      orange: { bg: 'bg-orange-100 dark:bg-orange-900/30', text: 'text-orange-600 dark:text-orange-400', border: 'border-orange-200 dark:border-orange-800' },
    }
    return colorMap[color] || colorMap.blue
  }

  return (
    <section className="py-20 px-4 bg-slate-50 dark:bg-slate-800/50">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-4">
            {t('title')}
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">
            {t('subtitle')}
          </p>
        </div>

        <div className="relative">
          {/* Connection Line */}
          <div className="hidden lg:block absolute top-1/2 left-0 right-0 h-0.5 bg-gradient-to-r from-indigo-200 via-purple-200 to-orange-200 dark:from-indigo-800 dark:via-purple-800 dark:to-orange-800 -translate-y-1/2" />

          {/* Steps Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-6 lg:gap-3">
            {steps.map((step, index) => {
              const Icon = getIcon(step.icon)
              const colors = getColorClasses(step.color)

              return (
                <div key={step.key} className="relative flex flex-col items-center text-center group">
                  {/* Step Number Badge */}
                  <div className={`absolute -top-2 -right-2 w-6 h-6 rounded-full bg-white dark:bg-slate-900 border-2 ${colors.border} flex items-center justify-center text-xs font-bold ${colors.text} z-10`}>
                    {index + 1}
                  </div>

                  {/* Icon Circle */}
                  <div className={`relative w-16 h-16 rounded-full ${colors.bg} flex items-center justify-center mb-3 group-hover:scale-110 transition-transform border-2 ${colors.border} bg-white dark:bg-slate-900`}>
                    <Icon className={`h-7 w-7 ${colors.text}`} />
                  </div>

                  {/* Arrow (between steps) */}
                  {index < steps.length - 1 && (
                    <div className="hidden lg:block absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 z-20">
                      <Icons.chevronRight className="h-5 w-5 text-slate-300 dark:text-slate-600" />
                    </div>
                  )}

                  {/* Label */}
                  <h3 className="font-semibold text-sm text-slate-900 dark:text-white">
                    {t(`steps.${step.key}.title`)}
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-[120px]">
                    {t(`steps.${step.key}.description`)}
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </section>
  )
}

