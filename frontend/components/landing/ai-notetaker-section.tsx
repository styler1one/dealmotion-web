'use client'

import { useTranslations } from 'next-intl'
import { Icons } from '@/components/icons'

const features = [
  { icon: 'mail', key: 'emailInvite', color: 'blue' },
  { icon: 'calendar', key: 'autoRecord', color: 'green' },
  { icon: 'settings', key: 'smartFilters', color: 'purple' },
  { icon: 'globe', key: 'platforms', color: 'orange' },
] as const

const steps = [
  { icon: 'mail', key: 'invite' },
  { icon: 'bot', key: 'join' },
  { icon: 'mic', key: 'record' },
  { icon: 'sparkles', key: 'analyze' },
] as const

export function AINotetakerSection() {
  const t = useTranslations('homepage.aiNotetakerSection')

  const getIcon = (iconName: string) => {
    const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
      mail: Icons.mail,
      calendar: Icons.calendar,
      settings: Icons.settings,
      globe: Icons.globe,
      bot: Icons.sparkles,
      mic: Icons.mic,
      sparkles: Icons.sparkles,
      check: Icons.check,
      arrowRight: Icons.arrowRight,
    }
    return iconMap[iconName] || Icons.circle
  }

  const getColorClasses = (color: string) => {
    const colorMap: Record<string, { bg: string; text: string; border: string }> = {
      blue: { 
        bg: 'bg-blue-100 dark:bg-blue-900/30', 
        text: 'text-blue-600 dark:text-blue-400',
        border: 'border-blue-200 dark:border-blue-800'
      },
      green: { 
        bg: 'bg-green-100 dark:bg-green-900/30', 
        text: 'text-green-600 dark:text-green-400',
        border: 'border-green-200 dark:border-green-800'
      },
      purple: { 
        bg: 'bg-purple-100 dark:bg-purple-900/30', 
        text: 'text-purple-600 dark:text-purple-400',
        border: 'border-purple-200 dark:border-purple-800'
      },
      orange: { 
        bg: 'bg-orange-100 dark:bg-orange-900/30', 
        text: 'text-orange-600 dark:text-orange-400',
        border: 'border-orange-200 dark:border-orange-800'
      },
    }
    return colorMap[color] || colorMap.blue
  }

  return (
    <section className="py-20 px-4 bg-gradient-to-b from-violet-50 to-white dark:from-violet-950/30 dark:to-slate-900">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-400 text-sm font-medium mb-6">
            <Icons.zap className="h-4 w-4" />
            {t('badge')}
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-4">
            {t('title')}
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-300 max-w-3xl mx-auto">
            {t('subtitle')}
          </p>
        </div>

        {/* Features Grid */}
        <div className="grid md:grid-cols-2 gap-6 mb-16">
          {features.map((feature) => {
            const Icon = getIcon(feature.icon)
            const colors = getColorClasses(feature.color)
            return (
              <div 
                key={feature.key}
                className={`p-6 rounded-2xl bg-white dark:bg-slate-800 border-2 ${colors.border} shadow-sm hover:shadow-md transition-all duration-300 hover:-translate-y-1`}
              >
                <div className="flex items-start gap-4">
                  <div className={`w-12 h-12 rounded-xl ${colors.bg} flex items-center justify-center flex-shrink-0`}>
                    <Icon className={`h-6 w-6 ${colors.text}`} />
                  </div>
                  <div>
                    <h3 className="font-semibold text-lg text-slate-900 dark:text-white mb-2">
                      {t(`${feature.key}.title`)}
                    </h3>
                    <p className="text-slate-600 dark:text-slate-400">
                      {t(`${feature.key}.description`)}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        {/* How It Works Mini */}
        <div className="bg-gradient-to-r from-violet-600 to-purple-600 rounded-2xl p-8 text-white">
          <h3 className="text-xl font-semibold text-center mb-8">
            {t('howItWorksTitle')}
          </h3>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-0">
            {steps.map((step, index) => {
              const Icon = getIcon(step.icon)
              return (
                <div key={step.key} className="flex items-center">
                  <div className="flex flex-col items-center">
                    <div className="w-14 h-14 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center mb-3">
                      <Icon className="h-7 w-7 text-white" />
                    </div>
                    <span className="text-sm text-white/90 text-center max-w-[120px]">
                      {t(`steps.${step.key}`)}
                    </span>
                  </div>
                  {index < steps.length - 1 && (
                    <div className="hidden sm:block mx-4">
                      <Icons.arrowRight className="h-5 w-5 text-white/50" />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          
          {/* Bot Name Badge */}
          <div className="mt-8 flex justify-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 backdrop-blur-sm text-white/90 text-sm">
              <Icons.sparkles className="h-4 w-4" />
              {t('botName')}
            </div>
          </div>
        </div>

        {/* Platform Badges */}
        <div className="mt-12 flex flex-wrap justify-center gap-4">
          {['Microsoft Teams', 'Google Meet', 'Zoom', 'Webex'].map((platform) => (
            <div 
              key={platform}
              className="px-4 py-2 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 text-sm font-medium border dark:border-slate-700"
            >
              {platform}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

