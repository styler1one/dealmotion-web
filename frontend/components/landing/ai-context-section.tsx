'use client'

import { useTranslations } from 'next-intl'
import { Icons } from '@/components/icons'

const contextLayers = [
  { icon: 'user', key: 'profile', color: 'blue' },
  { icon: 'building', key: 'company', color: 'purple' },
  { icon: 'book', key: 'knowledge', color: 'green' },
  { icon: 'target', key: 'prospect', color: 'orange' },
] as const

const benefits = [
  { icon: 'sparkles', key: 'personalized' },
  { icon: 'zap', key: 'instant' },
  { icon: 'check', key: 'onBrand' },
  { icon: 'trendingUp', key: 'improves' },
] as const

export function AIContextSection() {
  const t = useTranslations('homepage.aiContext')

  const getIcon = (iconName: string) => {
    const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
      user: Icons.user,
      building: Icons.building,
      book: Icons.book,
      target: Icons.target,
      sparkles: Icons.sparkles,
      zap: Icons.zap,
      check: Icons.check,
      trendingUp: Icons.trendingUp,
    }
    return iconMap[iconName] || Icons.circle
  }

  const getColorClasses = (color: string) => {
    const colorMap: Record<string, { bg: string; text: string; ring: string }> = {
      blue: { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-600 dark:text-blue-400', ring: 'ring-blue-500/20' },
      purple: { bg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-600 dark:text-purple-400', ring: 'ring-purple-500/20' },
      green: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-600 dark:text-green-400', ring: 'ring-green-500/20' },
      orange: { bg: 'bg-orange-100 dark:bg-orange-900/30', text: 'text-orange-600 dark:text-orange-400', ring: 'ring-orange-500/20' },
    }
    return colorMap[color] || colorMap.blue
  }

  return (
    <section className="py-20 px-4 bg-gradient-to-b from-slate-50 to-white dark:from-slate-800/50 dark:to-slate-900">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 text-sm font-medium mb-6">
            <Icons.sparkles className="h-4 w-4" />
            {t('badge')}
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-4">
            {t('title')}
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">
            {t('subtitle')}
          </p>
        </div>

        {/* Context Flow Visualization */}
        <div className="grid lg:grid-cols-2 gap-12 items-center mb-16">
          {/* Left: Context Inputs */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
              {t('inputsTitle')}
            </h3>
            {contextLayers.map((layer) => {
              const Icon = getIcon(layer.icon)
              const colors = getColorClasses(layer.color)
              return (
                <div 
                  key={layer.key}
                  className={`flex items-center gap-4 p-4 rounded-xl bg-white dark:bg-slate-800 border dark:border-slate-700 shadow-sm hover:shadow-md transition-shadow ring-2 ${colors.ring}`}
                >
                  <div className={`w-12 h-12 rounded-xl ${colors.bg} flex items-center justify-center flex-shrink-0`}>
                    <Icon className={`h-6 w-6 ${colors.text}`} />
                  </div>
                  <div>
                    <h4 className="font-semibold text-slate-900 dark:text-white">
                      {t(`layers.${layer.key}.title`)}
                    </h4>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      {t(`layers.${layer.key}.description`)}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Right: Arrow + Output */}
          <div className="flex flex-col items-center lg:items-start">
            {/* Arrow */}
            <div className="hidden lg:flex items-center justify-center w-full mb-8">
              <div className="flex items-center gap-4">
                <div className="h-0.5 w-16 bg-gradient-to-r from-slate-200 to-purple-300 dark:from-slate-700 dark:to-purple-600" />
                <div className="w-12 h-12 rounded-full bg-gradient-to-r from-blue-600 to-violet-600 flex items-center justify-center">
                  <Icons.sparkles className="h-6 w-6 text-white" />
                </div>
                <div className="h-0.5 w-16 bg-gradient-to-r from-purple-300 to-orange-300 dark:from-purple-600 dark:to-orange-600" />
              </div>
            </div>

            {/* Output Card */}
            <div className="w-full p-6 rounded-2xl bg-gradient-to-br from-blue-600 to-violet-600 text-white shadow-xl">
              <div className="flex items-center gap-3 mb-4">
                <Icons.sparkles className="h-6 w-6" />
                <h3 className="text-lg font-semibold">{t('outputTitle')}</h3>
              </div>
              <p className="text-blue-100 mb-6">
                {t('outputDescription')}
              </p>
              <div className="grid grid-cols-2 gap-3">
                {benefits.map((benefit) => {
                  const Icon = getIcon(benefit.icon)
                  return (
                    <div key={benefit.key} className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-blue-200" />
                      <span className="text-sm text-blue-100">
                        {t(`benefits.${benefit.key}`)}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Quote */}
        <div className="text-center max-w-3xl mx-auto">
          <p className="text-xl text-slate-600 dark:text-slate-300 italic">
            "{t('quote')}"
          </p>
        </div>
      </div>
    </section>
  )
}

