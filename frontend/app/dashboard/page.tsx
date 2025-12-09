'use client'

import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useRouter } from 'next/navigation'
import { useEffect, useState, useMemo } from 'react'
import { Button } from '@/components/ui/button'
import { useToast } from '@/components/ui/use-toast'
import { Icons } from '@/components/icons'
import { DashboardLayout } from '@/components/layout'
import { useTranslations, useLocale } from 'next-intl'
import { api } from '@/lib/api'
import { useBilling } from '@/lib/billing-context'
import { logger } from '@/lib/logger'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { ResearchForm } from '@/components/forms'
import type { User } from '@supabase/supabase-js'
import type { SalesProfile, CompanyProfile, KBFile, ResearchBrief, MeetingPrep, Followup } from '@/types'

// Activity type from backend
interface Activity {
    id: string
    type: 'research_completed' | 'prep_generated' | 'followup_created' | 'contact_added'
    company: string
    contact_name?: string
    timestamp: string
    icon: string
    color: string
}

// Helper function for relative time (locale-aware)
function getRelativeTime(dateString: string, locale: string): string {
    const date = new Date(dateString)
    const now = new Date()
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000)
    
    // Use Intl.RelativeTimeFormat for proper localization
    const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })
    
    if (diffInSeconds < 60) return rtf.format(0, 'second')
    if (diffInSeconds < 3600) return rtf.format(-Math.floor(diffInSeconds / 60), 'minute')
    if (diffInSeconds < 86400) return rtf.format(-Math.floor(diffInSeconds / 3600), 'hour')
    if (diffInSeconds < 604800) return rtf.format(-Math.floor(diffInSeconds / 86400), 'day')
    return date.toLocaleDateString(locale)
}

// Helper function for time-based greeting key
function getGreetingKey(): { key: string; emoji: string } {
    const hour = new Date().getHours()
    if (hour < 12) return { key: 'morning', emoji: '☀️' }
    if (hour < 17) return { key: 'afternoon', emoji: '👋' }
    if (hour < 21) return { key: 'evening', emoji: '🌆' }
    return { key: 'night', emoji: '🌙' }
}

// Helper to count items from last 7 days
function countRecentItems<T extends { created_at: string }>(items: T[]): number {
    const weekAgo = new Date()
    weekAgo.setDate(weekAgo.getDate() - 7)
    return items.filter(item => new Date(item.created_at) > weekAgo).length
}

interface ProspectWithStatus {
    id: string
    company_name: string
    hasResearch: boolean
    researchId?: string
    researchStatus?: string
    hasPrep: boolean
    prepId?: string
    prepStatus?: string
    hasFollowup: boolean
    followupId?: string
    followupStatus?: string
    lastActivity: string
    nextAction: 'research' | 'prep' | 'followup' | 'complete'
}

