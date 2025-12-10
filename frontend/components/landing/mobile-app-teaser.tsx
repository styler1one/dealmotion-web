'use client'

import { useTranslations } from 'next-intl'
import { Icons } from '@/components/icons'

const steps = [
  { icon: 'mic', key: 'record' },
  { icon: 'upload', key: 'upload' },
  { icon: 'sparkles', key: 'analyze' },
  { icon: 'mail', key: 'share' },
] as const

const useCases = [
  { icon: 'users', key: 'coffee' },
  { icon: 'building', key: 'onsite' },
  { icon: 'calendar', key: 'events' },
  { icon: 'globe', key: 'field' },
] as const

export function MobileAppTeaser() {
  const t = useTranslations('homepage.mobileApp')

  const getIcon = (iconName: string) => {
    const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
      mic: Icons.mic,
      upload: Icons.upload,
      sparkles: Icons.sparkles,
      mail: Icons.mail,
      users: Icons.users,
      building: Icons.building,
      calendar: Icons.calendar,
      globe: Icons.globe,
    }
    return iconMap[iconName] || Icons.circle
  }

  return (
    <section className="py-20 px-4 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 overflow-hidden">
      <div className="max-w-6xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          {/* Left: Content */}
          <div>
            {/* Beta Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-green-500/20 text-green-400 text-sm font-medium mb-6">
              <Icons.sparkles className="h-4 w-4" />
              {t('badge')}
            </div>

            <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
              {t('title')}
            </h2>
            <p className="text-lg text-slate-300 mb-8">
              {t('subtitle')}
            </p>

            {/* 4-Step Flow */}
            <div className="grid grid-cols-4 gap-2 mb-10">
              {steps.map((step, index) => {
                const Icon = getIcon(step.icon)
                return (
                  <div key={step.key} className="flex flex-col items-center text-center">
                    <div className="relative">
                      <div className="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center mb-2">
                        <Icon className="h-5 w-5 text-white" />
                      </div>
                      {index < steps.length - 1 && (
                        <div className="absolute top-1/2 left-full w-full h-0.5 bg-white/20 -translate-y-1/2" />
                      )}
                    </div>
                    <span className="text-xs text-slate-400">{t(`steps.${step.key}`)}</span>
                  </div>
                )
              })}
            </div>

            {/* Use Cases */}
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
              {t('useCasesTitle')}
            </h3>
            <div className="grid grid-cols-2 gap-3">
              {useCases.map((useCase) => {
                const Icon = getIcon(useCase.icon)
                return (
                  <div key={useCase.key} className="flex items-center gap-3 text-slate-300">
                    <Icon className="h-5 w-5 text-slate-500" />
                    <span className="text-sm">{t(`useCases.${useCase.key}`)}</span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Right: Phone Mockup */}
          <div className="flex justify-center lg:justify-end">
            <div className="relative">
              {/* Phone Frame */}
              <div className="w-64 h-[500px] bg-slate-800 rounded-[3rem] border-4 border-slate-700 shadow-2xl overflow-hidden">
                {/* Phone Notch */}
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-24 h-6 bg-slate-900 rounded-b-xl" />
                
                {/* Phone Screen Content */}
                <div className="h-full flex flex-col p-6 pt-10">
                  {/* App Header */}
                  <div className="flex items-center justify-between mb-8">
                    <div className="flex items-center gap-2">
                      <Icons.sparkles className="h-5 w-5 text-blue-400" />
                      <span className="text-white font-semibold text-sm">DealMotion</span>
                    </div>
                    <div className="w-8 h-8 rounded-full bg-slate-700" />
                  </div>

                  {/* Meeting Card */}
                  <div className="bg-slate-700/50 rounded-2xl p-4 mb-4">
                    <p className="text-white font-medium text-sm mb-1">Coffee with Sarah</p>
                    <p className="text-slate-400 text-xs">Acme Corp • Today at 2pm</p>
                  </div>

                  {/* Recording Button */}
                  <div className="flex-1 flex flex-col items-center justify-center">
                    <div className="w-24 h-24 rounded-full bg-gradient-to-br from-red-500 to-red-600 flex items-center justify-center shadow-lg shadow-red-500/30 mb-4">
                      <Icons.mic className="h-10 w-10 text-white" />
                    </div>
                    <p className="text-slate-400 text-sm">{t('tapToRecord')}</p>
                  </div>

                  {/* Bottom Nav */}
                  <div className="flex justify-around pt-4 border-t border-slate-700">
                    <Icons.calendar className="h-6 w-6 text-slate-500" />
                    <Icons.mic className="h-6 w-6 text-blue-400" />
                    <Icons.user className="h-6 w-6 text-slate-500" />
                  </div>
                </div>
              </div>

              {/* Decorative Elements */}
              <div className="absolute -top-4 -right-4 w-24 h-24 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-full blur-2xl" />
              <div className="absolute -bottom-4 -left-4 w-32 h-32 bg-gradient-to-br from-amber-500/20 to-red-500/20 rounded-full blur-2xl" />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

