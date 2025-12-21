'use client'

import { useState, useEffect } from 'react'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useRouter, useParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { Toaster } from '@/components/ui/toaster'
import { DashboardLayout } from '@/components/layout/dashboard-layout'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { MarkdownEditor } from '@/components/markdown-editor'
import { useTranslations } from 'next-intl'
import { api } from '@/lib/api'
import { exportAsMarkdown, exportAsPdf, exportAsDocx } from '@/lib/export-utils'
import type { User } from '@supabase/supabase-js'
import { useAutopilot } from '@/components/autopilot/AutopilotProvider'

interface MeetingPrep {
  id: string
  prospect_id?: string
  prospect_company_name: string
  meeting_type: string
  status: string
  custom_notes?: string
  brief_content?: string
  talking_points?: Array<{ category: string; points: string[] }>
  questions?: string[]
  strategy?: string
  pdf_url?: string
  created_at: string
  completed_at?: string
  error_message?: string
  contact_ids?: string[]
  deal_id?: string
}

interface LinkedDeal {
  id: string
  name: string
  prospect_id: string
  is_active: boolean
}

interface ProfileStatus {
  hasSalesProfile: boolean
  hasCompanyProfile: boolean
}

interface ResearchBrief {
  id: string
  company_name: string
  status: string
  completed_at?: string
}

interface ProspectContact {
  id: string
  name: string
  role?: string
  linkedin_url?: string
  communication_style?: string
  decision_authority?: string
}

