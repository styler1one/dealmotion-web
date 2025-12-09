'use client'

import { useTranslations } from 'next-intl'
import { Icons } from '@/components/icons'

const outputs: Array<{
  icon: string
  key: string
  color: string
  highlight?: boolean
}> = [
  { icon: 'fileText', key: 'summary', color: 'blue' },
  { icon: 'users', key: 'customerReport', color: 'green', highlight: true },
  { icon: 'mail', key: 'shareEmail', color: 'orange' },
  { icon: 'barChart', key: 'commercialAnalysis', color: 'purple', highlight: true },
  { icon: 'sparkles', key: 'salesCoaching', color: 'pink', highlight: true },
  { icon: 'checkCircle', key: 'actionItems', color: 'cyan' },
  { icon: 'briefcase', key: 'internalReport', color: 'slate', highlight: true },
]

export function MeetingAnalysisShowcase() {
  const t = useTranslations('homepage.meetingAnalysis')

  const getIcon = (iconName: string) => {
    const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
      fileText: Icons.fileText,
      users: Icons.users,
      mail: Icons.mail,
      barChart: Icons.barChart,
      sparkles: Icons.sparkles,
      checkCircle: Icons.checkCircle,
      briefcase: Icons.briefcase,
    }
    return iconMap[iconName] || Icons.circle
  }

  const getColorClasses = (color: string) => {
    const colorMap: Record<string, { bg: string; text: string; border: string }> = {
      blue: { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-600 dark:text-blue-400', border: 'border-blue-200 dark:border-blue-700' },
      green: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-600 dark:text-green-400', border: 'border-green-200 dark:border-green-700' },
      orange: { bg: 'bg-orange-100 dark:bg-orange-900/30', text: 'text-orange-600 dark:text-orange-400', border: 'border-orange-200 dark:border-orange-700' },
      purple: { bg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-600 dark:text-purple-400', border: 'border-purple-200 dark:border-purple-700' },
      pink: { bg: 'bg-pink-100 dark:bg-pink-900/30', text: 'text-pink-600 dark:text-pink-400', border: 'border-pink-200 dark:border-pink-700' },
      cyan: { bg: 'bg-cyan-100 dark:bg-cyan-900/30', text: 'text-cyan-600 dark:text-cyan-400', border: 'border-cyan-200 dark:border-cyan-700' },
      slate: { bg: 'bg-slate-100 dark:bg-slate-800', text: 'text-slate-600 dark:text-slate-400', border: 'border-slate-200 dark:border-slate-700' },
    }
    return colorMap[color] || colorMap.blue
  }

  return (
    <section className="py-20 px-4 bg-white dark:bg-slate-900">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400 text-sm font-medium mb-6">
            <Icons.mic className="h-4 w-4" />
            {t('badge')}
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-4">
            {t('title')}
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">
            {t('subtitle')}
          </p>
        </div>

        {/* Visual Flow */}
        <div className="flex flex-col lg:flex-row items-center gap-8 mb-12">
          {/* Recording Input */}
          <div className="flex-shrink-0 w-48 h-48 rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 flex flex-col items-center justify-center text-white shadow-xl">
            <Icons.mic className="h-16 w-16 mb-3" />
            <span className="font-semibold">{t('recording')}</span>
            <span className="text-sm text-orange-100">{t('anyMeeting')}</span>
          </div>

          {/* Arrow */}
          <div className="hidden lg:flex items-center">
            <div className="w-16 h-0.5 bg-gradient-to-r from-orange-300 to-blue-300 dark:from-orange-600 dark:to-blue-600" />
            <Icons.chevronRight className="h-8 w-8 text-slate-300 dark:text-slate-600" />
          </div>
          <div className="lg:hidden">
            <Icons.arrowDown className="h-8 w-8 text-slate-300 dark:text-slate-600" />
          </div>

          {/* Outputs Grid */}
          <div className="flex-1 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {outputs.map((output) => {
              const Icon = getIcon(output.icon)
              const colors = getColorClasses(output.color)
              return (
                <div
                  key={output.key}
                  className={`
                    relative p-4 rounded-xl border ${colors.border} bg-white dark:bg-slate-800 
                    hover:shadow-lg transition-all hover:-translate-y-1
                    ${output.highlight ? 'ring-2 ring-offset-2 ring-offset-white dark:ring-offset-slate-900 ring-purple-400/30' : ''}
                  `}
                >
                  {output.highlight && (
                    <div className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-purple-500 flex items-center justify-center">
                      <Icons.sparkles className="h-3 w-3 text-white" />
                    </div>
                  )}
                  <div className={`w-10 h-10 rounded-lg ${colors.bg} flex items-center justify-center mb-3`}>
                    <Icon className={`h-5 w-5 ${colors.text}`} />
                  </div>
                  <h4 className="font-semibold text-sm text-slate-900 dark:text-white mb-1">
                    {t(`outputs.${output.key}.title`)}
                  </h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {t(`outputs.${output.key}.description`)}
                  </p>
                </div>
              )
            })}
          </div>
        </div>

        {/* Bottom Highlight */}
        <div className="text-center p-6 rounded-xl bg-gradient-to-r from-purple-50 to-orange-50 dark:from-purple-900/20 dark:to-orange-900/20 border border-purple-100 dark:border-purple-800">
          <p className="text-lg font-medium text-slate-900 dark:text-white">
            {t('highlight')}
          </p>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            {t('highlightSub')}
          </p>
        </div>
      </div>
    </section>
  )
}

