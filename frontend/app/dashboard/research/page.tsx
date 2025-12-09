'use client'

import { useState, useEffect, useCallback } from 'react'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { Toaster } from '@/components/ui/toaster'
import { DashboardLayout } from '@/components/layout'
import { formatDate } from '@/lib/date-utils'
import { useTranslations } from 'next-intl'
import { useSettings } from '@/lib/settings-context'
import { api } from '@/lib/api'
import { useConfirmDialog } from '@/components/confirm-dialog'
import { logger } from '@/lib/logger'
import { ResearchForm } from '@/components/forms'
import type { User } from '@supabase/supabase-js'
import type { ResearchBrief } from '@/types'

export default function ResearchPage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const { confirm } = useConfirmDialog()
  const t = useTranslations('research')
  const { settings } = useSettings()
  
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [briefs, setBriefs] = useState<ResearchBrief[]>([])

  // Get user for display purposes (non-blocking)
  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      setUser(user)
    })
  }, [supabase])

  const fetchBriefs = useCallback(async () => {
    try {
      const { data, error } = await api.get<{ briefs: ResearchBrief[] }>('/api/v1/research/briefs')

      if (!error && data) {
        setBriefs(data.briefs || [])
      }
    } catch (error) {
      logger.error('Failed to fetch briefs', error)
    }
  }, [])

  // Fetch briefs on mount
  useEffect(() => {
    fetchBriefs().finally(() => {
      setLoading(false)
    })
  }, [fetchBriefs])

  const handleDeleteBrief = async (briefId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    
    const confirmed = await confirm({
      title: t('confirm.deleteTitle'),
      description: t('confirm.deleteDescription'),
      confirmLabel: t('confirm.deleteButton'),
      cancelLabel: t('confirm.cancelButton'),
      variant: 'danger'
    })
    
    if (!confirmed) return
    
    try {
      const { error } = await api.delete(`/api/v1/research/${briefId}`)

      if (!error) {
        await fetchBriefs()
        toast({
          title: t('toast.deleted'),
          description: t('toast.deletedDesc'),
        })
      } else {
        throw new Error('Delete failed')
      }
    } catch (error) {
      logger.error('Delete failed', error)
      toast({
        variant: "destructive",
        title: t('toast.deleteFailed'),
        description: t('toast.deleteFailedDesc'),
      })
    }
  }

  // Auto-refresh for processing briefs
  useEffect(() => {
    const hasProcessingBriefs = briefs.some(b => 
      b.status === 'pending' || b.status === 'researching'
    )

    if (hasProcessingBriefs) {
      const interval = setInterval(() => {
        fetchBriefs()
      }, 5000)

      return () => clearInterval(interval)
    }
  }, [briefs, fetchBriefs])

  // Callback when research is started successfully
  const handleResearchSuccess = () => {
    fetchBriefs()
    // Auto-refresh after 3 seconds to catch status updates
    setTimeout(() => fetchBriefs(), 3000)
  }

  if (loading) {
    return (
      <DashboardLayout user={user}>
        <div className="flex items-center justify-center h-full">
          <div className="text-center space-y-4">
            <Icons.spinner className="h-8 w-8 animate-spin text-blue-600 mx-auto" />
            <p className="text-slate-500 dark:text-slate-400">{t('loading')}</p>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  if (!user) {
    router.push('/login')
    return null
  }

  const completedBriefs = briefs.filter(b => b.status === 'completed').length
  const processingBriefs = briefs.filter(b => b.status === 'researching' || b.status === 'pending').length

  return (
    <DashboardLayout user={user}>
      <div className="p-4 lg:p-6">
        {/* Page Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">
            {t('title')}
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            {t('subtitle')}
          </p>
        </div>

        {/* Two Column Layout */}
        <div className="flex gap-6">
          
          {/* Left Column - Research History */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                <Icons.fileText className="h-5 w-5 text-slate-400" />
                {t('history.title')}
                <span className="text-sm font-normal text-slate-400">({briefs.length})</span>
              </h2>
              <Button variant="ghost" size="sm" onClick={fetchBriefs}>
                <Icons.refresh className="h-4 w-4" />
              </Button>
            </div>

            {briefs.length === 0 ? (
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-12 text-center">
                <Icons.search className="h-16 w-16 text-slate-200 dark:text-slate-700 mx-auto mb-4" />
                <h3 className="font-semibold text-slate-700 dark:text-slate-200 mb-2">{t('history.empty')}</h3>
                <p className="text-slate-500 dark:text-slate-400 text-sm mb-4">
                  {t('history.emptyDesc')}
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {briefs.map((brief) => (
                  <div
                    key={brief.id}
                    className={`bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 hover:shadow-md dark:hover:shadow-slate-800/50 transition-all cursor-pointer group ${
                      brief.status === 'completed' ? 'hover:border-blue-300 dark:hover:border-blue-700' : ''
                    }`}
                    onClick={() => brief.status === 'completed' && router.push(`/dashboard/research/${brief.id}`)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-semibold text-slate-900 dark:text-white truncate">{brief.company_name}</h4>
                          
                          {brief.status === 'completed' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 dark:bg-green-900/50 text-green-700 dark:text-green-400 flex-shrink-0">
                              <Icons.check className="h-3 w-3" />
                              {t('stats.completed')}
                            </span>
                          )}
                          {brief.status === 'researching' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400 flex-shrink-0">
                              <Icons.spinner className="h-3 w-3 animate-spin" />
                              {t('stats.researching')}
                            </span>
                          )}
                          {brief.status === 'pending' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-50 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-400 flex-shrink-0">
                              <Icons.clock className="h-3 w-3" />
                              {t('stats.researching')}
                            </span>
                          )}
                          {brief.status === 'failed' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 dark:bg-red-900/50 text-red-700 dark:text-red-400 flex-shrink-0">
                              <Icons.alertCircle className="h-3 w-3" />
                              {t('stats.failed')}
                            </span>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                          {(brief.city || brief.country) && (
                            <span>📍 {[brief.city, brief.country].filter(Boolean).join(', ')}</span>
                          )}
                          <span>{formatDate(brief.created_at, settings.output_language)}</span>
                        </div>
                        
                        {brief.error_message && (
                          <p className="text-xs text-red-600 dark:text-red-400 mt-2 truncate">
                            {brief.error_message}
                          </p>
                        )}
                      </div>
                      
                      <div className="flex items-center gap-1 ml-4">
                        {brief.status === 'completed' && (
                          <>
                            <Button
                              variant="default"
                              size="sm"
                              className="h-8 text-xs bg-blue-600 hover:bg-blue-700"
                              onClick={(e) => {
                                e.stopPropagation()
                                router.push(`/dashboard/research/${brief.id}`)
                              }}
                            >
                              <Icons.arrowRight className="h-3 w-3 mr-1" />
                              {t('brief.view')}
                            </Button>
                          </>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-slate-400 hover:text-red-600 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => handleDeleteBrief(brief.id, e)}
                        >
                          <Icons.trash className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right Column - Sticky Sidebar */}
          <div className="w-80 flex-shrink-0 hidden lg:block">
            <div className="sticky top-4 space-y-4">
              
              {/* Stats Panel */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <Icons.barChart className="h-4 w-4 text-slate-400" />
                  {t('stats.title')}
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-green-50 dark:bg-green-900/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-green-600 dark:text-green-400">{completedBriefs}</p>
                    <p className="text-xs text-green-700 dark:text-green-300">{t('stats.completed')}</p>
                  </div>
                  <div className="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{processingBriefs}</p>
                    <p className="text-xs text-blue-700 dark:text-blue-300">{t('stats.researching')}</p>
                  </div>
                </div>
              </div>

              {/* New Research Form - Using Extracted Component */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                  <Icons.search className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                  {t('form.title')}
                </h3>
                
                <ResearchForm 
                  onSuccess={handleResearchSuccess}
                  isSheet={false}
                />
              </div>

              {/* How it works Panel */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-gradient-to-br from-indigo-50 to-blue-50 dark:from-indigo-950 dark:to-blue-950 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <Icons.sparkles className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                  {t('howItWorks.title')}
                </h3>
                <div className="space-y-3">
                  <div className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center flex-shrink-0 font-bold">1</div>
                    <div>
                      <p className="text-sm font-medium text-slate-800 dark:text-slate-100">{t('howItWorks.step1')}</p>
                      <p className="text-xs text-slate-600 dark:text-slate-400">{t('howItWorks.step1Desc')}</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center flex-shrink-0 font-bold">2</div>
                    <div>
                      <p className="text-sm font-medium text-slate-800 dark:text-slate-100">{t('howItWorks.step2')}</p>
                      <p className="text-xs text-slate-600 dark:text-slate-400">{t('howItWorks.step2Desc')}</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-green-600 text-white text-xs flex items-center justify-center flex-shrink-0 font-bold">3</div>
                    <div>
                      <p className="text-sm font-medium text-slate-800 dark:text-slate-100">{t('howItWorks.step3')}</p>
                      <p className="text-xs text-slate-600 dark:text-slate-400">{t('howItWorks.step3Desc')}</p>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>

        {/* Mobile: Floating New Research Button */}
        <div className="lg:hidden fixed bottom-6 right-6">
          <Button 
            className="rounded-full h-14 w-14 shadow-lg bg-blue-600 hover:bg-blue-700"
            onClick={() => {
              // Scroll to top where form is visible on mobile
              window.scrollTo({ top: 0, behavior: 'smooth' })
            }}
          >
            <Icons.plus className="h-6 w-6" />
          </Button>
        </div>

        <Toaster />
      </div>
    </DashboardLayout>
  )
}
