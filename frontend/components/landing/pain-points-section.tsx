'use client'

import { useTranslations } from 'next-intl'
import { Icons } from '@/components/icons'

const painPoints = [
  { key: 'research', beforeIcon: 'clock', afterIcon: 'zap' },
  { key: 'prep', beforeIcon: 'alertTriangle', afterIcon: 'check' },
  { key: 'notes', beforeIcon: 'x', afterIcon: 'sparkles' },
  { key: 'followup', beforeIcon: 'clock', afterIcon: 'mail' },
] as const

export function PainPointsSection() {
  const t = useTranslations('homepage.painPoints')

  const getIcon = (iconName: string) => {
    const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
      clock: Icons.clock,
      zap: Icons.zap,
      alertTriangle: Icons.alertTriangle,
      check: Icons.check,
      x: Icons.x,
      sparkles: Icons.sparkles,
      mail: Icons.mail,
    }
    return iconMap[iconName] || Icons.circle
  }

  return (
    <section className="py-20 px-4 bg-slate-50 dark:bg-slate-800/50">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-4">
            {t('title')}
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">
            {t('subtitle')}
          </p>
        </div>

        {/* Pain Points Grid */}
        <div className="grid md:grid-cols-2 gap-6">
          {painPoints.map((point) => {
            const BeforeIcon = getIcon(point.beforeIcon)
            const AfterIcon = getIcon(point.afterIcon)

            return (
              <div 
                key={point.key}
                className="group bg-white dark:bg-slate-800 rounded-2xl p-6 border dark:border-slate-700 shadow-sm hover:shadow-lg transition-all"
              >
                <div className="flex items-stretch gap-4">
                  {/* Before */}
                  <div className="flex-1 p-4 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-900/30">
                    <div className="flex items-center gap-2 mb-2">
                      <BeforeIcon className="h-4 w-4 text-red-500" />
                      <span className="text-xs font-medium text-red-600 dark:text-red-400 uppercase tracking-wider">
                        {t('before')}
                      </span>
                    </div>
                    <p className="text-sm text-red-700 dark:text-red-300">
                      {t(`items.${point.key}.before`)}
                    </p>
                  </div>

                  {/* Arrow */}
                  <div className="flex items-center">
                    <Icons.arrowRight className="h-5 w-5 text-slate-300 dark:text-slate-600 group-hover:text-green-500 transition-colors" />
                  </div>

                  {/* After */}
                  <div className="flex-1 p-4 rounded-xl bg-green-50 dark:bg-green-900/20 border border-green-100 dark:border-green-900/30">
                    <div className="flex items-center gap-2 mb-2">
                      <AfterIcon className="h-4 w-4 text-green-500" />
                      <span className="text-xs font-medium text-green-600 dark:text-green-400 uppercase tracking-wider">
                        {t('after')}
                      </span>
                    </div>
                    <p className="text-sm text-green-700 dark:text-green-300">
                      {t(`items.${point.key}.after`)}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