export default function DashboardPage() {
    const router = useRouter()
    const supabase = createClientComponentClient()
    const { toast } = useToast()
    const [user, setUser] = useState<User | null>(null)
    const [loading, setLoading] = useState(true)
    const [profile, setProfile] = useState<SalesProfile | null>(null)
    const [companyProfile, setCompanyProfile] = useState<CompanyProfile | null>(null)
    const [knowledgeBase, setKnowledgeBase] = useState<KBFile[]>([])
    const [researchBriefs, setResearchBriefs] = useState<ResearchBrief[]>([])
    const [meetingPreps, setMeetingPreps] = useState<MeetingPrep[]>([])
    const [followups, setFollowups] = useState<Followup[]>([])
    const [activities, setActivities] = useState<Activity[]>([])
    
    // Research Sheet state - for adding new prospects
    const [researchSheetOpen, setResearchSheetOpen] = useState(false)
    
    // Billing context for flow usage
    const { subscription, usage, loading: billingLoading } = useBilling()

    useEffect(() => {
        const loadData = async () => {
            const { data: { user } } = await supabase.auth.getUser()
            setUser(user)

            if (user) {
                try {
                    // Fetch all data in parallel using centralized API client
                    const [profileRes, companyRes, kbRes, researchRes, prepsRes, followupsRes, activityRes] = await Promise.all([
                        api.get<SalesProfile>('/api/v1/profile/sales'),
                        api.get<CompanyProfile>('/api/v1/profile/company'),
                        api.get<{ files: KBFile[] }>('/api/v1/knowledge-base/files'),
                        api.get<{ briefs: ResearchBrief[] }>('/api/v1/research/briefs'),
                        api.get<{ preps: MeetingPrep[] }>('/api/v1/prep/briefs'),
                        api.get<Followup[]>('/api/v1/followup/list'),
                        api.get<{ activities: Activity[] }>('/api/v1/dashboard/activity?limit=5'),
                    ])

                    if (!profileRes.error && profileRes.data) setProfile(profileRes.data)
                    if (!companyRes.error && companyRes.data) setCompanyProfile(companyRes.data)
                    if (!kbRes.error && kbRes.data) setKnowledgeBase(kbRes.data.files || [])
                    if (!researchRes.error && researchRes.data) setResearchBriefs(researchRes.data.briefs || [])
                    if (!prepsRes.error && prepsRes.data) setMeetingPreps(prepsRes.data.preps || [])
                    if (!followupsRes.error && followupsRes.data) setFollowups(followupsRes.data || [])
                    if (!activityRes.error && activityRes.data) setActivities(activityRes.data.activities || [])
                } catch (error) {
                    logger.error('Failed to load data', error, { source: 'DashboardPage' })
                }
            }

            setLoading(false)
        }
        loadData()
    }, [supabase])

    // Calculate trends (items from last 7 days)
    const recentResearch = useMemo(() => countRecentItems(researchBriefs), [researchBriefs])
    const recentPreps = useMemo(() => countRecentItems(meetingPreps), [meetingPreps])
    const recentFollowups = useMemo(() => countRecentItems(followups), [followups])

    // Build prospect-centric view
    const prospects = useMemo(() => {
        const prospectMap = new Map<string, ProspectWithStatus>()

        // Add from research briefs
        researchBriefs.forEach(brief => {
            const name = brief.company_name.toLowerCase()
            if (!prospectMap.has(name)) {
                prospectMap.set(name, {
                    id: brief.id,
                    company_name: brief.company_name,
                    hasResearch: true,
                    researchId: brief.id,
                    researchStatus: brief.status,
                    hasPrep: false,
                    hasFollowup: false,
                    lastActivity: brief.created_at,
                    nextAction: brief.status === 'completed' ? 'prep' : 'research'
                })
            } else {
                const existing = prospectMap.get(name)!
                existing.hasResearch = true
                existing.researchId = brief.id
                existing.researchStatus = brief.status
                if (new Date(brief.created_at) > new Date(existing.lastActivity)) {
                    existing.lastActivity = brief.created_at
                }
            }
        })

        // Add from meeting preps
        meetingPreps.forEach(prep => {
            const name = prep.prospect_company_name.toLowerCase()
            if (!prospectMap.has(name)) {
                prospectMap.set(name, {
                    id: prep.id,
                    company_name: prep.prospect_company_name,
                    hasResearch: false,
                    hasPrep: true,
                    prepId: prep.id,
                    prepStatus: prep.status,
                    hasFollowup: false,
                    lastActivity: prep.created_at,
                    nextAction: prep.status === 'completed' ? 'followup' : 'prep'
                })
            } else {
                const existing = prospectMap.get(name)!
                existing.hasPrep = true
                existing.prepId = prep.id
                existing.prepStatus = prep.status
                if (prep.status === 'completed') {
                    existing.nextAction = 'followup'
                }
                if (new Date(prep.created_at) > new Date(existing.lastActivity)) {
                    existing.lastActivity = prep.created_at
                }
            }
        })

        // Add from followups
        followups.forEach(followup => {
            const name = (followup.prospect_company_name || followup.meeting_subject || '').toLowerCase()
            if (!name) return
            
            if (!prospectMap.has(name)) {
                prospectMap.set(name, {
                    id: followup.id,
                    company_name: followup.prospect_company_name || followup.meeting_subject || '',
                    hasResearch: false,
                    hasPrep: false,
                    hasFollowup: true,
                    followupId: followup.id,
                    followupStatus: followup.status,
                    lastActivity: followup.created_at,
                    nextAction: 'complete'
                })
            } else {
                const existing = prospectMap.get(name)!
                existing.hasFollowup = true
                existing.followupId = followup.id
                existing.followupStatus = followup.status
                if (followup.status === 'completed') {
                    existing.nextAction = 'complete'
                }
                if (new Date(followup.created_at) > new Date(existing.lastActivity)) {
                    existing.lastActivity = followup.created_at
                }
            }
        })

        // Sort by last activity (most recent first)
        return Array.from(prospectMap.values())
            .sort((a, b) => new Date(b.lastActivity).getTime() - new Date(a.lastActivity).getTime())
    }, [researchBriefs, meetingPreps, followups])

    const t = useTranslations('dashboard')
    const tCommon = useTranslations('common')
    const tNavigation = useTranslations('navigation')
    const locale = useLocale()

    if (loading) {
        return (
            <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
                <div className="text-center">
                    <Icons.spinner className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
                    <p className="text-sm text-slate-500 dark:text-slate-400">{t('loading')}</p>
                </div>
            </div>
        )
    }

    // Smart suggestion based on activity
    const getSuggestion = () => {
        if (!profile?.full_name) return { 
            text: t('suggestions.createProfile'), 
            action: '/onboarding', 
            actionText: t('actions.createProfile'),
            icon: Icons.user,
        }
        if (!companyProfile?.company_name) return { 
            text: t('suggestions.addCompany'), 
            action: '/onboarding/company', 
            actionText: t('actions.addCompany'),
            icon: Icons.building,
        }
        if (researchBriefs.length === 0) return { 
            text: t('suggestions.startResearch'), 
            action: '/dashboard/research', 
            actionText: t('actions.startResearch'),
            icon: Icons.search,
        }
        // Find a completed research without contacts to suggest adding contacts first
        const completedResearch = researchBriefs.find(b => b.status === 'completed')
        if (meetingPreps.length === 0 && completedResearch) return { 
            text: t('suggestions.addContact', { company: completedResearch.company_name }), 
            action: `/dashboard/research/${completedResearch.id}`, 
            actionText: t('actions.addContact'),
            icon: Icons.userPlus,
        }
        if (followups.length === 0 && meetingPreps.some(p => p.status === 'completed')) return { 
            text: t('suggestions.uploadMeeting'), 
            action: '/dashboard/followup', 
            actionText: t('actions.uploadMeeting'),
            icon: Icons.mic,
        }
        
        // Check for prospects that need attention - first add contact, then prep
        const needsContact = prospects.find(p => p.hasResearch && p.researchStatus === 'completed' && !p.hasPrep)
        if (needsContact) return {
            text: t('suggestions.addContact', { company: needsContact.company_name }),
            action: `/dashboard/research/${needsContact.researchId}`,
            actionText: t('actions.addContact'),
            icon: Icons.userPlus,
        }
        
        const needsFollowup = prospects.find(p => p.hasPrep && p.prepStatus === 'completed' && !p.hasFollowup)
        if (needsFollowup) return {
            text: t('suggestions.needsFollowup', { company: needsFollowup.company_name }),
            action: '/dashboard/followup',
            actionText: t('actions.followup'),
            icon: Icons.mic,
        }

        return { 
            text: t('suggestions.allDone'), 
            action: '/dashboard/research', 
            actionText: t('actions.newProspect'),
            icon: Icons.sparkles,
        }
    }
    
    const suggestion = getSuggestion()
    const { key: greetingKey, emoji } = getGreetingKey()
    const greeting = t(`greeting.${greetingKey}`)
    const SuggestionIcon = suggestion.icon

    const getNextActionButton = (prospect: ProspectWithStatus) => {
        switch (prospect.nextAction) {
            case 'research':
                return (
                    <span className="text-xs text-blue-600 dark:text-blue-400 flex items-center gap-1">
                        <Icons.spinner className="h-3 w-3 animate-spin" />
                        {t('actions.researchInProgress')}
                    </span>
                )
            case 'prep':
                return (
                    <Button size="sm" className="h-7 text-xs bg-green-600 hover:bg-green-700" onClick={(e) => {
                        e.stopPropagation()
                        sessionStorage.setItem('prepareForCompany', prospect.company_name)
                        router.push('/dashboard/preparation')
                    }}>
                        <Icons.fileText className="h-3 w-3 mr-1" />
                        {t('actions.prepare')}
                    </Button>
                )
            case 'followup':
                return (
                    <Button size="sm" className="h-7 text-xs bg-orange-600 hover:bg-orange-700" onClick={(e) => {
                        e.stopPropagation()
                        sessionStorage.setItem('followupForCompany', prospect.company_name)
                        router.push('/dashboard/followup')
                    }}>
                        <Icons.mic className="h-3 w-3 mr-1" />
                        {t('actions.followup')}
                    </Button>
                )
            case 'complete':
                return (
                    <span className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                        <Icons.check className="h-3 w-3" />
                        {t('actions.complete')}
                    </span>
                )
        }
    }

    const getProspectLink = (prospect: ProspectWithStatus) => {
        if (prospect.followupId && prospect.followupStatus === 'completed') {
            return `/dashboard/followup/${prospect.followupId}`
        }
        if (prospect.prepId && prospect.prepStatus === 'completed') {
            return `/dashboard/preparation/${prospect.prepId}`
        }
        if (prospect.researchId && prospect.researchStatus === 'completed') {
            return `/dashboard/research/${prospect.researchId}`
        }
        return null
    }
    
    // Activity icon mapper
    const getActivityIcon = (iconName: string) => {
        switch (iconName) {
            case 'search': return Icons.search
            case 'fileText': return Icons.fileText
            case 'mail': return Icons.mail
            case 'userPlus': return Icons.userPlus
            default: return Icons.check
        }
    }
    
    // Flow usage calculation
    const flowUsage = usage?.flow
    const flowPercentage = flowUsage ? (flowUsage.unlimited ? 100 : Math.round((flowUsage.used / flowUsage.limit) * 100)) : 0

    return (
        <DashboardLayout user={user}>
            <div className="p-4 lg:p-6">
                {/* Welcome + Luna Insight */}
                <div className="mb-6">
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">
                        {greeting}{typeof profile?.full_name === 'string' && profile.full_name ? `, ${profile.full_name.split(' ')[0]}` : ''}! {emoji}
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 text-sm mb-4">
                        {t('title')}
                    </p>
                    
                    {/* Luna Insight Card - Purple Gradient */}
                    <div className="bg-gradient-to-r from-violet-600 to-purple-600 rounded-xl p-5 shadow-lg">
                        <div className="flex items-start gap-4">
                            {/* Luna Avatar */}
                            <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
                                <Icons.sparkles className="h-6 w-6 text-white" />
                            </div>
                            
                            {/* Content */}
                            <div className="flex-1 min-w-0">
                                <p className="text-sm text-white/70 mb-1">{t('luna.title')}</p>
                                <p className="font-medium text-white">{suggestion.text}</p>
                            </div>
                            
                            {/* Action Button */}
                            {suggestion.action && (
                                <Button 
                                    onClick={() => router.push(suggestion.action!)} 
                                    variant="secondary"
                                    className="flex-shrink-0 bg-white/20 hover:bg-white/30 text-white border-0"
                                >
                                    {suggestion.actionText}
                                    <Icons.arrowRight className="h-4 w-4 ml-2" />
                                </Button>
                            )}
                        </div>
                    </div>
                </div>

                {/* Two Column Layout */}
                <div className="flex flex-col lg:flex-row gap-6">
                    {/* Left: Prospects + Activity */}
                    <div className="flex-1 min-w-0 space-y-6">
                        {/* Prospects Section */}
                        <div>
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                                    <Icons.users className="h-5 w-5 text-slate-400" />
                                    {t('prospects.title')}
                                    <span className="text-sm font-normal text-slate-400">({prospects.length})</span>
                                </h2>
                                <Button size="sm" onClick={() => setResearchSheetOpen(true)}>
                                    <Icons.plus className="h-4 w-4 mr-1" />
                                    {t('actions.newProspect')}
                                </Button>
                            </div>

                            {prospects.length === 0 ? (
                                <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-12 text-center">
                                    <Icons.users className="h-16 w-16 text-slate-200 dark:text-slate-700 mx-auto mb-4" />
                                    <h3 className="font-semibold text-slate-700 dark:text-slate-200 mb-2">{t('prospects.empty')}</h3>
                                    <p className="text-slate-500 dark:text-slate-400 text-sm mb-4">
                                        {t('prospects.emptyDescription')}
                                    </p>
                                    <Button onClick={() => setResearchSheetOpen(true)}>
                                        <Icons.search className="h-4 w-4 mr-2" />
                                        {t('actions.startResearch')}
                                    </Button>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {prospects.slice(0, 6).map((prospect) => {
                                        const link = getProspectLink(prospect)
                                        return (
                                            <div
                                                key={prospect.id}
                                                className={`bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 hover:shadow-md dark:hover:shadow-slate-800/50 transition-all ${link ? 'cursor-pointer' : ''}`}
                                                onClick={() => link && router.push(link)}
                                            >
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-4 min-w-0 flex-1">
                                                        {/* Company Initial */}
                                                        <div className="w-10 h-10 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center flex-shrink-0">
                                                            <span className="font-bold text-slate-600 dark:text-slate-300">
                                                                {prospect.company_name.charAt(0).toUpperCase()}
                                                            </span>
                                                        </div>
                                                        
                                                        {/* Company Info */}
                                                        <div className="min-w-0 flex-1">
                                                            <h3 className="font-semibold text-slate-900 dark:text-white truncate">{prospect.company_name}</h3>
                                                            <p className="text-xs text-slate-500 dark:text-slate-400">{getRelativeTime(prospect.lastActivity, locale)}</p>
                                                        </div>

                                                        {/* Status Indicators */}
                                                        <div className="flex items-center gap-2">
                                                            {/* Research */}
                                                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                                                                prospect.hasResearch && prospect.researchStatus === 'completed' 
                                                                    ? 'bg-blue-100 dark:bg-blue-900' 
                                                                    : prospect.hasResearch 
                                                                        ? 'bg-blue-50 dark:bg-blue-950' 
                                                                        : 'bg-slate-100 dark:bg-slate-800'
                                                            }`} title={tNavigation('research')}>
                                                                {prospect.hasResearch && prospect.researchStatus === 'completed' ? (
                                                                    <Icons.check className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                                                                ) : prospect.hasResearch ? (
                                                                    <Icons.spinner className="h-4 w-4 text-blue-400 animate-spin" />
                                                                ) : (
                                                                    <Icons.search className="h-4 w-4 text-slate-300 dark:text-slate-600" />
                                                                )}
                                                            </div>
                                                            
                                                            {/* Prep */}
                                                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                                                                prospect.hasPrep && prospect.prepStatus === 'completed' 
                                                                    ? 'bg-green-100 dark:bg-green-900' 
                                                                    : prospect.hasPrep 
                                                                        ? 'bg-green-50 dark:bg-green-950' 
                                                                        : 'bg-slate-100 dark:bg-slate-800'
                                                            }`} title={tNavigation('preparation')}>
                                                                {prospect.hasPrep && prospect.prepStatus === 'completed' ? (
                                                                    <Icons.check className="h-4 w-4 text-green-600 dark:text-green-400" />
                                                                ) : prospect.hasPrep ? (
                                                                    <Icons.spinner className="h-4 w-4 text-green-400 animate-spin" />
                                                                ) : (
                                                                    <Icons.fileText className="h-4 w-4 text-slate-300 dark:text-slate-600" />
                                                                )}
                                                            </div>
                                                            
                                                            {/* Follow-up */}
                                                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                                                                prospect.hasFollowup && prospect.followupStatus === 'completed' 
                                                                    ? 'bg-orange-100 dark:bg-orange-900' 
                                                                    : prospect.hasFollowup 
                                                                        ? 'bg-orange-50 dark:bg-orange-950' 
                                                                        : 'bg-slate-100 dark:bg-slate-800'
                                                            }`} title={tNavigation('followup')}>
                                                                {prospect.hasFollowup && prospect.followupStatus === 'completed' ? (
                                                                    <Icons.check className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                                                                ) : prospect.hasFollowup ? (
                                                                    <Icons.spinner className="h-4 w-4 text-orange-400 animate-spin" />
                                                                ) : (
                                                                    <Icons.mail className="h-4 w-4 text-slate-300 dark:text-slate-600" />
                                                                )}
                                                            </div>
                                                        </div>
                                                    </div>

                                                    {/* Next Action */}
                                                    <div className="ml-4 flex-shrink-0">
                                                        {getNextActionButton(prospect)}
                                                    </div>
                                                </div>
                                            </div>
                                        )
                                    })}
                                    
                                    {prospects.length > 6 && (
                                        <button 
                                            className="w-full py-3 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 flex items-center justify-center gap-2"
                                            onClick={() => router.push('/dashboard/prospects')}
                                        >
                                            {t('prospects.viewAll', { count: prospects.length })}
                                            <Icons.arrowRight className="h-4 w-4" />
                                        </button>
                                    )}
                                </div>
                            )}
                        </div>
                        
                        {/* Activity Feed */}
                        {activities.length > 0 && (
                            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4">
                                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                                    <Icons.clock className="h-4 w-4 text-slate-400" />
                                    {t('activity.title')}
                                </h3>
                                <div className="space-y-3">
                                    {activities.map((activity) => {
                                        const ActivityIcon = getActivityIcon(activity.icon)
                                        const colorClasses: Record<string, string> = {
                                            blue: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/50',
                                            green: 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/50',
                                            orange: 'text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/50',
                                            purple: 'text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-900/50',
                                        }
                                        return (
                                            <div key={activity.id} className="flex items-center gap-3">
                                                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${colorClasses[activity.color] || colorClasses.blue}`}>
                                                    <ActivityIcon className="h-4 w-4" />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-sm text-slate-700 dark:text-slate-200 truncate">
                                                        {t(`activity.${activity.type}`, { company: activity.company })}
                                                    </p>
                                                </div>
                                                <span className="text-xs text-slate-400 flex-shrink-0">
                                                    {getRelativeTime(activity.timestamp, locale)}
                                                </span>
                                            </div>
                                        )
                                    })}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Right: Sidebar */}
                    <div className="w-full lg:w-80 flex-shrink-0">
                        <div className="lg:sticky lg:top-4 space-y-4">
                            
                            {/* Mobile: Stats in horizontal scroll */}
                            <div className="lg:hidden flex gap-3 overflow-x-auto pb-2 -mx-4 px-4">
                                <div className="flex-shrink-0 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-3 min-w-[100px] text-center">
                                    <Icons.search className="h-5 w-5 text-blue-600 dark:text-blue-400 mx-auto mb-1" />
                                    <p className="text-lg font-bold text-slate-900 dark:text-white">{researchBriefs.length}</p>
                                    <p className="text-xs text-slate-500">{t('stats.research')}</p>
                                </div>
                                <div className="flex-shrink-0 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-3 min-w-[100px] text-center">
                                    <Icons.fileText className="h-5 w-5 text-green-600 dark:text-green-400 mx-auto mb-1" />
                                    <p className="text-lg font-bold text-slate-900 dark:text-white">{meetingPreps.length}</p>
                                    <p className="text-xs text-slate-500">{t('stats.preparations')}</p>
                                </div>
                                <div className="flex-shrink-0 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-3 min-w-[100px] text-center">
                                    <Icons.mail className="h-5 w-5 text-orange-600 dark:text-orange-400 mx-auto mb-1" />
                                    <p className="text-lg font-bold text-slate-900 dark:text-white">{followups.length}</p>
                                    <p className="text-xs text-slate-500">{t('stats.followups')}</p>
                                </div>
                                {flowUsage && (
                                    <div className="flex-shrink-0 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-3 min-w-[100px] text-center">
                                        <Icons.barChart className="h-5 w-5 text-purple-600 dark:text-purple-400 mx-auto mb-1" />
                                        <p className="text-lg font-bold text-slate-900 dark:text-white">
                                            {flowUsage.unlimited ? '∞' : `${flowUsage.used}/${flowUsage.limit}`}
                                        </p>
                                        <p className="text-xs text-slate-500">{t('flowUsage.title')}</p>
                                    </div>
                                )}
                            </div>
                            
                            {/* Desktop: Stats Widget */}
                            <div className="hidden lg:block rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                                    <Icons.barChart className="h-4 w-4 text-slate-400" />
                                    {t('stats.thisWeek')}
                                </h3>
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <div className="w-8 h-8 rounded-lg bg-blue-50 dark:bg-blue-900 flex items-center justify-center">
                                                <Icons.search className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                                            </div>
                                            <span className="text-sm text-slate-600 dark:text-slate-300">{t('stats.research')}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="font-bold text-slate-900 dark:text-white">{researchBriefs.length}</span>
                                            {recentResearch > 0 && (
                                                <span className="text-xs font-medium text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900 px-1.5 py-0.5 rounded-full">
                                                    +{recentResearch}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <div className="w-8 h-8 rounded-lg bg-green-50 dark:bg-green-900 flex items-center justify-center">
                                                <Icons.fileText className="h-4 w-4 text-green-600 dark:text-green-400" />
                                            </div>
                                            <span className="text-sm text-slate-600 dark:text-slate-300">{t('stats.preparations')}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="font-bold text-slate-900 dark:text-white">{meetingPreps.length}</span>
                                            {recentPreps > 0 && (
                                                <span className="text-xs font-medium text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900 px-1.5 py-0.5 rounded-full">
                                                    +{recentPreps}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <div className="w-8 h-8 rounded-lg bg-orange-50 dark:bg-orange-900 flex items-center justify-center">
                                                <Icons.mail className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                                            </div>
                                            <span className="text-sm text-slate-600 dark:text-slate-300">{t('stats.followups')}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="font-bold text-slate-900 dark:text-white">{followups.length}</span>
                                            {recentFollowups > 0 && (
                                                <span className="text-xs font-medium text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900 px-1.5 py-0.5 rounded-full">
                                                    +{recentFollowups}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            {/* Flow Usage Widget */}
                            {flowUsage && (
                                <div className="hidden lg:block rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                                    <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                                        <Icons.zap className="h-4 w-4 text-purple-600" />
                                        {t('flowUsage.title')}
                                    </h3>
                                    
                                    {flowUsage.unlimited ? (
                                        <div className="flex items-center gap-2">
                                            <span className="text-2xl font-bold text-purple-600">∞</span>
                                            <span className="text-sm text-slate-600 dark:text-slate-400">{t('flowUsage.unlimited')}</span>
                                        </div>
                                    ) : (
                                        <>
                                            <div className="flex items-baseline gap-1 mb-2">
                                                <span className="text-2xl font-bold text-slate-900 dark:text-white">{flowUsage.used}</span>
                                                <span className="text-slate-400">/ {flowUsage.limit}</span>
                                            </div>
                                            <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden mb-2">
                                                <div 
                                                    className={`h-full rounded-full transition-all ${flowPercentage > 80 ? 'bg-orange-500' : 'bg-purple-600'}`}
                                                    style={{ width: `${Math.min(flowPercentage, 100)}%` }}
                                                />
                                            </div>
                                            <p className="text-xs text-slate-500">
                                                {t('flowUsage.remaining', { remaining: flowUsage.limit - flowUsage.used })}
                                            </p>
                                        </>
                                    )}
                                    
                                    {subscription && (
                                        <p className="text-xs text-slate-400 mt-2">{subscription.plan_name}</p>
                                    )}
                                    
                                    {!flowUsage.unlimited && flowPercentage > 80 && (
                                        <Button 
                                            size="sm" 
                                            variant="outline" 
                                            className="w-full mt-3 text-purple-600 border-purple-200 hover:bg-purple-50"
                                            onClick={() => router.push('/dashboard/settings')}
                                        >
                                            {t('flowUsage.upgrade')}
                                        </Button>
                                    )}
                                </div>
                            )}

                            {/* Quick Actions */}
                            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                                    <Icons.zap className="h-4 w-4 text-amber-500" />
                                    {t('quickActions.title')}
                                </h3>
                                <div className="grid grid-cols-2 gap-2">
                                    <button
                                        onClick={() => setResearchSheetOpen(true)}
                                        className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/50 hover:bg-blue-100 dark:hover:bg-blue-900 transition-colors text-center"
                                    >
                                        <Icons.search className="h-5 w-5 text-blue-600 dark:text-blue-400 mx-auto mb-1" />
                                        <span className="text-xs font-medium text-blue-700 dark:text-blue-300">{t('quickActions.newResearch')}</span>
                                    </button>
                                    <button
                                        onClick={() => router.push('/dashboard/preparation')}
                                        className="p-3 rounded-lg bg-green-50 dark:bg-green-900/50 hover:bg-green-100 dark:hover:bg-green-900 transition-colors text-center"
                                    >
                                        <Icons.fileText className="h-5 w-5 text-green-600 dark:text-green-400 mx-auto mb-1" />
                                        <span className="text-xs font-medium text-green-700 dark:text-green-300">{tNavigation('preparation')}</span>
                                    </button>
                                    <button
                                        onClick={() => router.push('/dashboard/followup')}
                                        className="p-3 rounded-lg bg-orange-50 dark:bg-orange-900/50 hover:bg-orange-100 dark:hover:bg-orange-900 transition-colors text-center"
                                    >
                                        <Icons.mic className="h-5 w-5 text-orange-600 dark:text-orange-400 mx-auto mb-1" />
                                        <span className="text-xs font-medium text-orange-700 dark:text-orange-300">{tNavigation('followup')}</span>
                                    </button>
                                    <button
                                        onClick={() => router.push('/dashboard/knowledge-base')}
                                        className="p-3 rounded-lg bg-purple-50 dark:bg-purple-900/50 hover:bg-purple-100 dark:hover:bg-purple-900 transition-colors text-center"
                                    >
                                        <Icons.book className="h-5 w-5 text-purple-600 dark:text-purple-400 mx-auto mb-1" />
                                        <span className="text-xs font-medium text-purple-700 dark:text-purple-300">Docs</span>
                                    </button>
                                </div>
                            </div>

                            {/* Profiles Status */}
                            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
                                <h3 className="font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                                    <Icons.user className="h-4 w-4 text-slate-400" />
                                    {t('profile.salesProfile')}
                                </h3>
                                <div className="space-y-2">
                                    <button
                                        onClick={() => router.push(profile?.full_name ? '/dashboard/profile' : '/onboarding')}
                                        className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                                    >
                                        <div className="flex items-center gap-2">
                                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                                                profile?.full_name ? 'bg-violet-100 dark:bg-violet-900' : 'bg-slate-100 dark:bg-slate-800'
                                            }`}>
                                                <Icons.user className={`h-4 w-4 ${profile?.full_name ? 'text-violet-600 dark:text-violet-400' : 'text-slate-400'}`} />
                                            </div>
                                            <span className="text-sm text-slate-700 dark:text-slate-200">{t('profile.salesProfile')}</span>
                                        </div>
                                        {profile?.full_name ? (
                                            <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                                                <Icons.check className="h-3 w-3" />
                                                {profile.profile_completeness || 0}%
                                            </span>
                                        ) : (
                                            <span className="text-xs text-amber-600 dark:text-amber-400">{t('profile.incomplete')} →</span>
                                        )}
                                    </button>
                                    <button
                                        onClick={() => router.push(companyProfile?.company_name ? '/dashboard/company-profile' : '/onboarding/company')}
                                        className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                                    >
                                        <div className="flex items-center gap-2">
                                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                                                companyProfile?.company_name ? 'bg-indigo-100 dark:bg-indigo-900' : 'bg-slate-100 dark:bg-slate-800'
                                            }`}>
                                                <Icons.building className={`h-4 w-4 ${companyProfile?.company_name ? 'text-indigo-600 dark:text-indigo-400' : 'text-slate-400'}`} />
                                            </div>
                                            <span className="text-sm text-slate-700 dark:text-slate-200">{t('profile.companyProfile')}</span>
                                        </div>
                                        {companyProfile?.company_name ? (
                                            <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                                                <Icons.check className="h-3 w-3" />
                                                {companyProfile.profile_completeness || 0}%
                                            </span>
                                        ) : (
                                            <span className="text-xs text-amber-600 dark:text-amber-400">{t('profile.incomplete')} →</span>
                                        )}
                                    </button>
                                </div>
                            </div>

                            {/* Knowledge Base */}
                            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-gradient-to-br from-purple-50 to-indigo-50 dark:from-purple-950 dark:to-indigo-950 p-4 shadow-sm">
                                <h3 className="font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                                    <Icons.book className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                                    Knowledge Base
                                </h3>
                                <p className="text-xs text-slate-600 dark:text-slate-300 mb-3">
                                    {t('profile.documentsCount', { count: knowledgeBase.length })}
                                </p>
                                <Button 
                                    variant="outline" 
                                    size="sm" 
                                    className="w-full"
                                    onClick={() => router.push('/dashboard/knowledge-base')}
                                >
                                    <Icons.upload className="h-4 w-4 mr-2" />
                                    {tCommon('upload')}
                                </Button>
                            </div>

                        </div>
                    </div>
                </div>
                
                {/* Research Sheet - Opens when clicking "New Prospect" */}
                <Sheet open={researchSheetOpen} onOpenChange={setResearchSheetOpen}>
                    <SheetContent side="right" className="sm:max-w-md overflow-y-auto">
                        <SheetHeader>
                            <SheetTitle className="flex items-center gap-2">
                                <Icons.search className="w-5 h-5 text-blue-600" />
                                {t('quickActions.newResearch')}
                            </SheetTitle>
                            <SheetDescription>
                                {t('prospects.emptyDescription')}
                            </SheetDescription>
                        </SheetHeader>
                        <div className="mt-6">
                            <ResearchForm
                                onSuccess={(result) => {
                                    setResearchSheetOpen(false)
                                    toast({ 
                                        title: t('toast.researchStarted'),
                                        description: t('toast.researchStartedDesc')
                                    })
                                    // Navigate directly to the new prospect's hub
                                    router.push(`/dashboard/prospects/${result.prospect_id}`)
                                }}
                                onCancel={() => setResearchSheetOpen(false)}
                                isSheet={true}
                            />
                        </div>
                    </SheetContent>
                </Sheet>
            </div>
        </DashboardLayout>
    )
}
