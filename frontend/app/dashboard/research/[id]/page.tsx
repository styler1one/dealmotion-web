'use client'

import { useState, useEffect, useCallback } from 'react'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useRouter, useParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { useToast } from '@/components/ui/use-toast'
import { Toaster } from '@/components/ui/toaster'
import { Badge } from '@/components/ui/badge'
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
import { ContactSearchModal } from '@/components/contacts'
import { useConfirmDialog } from '@/components/confirm-dialog'
import type { User } from '@supabase/supabase-js'

interface ResearchBrief {
  id: string
  company_name: string
  brief_content: string
  pdf_url?: string
  created_at: string
  completed_at: string
}

interface Contact {
  id: string
  prospect_id: string
  name: string
  role?: string
  email?: string
  linkedin_url?: string
  communication_style?: string
  decision_authority?: string
  probable_drivers?: string
  profile_brief?: string
  opening_suggestions?: string[]
  questions_to_ask?: string[]
  topics_to_avoid?: string[]
  is_primary: boolean
  analyzed_at?: string
  created_at: string
}

interface ProfileStatus {
  hasSalesProfile: boolean
  hasCompanyProfile: boolean
}

export default function ResearchBriefPage() {
  const router = useRouter()
  const params = useParams()
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const { confirm } = useConfirmDialog()
  const t = useTranslations('research')
  const tCommon = useTranslations('common')
  
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [brief, setBrief] = useState<ResearchBrief | null>(null)
  const [profileStatus, setProfileStatus] = useState<ProfileStatus>({ hasSalesProfile: false, hasCompanyProfile: false })
  
  // Contact states
  const [contacts, setContacts] = useState<Contact[]>([])
  const [showContactSearchModal, setShowContactSearchModal] = useState(false)
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null)
  const [contactsLoading, setContactsLoading] = useState(false)
  const [analyzingContactIds, setAnalyzingContactIds] = useState<Set<string>>(new Set())
  
  // Edit brief states
  const [isEditing, setIsEditing] = useState(false)
  const [editedContent, setEditedContent] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  
  // Edit contact states
  const [isEditingContact, setIsEditingContact] = useState(false)
  const [editedContactBrief, setEditedContactBrief] = useState('')
  const [isSavingContact, setIsSavingContact] = useState(false)
  
  // Export states
  const [isExporting, setIsExporting] = useState(false)

  useEffect(() => {
    const getUser = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      setUser(user)
      if (user) {
        fetchBrief()
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

  const fetchBrief = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) return

      const { data, error } = await api.get<ResearchBrief>(`/api/v1/research/${params.id}/brief`)

      if (!error && data) {
        setBrief(data)
      } else {
        toast({
          variant: "destructive",
          title: t('toast.loadFailed'),
          description: t('toast.loadFailedDesc'),
        })
        router.push('/dashboard/research')
      }
    } catch (error) {
      console.error('Failed to fetch brief:', error)
      toast({
        variant: "destructive",
        title: t('contacts.searchFailed'),
        description: t('contacts.searchFailedDesc'),
      })
    } finally {
      setLoading(false)
    }
  }

  // Fetch contacts for this research
  const fetchContacts = useCallback(async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) return

      setContactsLoading(true)
      const { data, error } = await api.get<{ contacts: Contact[] }>(`/api/v1/research/${params.id}/contacts`)

      if (!error && data) {
        setContacts(data.contacts || [])
      }
    } catch (error) {
      console.error('Failed to fetch contacts:', error)
    } finally {
      setContactsLoading(false)
    }
  }, [supabase, params.id])

  // Load contacts when brief is loaded
  useEffect(() => {
    if (brief) {
      fetchContacts()
    }
  }, [brief, fetchContacts])

  // Handle contact added from modal
  const handleContactAdded = (contact: Contact) => {
    setContacts(prev => [...prev, contact])
    setAnalyzingContactIds(prev => new Set([...prev, contact.id]))
    
    // Smart polling for analysis completion
    const pollForAnalysis = async (contactId: string, attempts: number) => {
      if (attempts > 12) {
        setAnalyzingContactIds(prev => {
          const next = new Set(prev)
          next.delete(contactId)
          return next
        })
        return
      }
      
      await fetchContacts()
      
      const updatedContact = contacts.find(c => c.id === contactId)
      if (updatedContact?.analyzed_at) {
        setAnalyzingContactIds(prev => {
          const next = new Set(prev)
          next.delete(contactId)
          return next
        })
        toast({
          title: t('contacts.analysisComplete'),
          description: t('contacts.analysisCompleteDesc', { name: updatedContact.name }),
        })
        return
      }
      
      setTimeout(() => pollForAnalysis(contactId, attempts + 1), 5000)
    }
    
    // Start polling for analysis
    setTimeout(() => pollForAnalysis(contact.id, 0), 3000)
  }

  // Delete a contact
  const handleDeleteContact = async (contactId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    
    // Show confirmation dialog
    const confirmed = await confirm({
      title: t('contacts.confirmDeleteTitle'),
      description: t('contacts.confirmDeleteDescription'),
      confirmLabel: tCommon('delete'),
      cancelLabel: tCommon('cancel'),
      variant: 'danger',
    })
    if (!confirmed) return
    
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) return

      const { error } = await api.delete(`/api/v1/contacts/${contactId}`)

      if (!error) {
        setContacts(prev => prev.filter(c => c.id !== contactId))
        if (selectedContact?.id === contactId) {
          setSelectedContact(null)
        }
        toast({
          title: t('toast.deleted'),
          description: t('toast.deletedDesc'),
        })
      }
    } catch (error) {
      console.error('Failed to delete contact:', error)
    }
  }

  // Navigate to preparation with this prospect pre-selected
  const handleStartPreparation = () => {
    // Store the company name in sessionStorage for the preparation page to pick up
    if (brief) {
      sessionStorage.setItem('prepareForCompany', brief.company_name)
    }
    router.push('/dashboard/preparation')
  }

  // Start editing the brief
  const handleStartEdit = () => {
    if (brief) {
      setEditedContent(brief.brief_content)
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
    if (!brief || !editedContent.trim()) return
    
    setIsSaving(true)
    try {
      const { data, error } = await api.patch<{ id: string; brief_content: string }>(
        `/api/v1/research/${brief.id}/brief`,
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
      setBrief({ ...brief, brief_content: editedContent })
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
  
  // Save contact analysis
  const handleSaveContactBrief = async () => {
    if (!selectedContact || !editedContactBrief.trim()) return
    
    setIsSavingContact(true)
    try {
      const { data, error } = await api.patch<Contact>(
        `/api/v1/contacts/${selectedContact.id}`,
        { profile_brief: editedContactBrief }
      )
      
      if (error) {
        toast({
          title: t('contacts.saveFailed'),
          description: t('contacts.saveFailedDesc'),
          variant: 'destructive'
        })
        return
      }
      
      // Update local state
      setContacts(contacts.map(c => 
        c.id === selectedContact.id 
          ? { ...c, profile_brief: editedContactBrief }
          : c
      ))
      setSelectedContact({ ...selectedContact, profile_brief: editedContactBrief })
      setIsEditingContact(false)
      setEditedContactBrief('')
      
      toast({
        title: t('contacts.saved'),
        description: t('contacts.savedDesc')
      })
    } catch (err) {
      console.error('Error saving contact:', err)
      toast({
        title: t('contacts.saveFailed'),
        description: t('contacts.saveFailedDesc'),
        variant: 'destructive'
      })
    } finally {
      setIsSavingContact(false)
    }
  }
  
  // Start editing contact
  const handleEditContact = () => {
    if (selectedContact?.profile_brief) {
      setEditedContactBrief(selectedContact.profile_brief)
      setIsEditingContact(true)
    }
  }
  
  // Cancel editing contact
  const handleCancelEditContact = () => {
    setIsEditingContact(false)
    setEditedContactBrief('')
  }

  // Export handlers
  const handleExportMd = () => {
    if (!brief) return
    exportAsMarkdown(brief.brief_content, brief.company_name)
    toast({
      title: t('brief.copied'),
      description: tCommon('export.markdownDownloaded'),
    })
  }

  const handleExportPdf = async () => {
    if (!brief) return
    setIsExporting(true)
    try {
      await exportAsPdf(brief.brief_content, brief.company_name, brief.company_name)
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
    if (!brief) return
    setIsExporting(true)
    try {
      await exportAsDocx(brief.brief_content, brief.company_name, brief.company_name)
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

  // Get badge for decision authority
  const getAuthorityBadge = (authority?: string) => {
    switch (authority) {
      case 'decision_maker':
        return <Badge className="bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-400 text-[10px] px-1.5 py-0 h-4 font-medium">DM</Badge>
      case 'influencer':
        return <Badge className="bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400 text-[10px] px-1.5 py-0 h-4 font-medium">INF</Badge>
      case 'gatekeeper':
        return <Badge className="bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-400 text-[10px] px-1.5 py-0 h-4 font-medium">GK</Badge>
      default:
        return null
    }
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

  if (!brief) {
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
              onClick={() => router.push('/dashboard/research')}
            >
              <Icons.arrowLeft className="h-4 w-4 mr-2" />
              {tCommon('back')}
            </Button>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{brief.company_name}</h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Research Brief • {new Date(brief.completed_at).toLocaleDateString('nl-NL')}
              </p>
            </div>
          </div>

          {/* Two Column Layout */}
          <div className="flex gap-6">
            {/* Left Column - Brief Content (scrollable) */}
            <div className="flex-1 min-w-0">
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 lg:p-8 shadow-sm">
                {/* Action buttons - rechtsboven in de brief */}
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
                        navigator.clipboard.writeText(brief.brief_content)
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
                        code: ({ node, ...props }) => <code className="bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded text-sm" {...props} />,
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
                      {brief.brief_content}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            </div>

            {/* Right Column - Sticky Sidebar */}
            <div className="w-80 flex-shrink-0 hidden lg:block">
              <div className="sticky top-4 space-y-4">
                
                {/* AI Context Panel */}
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-gradient-to-br from-indigo-50 to-blue-50 dark:from-indigo-950 dark:to-blue-950 p-4 shadow-sm">
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                    <Icons.sparkles className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                    {t('context.title')}
                  </h3>
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
                      <Icons.check className="h-4 w-4 text-green-600 dark:text-green-400" />
                      <span className="text-slate-700 dark:text-slate-200">{t('context.researchBrief')}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      {contacts.length > 0 ? (
                        <Icons.check className="h-4 w-4 text-green-600 dark:text-green-400" />
                      ) : (
                        <Icons.circle className="h-4 w-4 text-amber-400" />
                      )}
                      <span className={contacts.length > 0 ? 'text-slate-700 dark:text-slate-200' : 'text-amber-600 dark:text-amber-400'}>
                        {t('context.contacts')} ({contacts.length})
                      </span>
                    </div>
                  </div>
                </div>

                {/* Contacts Panel */}
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                      <Icons.user className="h-4 w-4" />
                      {t('contacts.title')}
                    </h3>
                    <Button 
                      size="sm" 
                      variant="ghost"
                      className="h-7 text-xs"
                      onClick={() => setShowContactSearchModal(true)}
                    >
                      <Icons.plus className="h-3 w-3 mr-1" />
                      {tCommon('add')}
                    </Button>
                  </div>

                  {/* Contacts List (Compact) */}
                  {contactsLoading ? (
                    <div className="text-center py-4 text-slate-500 dark:text-slate-400">
                      <Icons.spinner className="h-5 w-5 animate-spin mx-auto" />
                    </div>
                  ) : contacts.length === 0 ? (
                    <div className="text-center py-4">
                      <Icons.user className="h-8 w-8 mx-auto mb-2 text-slate-300 dark:text-slate-600" />
                      <p className="text-xs text-slate-500 dark:text-slate-400">{t('detail.contactsPanel.noContacts')}</p>
                      <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                        {t('detail.contactsPanel.addForPreparation')}
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {/* Hint voor gebruiker */}
                      <p className="text-xs text-slate-400 dark:text-slate-500 mb-2 flex items-center gap-1">
                        <Icons.info className="h-3 w-3" />
                        Klik voor uitgebreide analyse
                      </p>
                      
                      {contacts.map((contact) => {
                        const isAnalyzing = analyzingContactIds.has(contact.id) || (!contact.analyzed_at && contact.profile_brief === "Analyse wordt uitgevoerd...")
                        const hasAnalysis = contact.analyzed_at && contact.profile_brief
                        
                        return (
                          <div 
                            key={contact.id}
                            className={`p-3 rounded-lg border transition-all ${
                              selectedContact?.id === contact.id 
                                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 shadow-md' 
                                : isAnalyzing
                                  ? 'border-amber-400 dark:border-amber-600 bg-amber-50 dark:bg-amber-900/30'
                                  : hasAnalysis
                                    ? 'border-slate-200 dark:border-slate-700 hover:border-blue-300 dark:hover:border-blue-600 hover:bg-blue-50/50 dark:hover:bg-blue-900/20 cursor-pointer hover:shadow-sm'
                                    : 'border-slate-200 dark:border-slate-700'
                            }`}
                            onClick={() => hasAnalysis && setSelectedContact(selectedContact?.id === contact.id ? null : contact)}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2 min-w-0 flex-1">
                                <div className={`h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                                  isAnalyzing ? 'bg-amber-200 dark:bg-amber-800' : hasAnalysis ? 'bg-blue-100 dark:bg-blue-900' : 'bg-slate-200 dark:bg-slate-700'
                                }`}>
                                  {isAnalyzing ? (
                                    <Icons.spinner className="h-4 w-4 text-amber-600 dark:text-amber-400 animate-spin" />
                                  ) : (
                                    <Icons.user className={`h-4 w-4 ${hasAnalysis ? 'text-blue-600 dark:text-blue-400' : 'text-slate-500 dark:text-slate-400'}`} />
                                  )}
                                </div>
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-1.5">
                                    <span className="font-medium text-sm text-slate-900 dark:text-white truncate">{contact.name}</span>
                                    <span className="flex-shrink-0">{getAuthorityBadge(contact.decision_authority)}</span>
                                  </div>
                                  {contact.role && (
                                    <div className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">{contact.role}</div>
                                  )}
                                </div>
                              </div>
                              
                              <div className="flex items-center gap-1">
                                {/* Bekijk profiel indicator */}
                                {hasAnalysis && (
                                  <div className="flex items-center gap-1 text-blue-600 dark:text-blue-400 mr-1">
                                    <span className="text-xs font-medium hidden sm:inline">{tCommon('view')}</span>
                                    <Icons.chevronRight className="h-4 w-4" />
                                  </div>
                                )}
                                {isAnalyzing && (
                                  <span className="text-xs text-amber-600 dark:text-amber-400 mr-1">Analyseren...</span>
                                )}
                                <Button 
                                  variant="ghost" 
                                  size="sm"
                                  className="h-6 w-6 p-0 text-slate-400 hover:text-red-500 dark:hover:text-red-400"
                                  onClick={(e) => handleDeleteContact(contact.id, e)}
                                >
                                  <Icons.x className="h-3 w-3" />
                                </Button>
                              </div>
                            </div>
                            
                            {/* Preview van de analyse */}
                            {hasAnalysis && contact.communication_style && (
                              <div className="mt-2 pt-2 border-t border-slate-100 dark:border-slate-700">
                                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                                  <span className="inline-flex items-center bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 px-2 py-0.5 rounded-full">{contact.communication_style}</span>
                                  {contact.probable_drivers && (
                                    <span className="inline-flex items-center bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-2 py-0.5 rounded-full truncate max-w-[150px]">{contact.probable_drivers.split(',')[0]?.trim()}</span>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>

                {/* CTA Panel - Conditional based on contacts */}
                {contacts.length === 0 ? (
                  // No contacts yet - prompt to add contact first
                  <div className="rounded-xl border-2 border-amber-200 dark:border-amber-800 bg-gradient-to-br from-amber-50 to-yellow-50 dark:from-amber-950 dark:to-yellow-950 p-4 shadow-sm">
                    <h3 className="font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                      <Icons.user className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                      {t('nextStep.addContact.title')}
                    </h3>
                    <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
                      {t('nextStep.addContact.description')}
                    </p>
                    <Button 
                      className="w-full bg-amber-600 hover:bg-amber-700"
                      onClick={() => setShowContactSearchModal(true)}
                    >
                      <Icons.userPlus className="h-4 w-4 mr-2" />
                      {t('nextStep.addContact.button')}
                    </Button>
                    <p className="text-xs text-amber-700 dark:text-amber-400 mt-2 text-center">
                      {t('nextStep.addContact.hint')}
                    </p>
                  </div>
                ) : (
                  // Has contacts - can proceed to preparation
                  <div className="rounded-xl border-2 border-green-200 dark:border-green-800 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950 dark:to-emerald-950 p-4 shadow-sm">
                    <h3 className="font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                      <Icons.arrowRight className="h-4 w-4 text-green-600 dark:text-green-400" />
                      {t('nextStep.ready.title')}
                    </h3>
                    <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
                      {t('nextStep.ready.description')}
                    </p>
                    <Button 
                      className="w-full bg-green-600 hover:bg-green-700"
                      onClick={handleStartPreparation}
                    >
                      <Icons.fileText className="h-4 w-4 mr-2" />
                      {t('nextStep.ready.button')}
                    </Button>
                    <p className="text-xs text-green-700 dark:text-green-400 mt-2 text-center">
                      {t('nextStep.ready.withContacts', { count: contacts.length })}
                    </p>
                  </div>
                )}

              </div>
            </div>
          </div>

          {/* Mobile: Floating Action Button for Contacts/Preparation */}
          <div className="lg:hidden fixed bottom-6 right-6 flex flex-col gap-2">
            {contacts.length === 0 ? (
              <Button 
                className="rounded-full h-14 w-14 shadow-lg bg-amber-600 hover:bg-amber-700"
                onClick={() => setShowContactSearchModal(true)}
              >
                <Icons.userPlus className="h-6 w-6" />
              </Button>
            ) : (
              <Button 
                className="rounded-full h-14 w-14 shadow-lg bg-green-600 hover:bg-green-700"
                onClick={handleStartPreparation}
              >
                <Icons.arrowRight className="h-6 w-6" />
              </Button>
            )}
          </div>

        </div>

        {/* Contact Detail Modal (when contact is selected) */}
        {selectedContact && selectedContact.analyzed_at && (
          <div 
            className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
            onClick={() => { setSelectedContact(null); setIsEditingContact(false); setEditedContactBrief(''); }}
          >
            <div 
              className="bg-white dark:bg-slate-900 rounded-xl max-w-4xl w-full max-h-[85vh] overflow-y-auto shadow-xl border border-slate-200 dark:border-slate-700"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="sticky top-0 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700 px-6 py-4 flex items-center justify-between z-10">
                <div>
                  <h2 className="text-lg font-bold text-slate-900 dark:text-white">{selectedContact.name}</h2>
                  {selectedContact.role && (
                    <p className="text-sm text-slate-500 dark:text-slate-400">{selectedContact.role}</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {isEditingContact ? (
                    <>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={handleCancelEditContact}
                      >
                        {tCommon('cancel')}
                      </Button>
                      <Button 
                        variant="default"
                        size="sm"
                        onClick={handleSaveContactBrief}
                        disabled={isSavingContact}
                        className="bg-green-600 hover:bg-green-700"
                      >
                        {isSavingContact ? (
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
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={handleEditContact}
                    >
                      <Icons.edit className="h-4 w-4 mr-1" />
                      {t('brief.edit')}
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => { setSelectedContact(null); setIsEditingContact(false); setEditedContactBrief(''); }}>
                    <Icons.x className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <div className="p-6">
                {isEditingContact ? (
                  <MarkdownEditor
                    value={editedContactBrief}
                    onChange={setEditedContactBrief}
                    placeholder={t('contacts.editPlaceholder')}
                    className="min-h-[400px]"
                  />
                ) : (
                  <>
                    {selectedContact.profile_brief && (
                      <div className="prose prose-sm prose-slate dark:prose-invert max-w-none">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            h1: ({ node, ...props }) => <h1 className="text-xl font-bold mb-3 text-slate-900 dark:text-white" {...props} />,
                            h2: ({ node, ...props }) => <h2 className="text-lg font-bold mt-5 mb-3 text-slate-900 dark:text-white border-b border-slate-200 dark:border-slate-700 pb-2" {...props} />,
                            h3: ({ node, ...props }) => <h3 className="text-base font-semibold mt-4 mb-2 text-slate-900 dark:text-white" {...props} />,
                            p: ({ node, ...props }) => <p className="mb-3 text-sm text-slate-700 dark:text-slate-300 leading-relaxed" {...props} />,
                            ul: ({ node, ...props }) => <ul className="list-disc list-inside mb-3 space-y-1.5 text-sm" {...props} />,
                            ol: ({ node, ...props }) => <ol className="list-decimal list-inside mb-3 space-y-1.5 text-sm" {...props} />,
                            li: ({ node, ...props }) => <li className="ml-2 text-slate-700 dark:text-slate-300" {...props} />,
                            strong: ({ node, ...props }) => <strong className="font-semibold text-slate-900 dark:text-white" {...props} />,
                            hr: ({ node, ...props }) => <hr className="my-4 border-slate-200 dark:border-slate-700" {...props} />,
                            table: ({ node, ...props }) => (
                              <div className="overflow-x-auto my-4 rounded-lg border border-slate-200 dark:border-slate-700">
                                <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700 text-sm" {...props} />
                              </div>
                            ),
                            thead: ({ node, ...props }) => <thead className="bg-slate-50 dark:bg-slate-800" {...props} />,
                            tbody: ({ node, ...props }) => <tbody className="divide-y divide-slate-200 dark:divide-slate-700 bg-white dark:bg-slate-900" {...props} />,
                            tr: ({ node, ...props }) => <tr className="hover:bg-slate-50 dark:hover:bg-slate-800/50" {...props} />,
                            th: ({ node, ...props }) => <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider" {...props} />,
                            td: ({ node, ...props }) => <td className="px-4 py-3 text-slate-700 dark:text-slate-300 whitespace-normal" {...props} />,
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
                          {selectedContact.profile_brief}
                        </ReactMarkdown>
                      </div>
                    )}
                    
                    {/* Note: Opening lines and discovery questions are now 
                        generated in the Preparation phase, not here */}
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      
        {/* Contact Search Modal */}
        {brief && (
          <ContactSearchModal
            isOpen={showContactSearchModal}
            onClose={() => setShowContactSearchModal(false)}
            companyName={brief.company_name}
            researchId={params.id as string}
            onContactAdded={handleContactAdded}
          />
        )}

        <Toaster />
      </>
    </DashboardLayout>
  )
}
