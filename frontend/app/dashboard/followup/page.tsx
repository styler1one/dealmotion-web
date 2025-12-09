'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/date-utils'
import { logger } from '@/lib/logger'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { Toaster } from '@/components/ui/toaster'
import { DashboardLayout } from '@/components/layout'
import { useTranslations } from 'next-intl'
import { useSettings } from '@/lib/settings-context'
import { useConfirmDialog } from '@/components/confirm-dialog'
import { FollowupUploadForm } from '@/components/forms'
import type { User } from '@supabase/supabase-js'

interface FollowupItem {
  id: string
  prospect_company_name: string | null
  meeting_subject: string | null
  meeting_date: string | null
  status: string
  executive_summary: string | null
  audio_duration_seconds: number | null
  created_at: string
  completed_at: string | null
}

export default function FollowupPage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const { confirm } = useConfirmDialog()
  const t = useTranslations('followup')
  const tCommon = useTranslations('common')
  const { settings } = useSettings()
  
  const [user, setUser] = useState<User | null>(null)
  const [followups, setFollowups] = useState<FollowupItem[]>([])
  const [loading, setLoading] = useState(true)
  
  // Pre-filled values from navigation
  const [initialProspectCompany, setInitialProspectCompany] = useState('')
  
  const fetchFollowups = useCallback(async () => {
    try {
      const { data, error } = await api.get<FollowupItem[]>('/api/v1/followup/list')
      
      if (!error && data) {
        setFollowups(data)
      }
    } catch (error) {
      logger.error('Error fetching followups', error)
    } finally {
      setLoading(false)
    }
  }, [])

  const followupsRef = useRef<FollowupItem[]>([])
  followupsRef.current = followups

  useEffect(() => {
    // Load user and followups in parallel
    Promise.all([
      supabase.auth.getUser().then(({ data: { user } }) => setUser(user)),
      fetchFollowups()
    ])

    // Check for pre-selected company from Preparation page
    const followupFor = sessionStorage.getItem('followupForCompany')
    if (followupFor) {
      setInitialProspectCompany(followupFor)
      sessionStorage.removeItem('followupForCompany')
    }
  }, [fetchFollowups])

  useEffect(() => {
    const interval = setInterval(() => {
      const hasProcessing = followupsRef.current.some(f => 
        ['uploading', 'transcribing', 'summarizing'].includes(f.status)
      )
      if (hasProcessing) {
        fetchFollowups()
      }
    }, 5000)
    
    return () => clearInterval(interval)
  }, [fetchFollowups])

  const handleUploadSuccess = () => {
    setInitialProspectCompany('')
    fetchFollowups()
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
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
      const { error } = await api.delete(`/api/v1/followup/${id}`)

      if (!error) {
        toast({ title: t('toast.deleted') })
        fetchFollowups()
      } else {
        throw new Error('Delete failed')
      }
    } catch (error) {
      toast({
        title: t('toast.failed'),
        variant: 'destructive'
      })
    }
  }

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-'
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const completedFollowups = followups.filter(f => f.status === 'completed').length
  const processingFollowups = followups.filter(f => ['uploading', 'transcribing', 'summarizing'].includes(f.status)).length

  if (loading) {
    return (
      <DashboardLayout user={user}>
        <div className="flex items-center justify-center h-full">
          <div className="text-center space-y-4">
            <Icons.spinner className="h-8 w-8 animate-spin text-orange-600 mx-auto" />
            <p className="text-slate-500 dark:text-slate-400">{t('loading')}</p>
          </div>
        </div>
      </DashboardLayout>
    )
  }

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
          
          {/* Left Column - Follow-ups History */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                <Icons.mail className="h-5 w-5 text-slate-400" />
                {t('history.title')}
                <span className="text-sm font-normal text-slate-400">({followups.length})</span>
              </h2>
              <Button variant="ghost" size="sm" onClick={fetchFollowups}>
                <Icons.refresh className="h-4 w-4" />
              </Button>
            </div>

            {followups.length === 0 ? (
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-12 text-center">
                <Icons.mic className="h-16 w-16 text-slate-200 dark:text-slate-700 mx-auto mb-4" />
                <h3 className="font-semibold text-slate-700 dark:text-slate-200 mb-2">{t('history.empty')}</h3>
                <p className="text-slate-500 dark:text-slate-400 text-sm mb-4">
                  {t('history.emptyDesc')}
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {followups.map((followup) => (
                  <div
                    key={followup.id}
                    className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 hover:shadow-md dark:hover:shadow-slate-800/50 transition-all cursor-pointer group"
                    onClick={() => router.push(`/dashboard/followup/${followup.id}`)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-semibold text-slate-900 dark:text-white truncate">
                            {followup.prospect_company_name || followup.meeting_subject || 'Meeting'}
                          </h4>
                          
                          {followup.status === 'completed' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 dark:bg-green-900/50 text-green-700 dark:text-green-400 flex-shrink-0">
                              <Icons.check className="h-3 w-3" />
                              {t('stats.completed')}
                            </span>
                          )}
                          {followup.status === 'transcribing' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-50 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-400 flex-shrink-0">
                              <Icons.spinner className="h-3 w-3 animate-spin" />
                              {t('form.processing')}
                            </span>
                          )}
                          {followup.status === 'summarizing' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-purple-50 dark:bg-purple-900/50 text-purple-700 dark:text-purple-400 flex-shrink-0">
                              <Icons.spinner className="h-3 w-3 animate-spin" />
                              {t('form.processing')}
                            </span>
                          )}
                          {followup.status === 'uploading' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400 flex-shrink-0">
                              <Icons.spinner className="h-3 w-3 animate-spin" />
                              {t('form.processing')}
                            </span>
                          )}
                          {followup.status === 'failed' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 dark:bg-red-900/50 text-red-700 dark:text-red-400 flex-shrink-0">
                              <Icons.alertCircle className="h-3 w-3" />
                              {t('toast.failed')}
                            </span>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                          {followup.meeting_date && (
                            <span>{formatDate(followup.meeting_date, settings.output_language)}</span>
                          )}
                          {followup.audio_duration_seconds && (
                            <span className="flex items-center gap-1">
                              <Icons.clock className="h-3 w-3" />
                              {formatDuration(followup.audio_duration_seconds)}
                            </span>
                          )}
                          <span>{formatDate(followup.created_at, settings.output_language)}</span>
                        </div>

                        {followup.executive_summary && (
                          <p className="text-xs text-slate-500 dark:text-slate-400 mt-2 line-clamp-1">
                            {followup.executive_summary}
                          </p>
                        )}
                      </div>
                      
                      <div className="flex items-center gap-1 ml-4">
                        {followup.status === 'completed' && (
                          <Button
                            variant="default"
                            size="sm"
                            className="h-8 text-xs bg-orange-600 hover:bg-orange-700 opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={(e) => {
                              e.stopPropagation()
                              router.push(`/dashboard/followup/${followup.id}`)
                            }}
                          >
                            <Icons.eye className="h-3 w-3 mr-1" />
                            {tCommon('view')}
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-slate-400 hover:text-red-600 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => handleDelete(followup.id, e)}
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
                    <p className="text-2xl font-bold text-green-600 dark:text-green-400">{completedFollowups}</p>
                    <p className="text-xs text-green-700 dark:text-green-300">{t('stats.completed')}</p>
                  </div>
                  <div className="bg-orange-50 dark:bg-orange-900/30 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">{processingFollowups}</p>
                    <p className="text-xs text-orange-700 dark:text-orange-300">{t('stats.processing')}</p>
                  </div>
                </div>
              </div>

              {/* Upload Form - Using Extracted Component */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <Icons.upload className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                  {t('form.title')}
                </h3>
                
                <FollowupUploadForm 
                  initialProspectCompany={initialProspectCompany}
                  onSuccess={handleUploadSuccess}
                  isSheet={false}
                />
              </div>

              {/* How it works Panel */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-gradient-to-br from-orange-50 to-amber-50 dark:from-orange-950 dark:to-amber-950 p-4 shadow-sm">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <Icons.sparkles className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                  {t('whatYouGet.title')}
                </h3>
                <ul className="space-y-2 text-xs text-slate-700 dark:text-slate-300">
                  <li className="flex items-start gap-2">
                    <Icons.check className="h-4 w-4 text-orange-600 dark:text-orange-400 flex-shrink-0 mt-0.5" />
                    <span>{t('whatYouGet.item1')}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <Icons.check className="h-4 w-4 text-orange-600 dark:text-orange-400 flex-shrink-0 mt-0.5" />
                    <span>{t('whatYouGet.item2')}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <Icons.check className="h-4 w-4 text-orange-600 dark:text-orange-400 flex-shrink-0 mt-0.5" />
                    <span>{t('detail.actionItems')}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <Icons.check className="h-4 w-4 text-orange-600 dark:text-orange-400 flex-shrink-0 mt-0.5" />
                    <span>{t('whatYouGet.item3')}</span>
                  </li>
                </ul>
              </div>

            </div>
          </div>
        </div>

        <Toaster />
      </div>
    </DashboardLayout>
  )
}
