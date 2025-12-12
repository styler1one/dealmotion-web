'use client'

import { useTranslations } from 'next-intl'
import { Icons } from '@/components/icons'

const steps = [
  { icon: 'calendar', key: 'open' },
  { icon: 'alertCircle', key: 'unprepared' },
  { icon: 'sparkles', key: 'brief' },
  { icon: 'checkCircle', key: 'confident' },
  { icon: 'bot', key: 'botJoins' },
  { icon: 'mic', key: 'record' },
  { icon: 'mail', key: 'sent' },
] as const

export function DayInTheLife() {
  const t = useTranslations('homepage.dayInTheLife')

  const getIcon = (iconName: string) => {
    const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
      calendar: Icons.calendar,
      alertCircle: Icons.alertCircle,
      sparkles: Icons.sparkles,
      checkCircle: Icons.checkCircle,
      bot: Icons.sparkles, // AI bot
      mic: Icons.mic,
      mail: Icons.mail,
    }
    return iconMap[iconName] || Icons.circle
  }

  return (
    <section className="py-20 px-4 bg-white dark:bg-slate-900">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-4">
            {t('title')}
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-300">
            {t('intro')}
          </p>
        </div>

        {/* Timeline */}
        <div className="relative">
          {/* Vertical Line */}
          <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-gradient-to-b from-blue-200 via-purple-200 to-orange-200 dark:from-blue-800 dark:via-purple-800 dark:to-orange-800" />

          {/* Steps */}
          <div className="space-y-6">
            {steps.map((step, index) => {
              const Icon = getIcon(step.icon)
              const isHighlight = step.key === 'brief' || step.key === 'botJoins' || step.key === 'record'

              return (
                <div key={step.key} className="flex items-start gap-6 group">
                  {/* Icon */}
                  <div className={`
                    relative z-10 w-16 h-16 rounded-xl flex items-center justify-center flex-shrink-0
                    ${isHighlight 
                      ? 'bg-gradient-to-br from-blue-500 to-violet-600 text-white shadow-lg shadow-blue-500/20' 
                      : 'bg-white dark:bg-slate-800 border-2 border-slate-200 dark:border-slate-700'
                    }
                    group-hover:scale-105 transition-transform
                  `}>
                    <Icon className={`h-7 w-7 ${isHighlight ? 'text-white' : 'text-slate-600 dark:text-slate-400'}`} />
                  </div>

                  {/* Content */}
                  <div className={`
                    flex-1 p-4 rounded-xl 
                    ${isHighlight 
                      ? 'bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800' 
                      : 'bg-slate-50 dark:bg-slate-800/50'
                    }
                  `}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium text-slate-400 dark:text-slate-500">
                        {t(`steps.${step.key}.time`)}
                      </span>
                    </div>
                    <p className={`font-medium ${isHighlight ? 'text-blue-900 dark:text-blue-100' : 'text-slate-900 dark:text-white'}`}>
                      {t(`steps.${step.key}.text`)}
                    </p>
                    {isHighlight && (
                      <p className="text-sm text-blue-600 dark:text-blue-400 mt-1">
                        {t(`steps.${step.key}.highlight`)}
                      </p>
                    )}
                  </div>

                  {/* Arrow to next */}
                  {index < steps.length - 1 && (
                    <div className="absolute left-8 mt-20 transform -translate-x-1/2">
                      <Icons.arrowDown className="h-4 w-4 text-slate-300 dark:text-slate-600 opacity-0" />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Bottom Tagline */}
        <div className="text-center mt-12">
          <p className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-violet-600">
            {t('tagline')}
          </p>
        </div>
      </div>
    </section>
  )
}