export default function PreparationDetailPage() {
  const router = useRouter()
  const params = useParams()
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const t = useTranslations('preparation')
  const tCommon = useTranslations('common')
  const { recordPrepViewed } = useAutopilot()
  
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [prep, setPrep] = useState<MeetingPrep | null>(null)
  const [profileStatus, setProfileStatus] = useState<ProfileStatus>({ hasSalesProfile: false, hasCompanyProfile: false })
  const [researchBrief, setResearchBrief] = useState<ResearchBrief | null>(null)
  const [linkedContacts, setLinkedContacts] = useState<ProspectContact[]>([])
  const [linkedDeal, setLinkedDeal] = useState<LinkedDeal | null>(null)
  const [prepViewedTracked, setPrepViewedTracked] = useState(false)
  
  // Edit brief states
  const [isEditing, setIsEditing] = useState(false)
  const [editedContent, setEditedContent] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  
  // Export states
  const [isExporting, setIsExporting] = useState(false)
  
  // Track prep viewed for Autopilot
  useEffect(() => {
    const prepId = params.id as string
    if (prep && prep.status === 'completed' && !prepViewedTracked) {
      const startTime = Date.now()
      
      // Track on unmount or after 30 seconds
      const timeout = setTimeout(() => {
        recordPrepViewed({
          preparation_id: prepId,
          view_duration_seconds: 30,
          scroll_depth: 0.5,
        })
        setPrepViewedTracked(true)
      }, 30000)
      
      return () => {
        clearTimeout(timeout)
        // Track view duration on unmount
        const duration = Math.floor((Date.now() - startTime) / 1000)
        if (duration >= 5 && !prepViewedTracked) {
          recordPrepViewed({
            preparation_id: prepId,
            view_duration_seconds: duration,
            scroll_depth: 0.5,
          })
        }
      }
    }
  }, [prep, prepViewedTracked, params.id, recordPrepViewed])

  useEffect(() => {
    const getUser = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      setUser(user)
      if (user) {
        fetchPrep()
        fetchProfileStatus()
      } else {
        router.push('/login')
      }
    }
    getUser()
  }, [supabase, params.id])

  const fetchProfileStatus = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) return

      const [salesRes, companyRes] = await Promise.all([
        api.get<{ full_name?: string }>('/api/v1/profile/sales'),
        api.get<{ company_name?: string }>('/api/v1/profile/company')
      ])

      setProfileStatus({
        hasSalesProfile: !salesRes.error && !!salesRes.data?.full_name,
        hasCompanyProfile: !companyRes.error && !!companyRes.data?.company_name
      })
    } catch (error) {
      console.error('Failed to fetch profile status:', error)
    }
  }

  const fetchPrep = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) return

      const { data, error } = await api.get<MeetingPrep>(`/api/v1/prep/${params.id}`)

      if (!error && data) {
        setPrep(data)
        
        // Try to find the research brief for this company
        if (data.prospect_company_name) {
          fetchResearchBrief(data.prospect_company_name)
        }
        
        // Fetch linked contacts
        if (data.contact_ids && data.contact_ids.length > 0) {
          fetchLinkedContacts(data.contact_ids)
        }
        
        // Fetch linked deal
        if (data.deal_id) {
          fetchLinkedDeal(data.deal_id)
        }
      } else {
        toast({
          variant: "destructive",
          title: t('toast.failed'),
          description: t('toast.failedDesc'),
        })
        router.push('/dashboard/preparation')
      }
    } catch (error) {
      console.error('Failed to fetch prep:', error)
      toast({
        variant: "destructive",
        title: t('toast.failed'),
        description: t('toast.failedDesc'),
      })
    } finally {
      setLoading(false)
    }
  }

  const fetchResearchBrief = async (companyName: string) => {
    try {
      const { data, error } = await api.get<{ briefs: Array<{ company_name: string; status: string; id: string }> }>('/api/v1/research/briefs')

      if (!error && data) {
        const brief = data.briefs?.find((b) => 
          b.company_name.toLowerCase() === companyName.toLowerCase() && b.status === 'completed'
        )
        if (brief) {
          setResearchBrief(brief)
        }
      }
    } catch (error) {
      console.error('Failed to fetch research brief:', error)
    }
  }

  const fetchLinkedContacts = async (contactIds: string[]) => {
    if (!contactIds || contactIds.length === 0) return
    
    try {
      const { data, error } = await api.get<{ contacts: ProspectContact[]; count: number }>(`/api/v1/contacts?ids=${contactIds.join(',')}`)

      if (!error && data) {
        setLinkedContacts(data.contacts || [])
      }
    } catch (error) {
      console.error('Failed to fetch linked contacts:', error)
    }
  }

  const fetchLinkedDeal = async (dealId: string) => {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) return

      const { data, error } = await supabase
        .from('deals')
        .select('id, name, prospect_id, is_active')
        .eq('id', dealId)
        .single()

      if (!error && data) {
        setLinkedDeal(data)
      }
    } catch (error) {
      console.error('Failed to fetch linked deal:', error)
    }
  }

  const handleStartFollowup = () => {
    if (prep) {
      sessionStorage.setItem('followupForCompany', prep.prospect_company_name)
    }
    router.push('/dashboard/followup')
  }

  // Start editing the brief
  const handleStartEdit = () => {
    if (prep?.brief_content) {
      setEditedContent(prep.brief_content)
      setIsEditing(true)
    }
  }

  // Cancel editing
  const handleCancelEdit = () => {
    setIsEditing(false)
    setEditedContent('')
  }

  // Save edited brief
  const handleSaveBrief = async () => {
    if (!prep || !editedContent.trim()) return
    
    setIsSaving(true)
    try {
      const { data, error } = await api.patch<MeetingPrep>(
        `/api/v1/prep/${prep.id}`,
        { brief_content: editedContent }
      )
      
      if (error) {
        toast({
          title: t('brief.saveFailed'),
          description: t('brief.saveFailedDesc'),
          variant: 'destructive'
        })
        return
      }
      
      // Update local state
      setPrep({ ...prep, brief_content: editedContent })
      setIsEditing(false)
      setEditedContent('')
      
      toast({
        title: t('brief.saved'),
        description: t('brief.savedDesc')
      })
    } catch (err) {
      console.error('Error saving brief:', err)
      toast({
        title: t('brief.saveFailed'),
        description: t('brief.saveFailedDesc'),
        variant: 'destructive'
      })
    } finally {
      setIsSaving(false)
    }
  }

  // Export handlers
  const handleExportMd = () => {
    if (!prep?.brief_content) return
    exportAsMarkdown(prep.brief_content, prep.prospect_company_name)
    toast({
      title: t('brief.copied'),
      description: tCommon('export.markdownDownloaded'),
    })
  }

  const handleExportPdf = async () => {
    if (!prep?.brief_content) return
    setIsExporting(true)
    try {
      await exportAsPdf(prep.brief_content, prep.prospect_company_name, `${prep.prospect_company_name} - Meeting Prep`)
      toast({
        title: t('brief.copied'),
        description: tCommon('export.pdfDownloaded'),
      })
    } catch (error) {
      console.error('PDF export failed:', error)
      toast({
        variant: 'destructive',
        title: t('brief.saveFailed'),
        description: tCommon('export.pdfFailed'),
      })
    } finally {
      setIsExporting(false)
    }
  }

  const handleExportDocx = async () => {
    if (!prep?.brief_content) return
    setIsExporting(true)
    try {
      await exportAsDocx(prep.brief_content, prep.prospect_company_name, `${prep.prospect_company_name} - Meeting Prep`)
      toast({
        title: t('brief.copied'),
        description: tCommon('export.wordDownloaded'),
      })
    } catch (error) {
      console.error('DOCX export failed:', error)
      toast({
        variant: 'destructive',
        title: t('brief.saveFailed'),
        description: tCommon('export.wordFailed'),
      })
    } finally {
      setIsExporting(false)
    }
  }

  const getMeetingTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      discovery: '🔍 Discovery Call',
      demo: '🖥️ Product Demo',
      closing: '🤝 Closing Call',
      follow_up: '📞 Follow-up Meeting',
      other: '📋 Anders'
    }
    return labels[type] || type
  }

  const getMeetingTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      discovery: '🔍',
      demo: '🖥️',
      closing: '🤝',
      follow_up: '📞',
      other: '📋'
    }
    return icons[type] || '📋'
  }

  if (loading) {
    return (
      <DashboardLayout user={user}>
        <div className="flex items-center justify-center h-full">
          <div className="text-center space-y-4">
            <Icons.spinner className="h-8 w-8 animate-spin text-green-600 mx-auto" />
            <p className="text-slate-500 dark:text-slate-400">{t('loading')}</p>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  if (!prep) {
    return null
  }

  return (
    <DashboardLayout user={user}>
      <>
        <div className="p-4 lg:p-6">
          {/* Page Header */}
          <div className="flex items-center gap-4 mb-6">
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push('/dashboard/preparation')}
            >
              <Icons.arrowLeft className="h-4 w-4 mr-2" />
              Terug
            </Button>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{prep.prospect_company_name}</h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {getMeetingTypeLabel(prep.meeting_type)} • {new Date(prep.completed_at || prep.created_at).toLocaleDateString('nl-NL')}
              </p>
            </div>
          </div>

          {/* Two Column Layout */}
          <div className="flex gap-6">
            {/* Left Column - Brief Content (scrollable) */}
            <div className="flex-1 min-w-0">
              {prep.status === 'completed' && prep.brief_content ? (
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 lg:p-8 shadow-sm">
                  {/* Action buttons */}
                  <div className="flex justify-end gap-2 mb-4">
                    {isEditing ? (
                      <>
                        <Button 
                          variant="outline" 
                          size="sm" 
                          onClick={handleCancelEdit}
                          disabled={isSaving}
                        >
                          <Icons.x className="h-4 w-4 mr-2" />
                          {t('brief.cancel')}
                        </Button>
                        <Button 
                          size="sm" 
                          onClick={handleSaveBrief}
                          disabled={isSaving}
                        >
                          {isSaving ? (
                            <>
                              <Icons.spinner className="h-4 w-4 mr-2 animate-spin" />
                              {t('brief.saving')}
                            </>
                          ) : (
                            <>
                              <Icons.check className="h-4 w-4 mr-2" />
                              {t('brief.save')}
                            </>
                          )}
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button 
                          variant="outline" 
                          size="sm" 
                          onClick={handleStartEdit}
                        >
                          <Icons.edit className="h-4 w-4 mr-2" />
                          {t('brief.edit')}
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => {
                          navigator.clipboard.writeText(prep.brief_content || '')
                          toast({
                            title: t('brief.copied'),
                            description: t('brief.copied'),
                          })
                        }}>
                          <Icons.copy className="h-4 w-4 mr-2" />
                          {t('brief.copy')}
                        </Button>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="outline" size="sm" disabled={isExporting}>
                              {isExporting ? (
                                <Icons.spinner className="h-4 w-4 mr-2 animate-spin" />
                              ) : (
                                <Icons.download className="h-4 w-4 mr-2" />
                              )}
                              {t('brief.export')}
                              <Icons.chevronDown className="h-3 w-3 ml-1" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={handleExportPdf}>
                              <Icons.fileText className="h-4 w-4 mr-2" />
                              {t('brief.exportPdf')}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={handleExportDocx}>
                              <Icons.fileText className="h-4 w-4 mr-2" />
                              {t('brief.exportDocx')}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={handleExportMd}>
                              <Icons.fileText className="h-4 w-4 mr-2" />
                              {t('brief.exportMd')}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </>
                    )}
                  </div>
                  
                  {isEditing ? (
                    <MarkdownEditor
                      value={editedContent}
                      onChange={setEditedContent}
                      placeholder={t('brief.edit')}
                      disabled={isSaving}
                    />
                  ) : (
                    <div className="prose prose-slate dark:prose-invert max-w-none prose-headings:scroll-mt-20">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          h1: ({ node, ...props }) => <h1 className="text-2xl font-bold mb-4 text-slate-900 dark:text-white" {...props} />,
                          h2: ({ node, ...props }) => <h2 className="text-xl font-bold mt-8 mb-4 pb-2 border-b border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white" {...props} />,
                          h3: ({ node, ...props }) => <h3 className="text-lg font-semibold mt-6 mb-3 text-slate-900 dark:text-white" {...props} />,
                          p: ({ node, ...props }) => <p className="mb-4 leading-relaxed text-slate-700 dark:text-slate-300" {...props} />,
                          ul: ({ node, ...props }) => <ul className="list-disc list-inside mb-4 space-y-2" {...props} />,
                          ol: ({ node, ...props }) => <ol className="list-decimal list-inside mb-4 space-y-2" {...props} />,
                          li: ({ node, ...props }) => <li className="ml-4 text-slate-700 dark:text-slate-300" {...props} />,
                          strong: ({ node, ...props }) => <strong className="font-semibold text-slate-900 dark:text-white" {...props} />,
                          table: ({ node, ...props }) => (
                            <div className="overflow-x-auto my-6 rounded-lg border border-slate-200 dark:border-slate-700">
                              <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700" {...props} />
                            </div>
                          ),
                          thead: ({ node, ...props }) => <thead className="bg-slate-50 dark:bg-slate-800" {...props} />,
                          tbody: ({ node, ...props }) => <tbody className="divide-y divide-slate-200 dark:divide-slate-700 bg-white dark:bg-slate-900" {...props} />,
                          tr: ({ node, ...props }) => <tr className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors" {...props} />,
                          th: ({ node, ...props }) => <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider whitespace-nowrap" {...props} />,
                          td: ({ node, ...props }) => <td className="px-4 py-3 text-sm text-slate-700 dark:text-slate-300" {...props} />,
                          a: ({ node, href, children, ...props }) => (
                            <a 
                              href={href} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 underline"
                              {...props}
                            >
                              {children}
                            </a>
                          ),
                        }}
                      >
                        {prep.brief_content}
                      </ReactMarkdown>
                    </div>
                  )}

                  {prep.questions && prep.questions.length > 0 && (
                    <div className="mt-8 pt-6 border-t border-slate-200 dark:border-slate-700">
                      <h3 className="font-bold text-lg mb-4 flex items-center gap-2 text-slate-900 dark:text-white">
                        <Icons.message className="h-5 w-5 text-green-600 dark:text-green-400" />
                        {t('detail.discoveryQuestions')}
                      </h3>
                      <div className="space-y-3">
                        {prep.questions.map((q, i) => (
                          <div key={i} className="flex items-start gap-3 p-3 bg-green-50 dark:bg-green-900/30 rounded-lg">
                            <span className="font-bold text-green-600 dark:text-green-400 min-w-[24px]">{i + 1}.</span>
                            <span className="text-slate-700 dark:text-slate-300">{q}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : prep.status === 'failed' ? (
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-8 shadow-sm text-center">
                  <Icons.alertCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
                  <h3 className="font-bold text-lg mb-2 text-slate-900 dark:text-white">{t('toast.failed')}</h3>
                  <p className="text-slate-500 dark:text-slate-400 mb-4">{prep.error_message || t('toast.failedDesc')}</p>
                  <Button onClick={() => router.push('/dashboard/preparation')}>
                    {tCommon('tryAgain')}
                  </Button>
                </div>
              ) : (
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-8 shadow-sm text-center">
                  <Icons.spinner className="h-16 w-16 text-green-600 mx-auto mb-4 animate-spin" />
                  <h3 className="font-bold text-lg mb-2 text-slate-900 dark:text-white">{t('form.generating')}</h3>
                  <p className="text-slate-500 dark:text-slate-400">{t('toast.startedDesc')}</p>
                </div>
              )}
            </div>

            {/* Right Column - Sticky Sidebar */}
            <div className="w-80 flex-shrink-0 hidden lg:block">
              <div className="sticky top-4 space-y-4">
                
                {/* Meeting Type Badge */}
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                  <div className="flex items-center gap-3">
                    <span className="text-3xl">{getMeetingTypeIcon(prep.meeting_type)}</span>
                    <div>
                      <p className="font-semibold text-slate-900 dark:text-white">{getMeetingTypeLabel(prep.meeting_type).replace(/^[^\s]+\s/, '')}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {new Date(prep.completed_at || prep.created_at).toLocaleDateString('nl-NL', {
                          weekday: 'long',
                          day: 'numeric',
                          month: 'long'
                        })}
                      </p>
                    </div>
                  </div>
                </div>

                {/* AI Context Panel */}
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950 dark:to-emerald-950 p-4 shadow-sm">
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                    <Icons.sparkles className="h-4 w-4 text-green-600 dark:text-green-400" />
                    {t('context.title')}
                  </h3>
                  <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
                    {t('context.description')}
                  </p>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-sm">
                      {profileStatus.hasSalesProfile ? (
                        <Icons.check className="h-4 w-4 text-green-600 dark:text-green-400" />
                      ) : (
                        <Icons.circle className="h-4 w-4 text-slate-300 dark:text-slate-600" />
                      )}
                      <span className={profileStatus.hasSalesProfile ? 'text-slate-700 dark:text-slate-200' : 'text-slate-400 dark:text-slate-500'}>
                        {t('context.salesProfile')}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      {profileStatus.hasCompanyProfile ? (
                        <Icons.check className="h-4 w-4 text-green-600 dark:text-green-400" />
                      ) : (
                        <Icons.circle className="h-4 w-4 text-slate-300 dark:text-slate-600" />
                      )}
                      <span className={profileStatus.hasCompanyProfile ? 'text-slate-700 dark:text-slate-200' : 'text-slate-400 dark:text-slate-500'}>
                        {t('context.companyProfile')}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      {researchBrief ? (
                        <Icons.check className="h-4 w-4 text-green-600 dark:text-green-400" />
                      ) : (
                        <Icons.circle className="h-4 w-4 text-slate-300 dark:text-slate-600" />
                      )}
                      <span className={researchBrief ? 'text-slate-700 dark:text-slate-200' : 'text-slate-400 dark:text-slate-500'}>
                        {t('detail.researchBrief')}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <Icons.check className="h-4 w-4 text-green-600 dark:text-green-400" />
                      <span className="text-slate-700 dark:text-slate-200">{t('detail.meetingContext')}</span>
                    </div>
                  </div>
                </div>

                {/* Research Link */}
                {researchBrief && (
                  <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                    <h3 className="font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                      <Icons.search className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                      {t('detail.linkedResearch')}
                    </h3>
                    <button
                      onClick={() => router.push(`/dashboard/research/${researchBrief.id}`)}
                      className="w-full p-3 bg-blue-50 dark:bg-blue-900/30 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors text-left group"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-sm text-blue-900 dark:text-blue-100">{researchBrief.company_name}</p>
                          <p className="text-xs text-blue-600 dark:text-blue-400">
                            {researchBrief.completed_at ? new Date(researchBrief.completed_at).toLocaleDateString('nl-NL') : '-'}
                          </p>
                        </div>
                        <Icons.chevronRight className="h-4 w-4 text-blue-600 dark:text-blue-400 group-hover:translate-x-1 transition-transform" />
                      </div>
                    </button>
                  </div>
                )}

                {/* Linked Deal */}
                {linkedDeal && (
                  <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                    <h3 className="font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                      <Icons.target className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                      {t('detail.linkedDeal')}
                    </h3>
                    <button
                      onClick={() => router.push(`/dashboard/prospects/${linkedDeal.prospect_id}/deals/${linkedDeal.id}`)}
                      className="w-full p-3 bg-indigo-50 dark:bg-indigo-900/30 rounded-lg hover:bg-indigo-100 dark:hover:bg-indigo-900/50 transition-colors text-left group"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-sm text-indigo-900 dark:text-indigo-100">{linkedDeal.name}</p>
                          <p className="text-xs text-indigo-600 dark:text-indigo-400">
                            {linkedDeal.is_active ? '✅ Active' : '📁 Archived'}
                          </p>
                        </div>
                        <Icons.chevronRight className="h-4 w-4 text-indigo-600 dark:text-indigo-400 group-hover:translate-x-1 transition-transform" />
                      </div>
                    </button>
                  </div>
                )}

                {/* Linked Contacts */}
                {linkedContacts.length > 0 && (
                  <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                    <h3 className="font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                      <Icons.user className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                      {t('detail.linkedContact')}
                    </h3>
                    <div className="space-y-2">
                      {linkedContacts.map((contact) => (
                        <button
                          key={contact.id}
                          onClick={() => researchBrief && router.push(`/dashboard/research/${researchBrief.id}#contacts`)}
                          className="w-full p-3 bg-purple-50 dark:bg-purple-900/30 rounded-lg hover:bg-purple-100 dark:hover:bg-purple-900/50 transition-colors text-left group"
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="font-medium text-sm text-purple-900 dark:text-purple-100">{contact.name}</p>
                              {contact.role && (
                                <p className="text-xs text-purple-600 dark:text-purple-400">{contact.role}</p>
                              )}
                              {contact.communication_style && (
                                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                                  💬 {contact.communication_style}
                                </p>
                              )}
                              {contact.decision_authority && (
                                <p className="text-xs text-slate-500 dark:text-slate-400">
                                  🎯 {contact.decision_authority}
                                </p>
                              )}
                            </div>
                            <Icons.chevronRight className="h-4 w-4 text-purple-600 dark:text-purple-400 group-hover:translate-x-1 transition-transform" />
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Custom Notes */}
                {prep.custom_notes && (
                  <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                    <h3 className="font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                      <Icons.fileText className="h-4 w-4 text-slate-600 dark:text-slate-400" />
                      {t('detail.yourNotes')}
                    </h3>
                    <p className="text-sm text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-800 p-3 rounded-lg">
                      {prep.custom_notes}
                    </p>
                  </div>
                )}

                {/* CTA Panel - Follow-up */}
                <div className="rounded-xl border-2 border-orange-200 dark:border-orange-800 bg-gradient-to-br from-orange-50 to-amber-50 dark:from-orange-950 dark:to-amber-950 p-4 shadow-sm">
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                    <Icons.arrowRight className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                    {t('nextStep.title')}
                  </h3>
                  <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
                    {t('nextStep.description')}
                  </p>
                  <Button 
                    className="w-full bg-orange-600 hover:bg-orange-700"
                    onClick={handleStartFollowup}
                  >
                    <Icons.mic className="h-4 w-4 mr-2" />
                    {t('nextStep.button')}
                  </Button>
                </div>

                {/* Quick Actions */}
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-3 text-sm">{t('detail.quickActions')}</h3>
                  <div className="space-y-2">
                    {prep.pdf_url && (
                      <Button variant="outline" size="sm" className="w-full justify-start" asChild>
                        <a href={prep.pdf_url} target="_blank" rel="noopener noreferrer">
                          <Icons.download className="h-4 w-4 mr-2" />
                          {tCommon('download')}
                        </a>
                      </Button>
                    )}
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="w-full justify-start"
                      onClick={() => {
                        navigator.clipboard.writeText(prep.brief_content || '')
                        toast({ title: tCommon('copied') })
                      }}
                    >
                      <Icons.copy className="h-4 w-4 mr-2" />
                      {t('brief.copyAll')}
                    </Button>
                    {researchBrief && (
                      <Button 
                        variant="outline" 
                        size="sm" 
                        className="w-full justify-start"
                        onClick={() => router.push(`/dashboard/research/${researchBrief.id}`)}
                      >
                        <Icons.search className="h-4 w-4 mr-2" />
                        {t('brief.viewResearch')}
                      </Button>
                    )}
                  </div>
                </div>

              </div>
            </div>
          </div>

          {/* Mobile: Floating Action Button */}
          <div className="lg:hidden fixed bottom-6 right-6">
            <Button 
              className="rounded-full h-14 w-14 shadow-lg bg-orange-600 hover:bg-orange-700"
              onClick={handleStartFollowup}
            >
              <Icons.mic className="h-6 w-6" />
            </Button>
          </div>

        </div>
      
        <Toaster />
      </>
    </DashboardLayout>
  )
}
