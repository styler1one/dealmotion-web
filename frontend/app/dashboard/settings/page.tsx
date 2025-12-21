'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DashboardLayout } from '@/components/layout'
import { 
  ArrowLeft, 
  Globe,
  MessageSquare,
  Mail,
  Loader2,
  Settings,
  Save,
  CreditCard,
  Link,
  Bell,
  ExternalLink,
  Sparkles,
  Crown,
  Brain,
  RotateCcw,
  Power,
  Palette,
  Smile,
  Type,
  FileText,
  Zap,
  Infinity,
  ArrowRight,
  Check,
  Calendar,
  RefreshCw,
  AlertCircle,
  Mic,
  X
} from 'lucide-react'
import { useTranslations, useLocale } from 'next-intl'
import { useToast } from '@/components/ui/use-toast'
import { useSettings } from '@/lib/settings-context'
import { LanguageSelect } from '@/components/language-select'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { useBilling } from '@/lib/billing-context'
import { CreditUsage } from '@/components/credit-usage'
import { CreditPacksModal } from '@/components/credit-packs-modal'
import { api } from '@/lib/api'
import { logger } from '@/lib/logger'
import { useConfirmDialog } from '@/components/confirm-dialog'
import { AutoRecordSettings } from '@/components/ai-notetaker/auto-record-settings'
import type { User } from '@supabase/supabase-js'

export default function SettingsPage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const t = useTranslations('settings')
  const tCommon = useTranslations('common')
  const tErrors = useTranslations('errors')
  const tBilling = useTranslations('billing')
  const tIntegrations = useTranslations('settings.integrations')
  const { toast } = useToast()
  const currentLocale = useLocale()
  
  const { settings, updateSettings, loading: settingsLoading, loaded: settingsLoaded } = useSettings()
  const { subscription, usage, loading: billingLoading, createCheckoutSession, openBillingPortal } = useBilling()
  const { confirm } = useConfirmDialog()
  
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [billingActionLoading, setBillingActionLoading] = useState(false)
  const [coachResetting, setCoachResetting] = useState(false)
  const [coachToggling, setCoachToggling] = useState(false)
  const [coachEnabled, setCoachEnabled] = useState<boolean | null>(null)
  const [coachSettingsLoading, setCoachSettingsLoading] = useState(true)
  
  // Style guide state
  const [styleGuide, setStyleGuide] = useState({
    tone: 'professional',
    formality: 'professional',
    emoji_usage: false,
    signoff: 'Best regards',
    writing_length: 'concise'
  })
  const [styleGuideLoading, setStyleGuideLoading] = useState(true)
  const [styleSaving, setStyleSaving] = useState(false)
  const [styleHasChanges, setStyleHasChanges] = useState(false)
  const [originalStyleGuide, setOriginalStyleGuide] = useState(styleGuide)
  
  // Calendar integration state
  interface CalendarProviderStatus {
    connected: boolean
    email: string | null
    last_sync: string | null
    last_sync_status: string | null
    meeting_count: number
    needs_reauth: boolean
    sync_enabled: boolean
  }
  
  interface CalendarStatus {
    google: CalendarProviderStatus
    microsoft: CalendarProviderStatus
  }
  
  const [calendarStatus, setCalendarStatus] = useState<CalendarStatus | null>(null)
  const [calendarLoading, setCalendarLoading] = useState(true)
  const [calendarError, setCalendarError] = useState<string | null>(null)
  const [googleConnecting, setGoogleConnecting] = useState(false)
  const [microsoftConnecting, setMicrosoftConnecting] = useState(false)
  const [calendarSyncing, setCalendarSyncing] = useState(false)
  const [disconnecting, setDisconnecting] = useState<string | null>(null)
  
  // Recording integrations state
  interface IntegrationProviderStatus {
    connected: boolean
    api_key_set: boolean
    account_email: string | null
    account_name: string | null
    last_sync: string | null
    last_sync_status: string | null
    pending_recordings: number
    auto_import: boolean
  }
  
  interface IntegrationsStatus {
    fireflies: IntegrationProviderStatus
    zoom: IntegrationProviderStatus
    teams: IntegrationProviderStatus
  }
  
  const [integrationsStatus, setIntegrationsStatus] = useState<IntegrationsStatus | null>(null)
  const [integrationsLoading, setIntegrationsLoading] = useState(true)
  const [firefliesApiKey, setFirefliesApiKey] = useState('')
  const [firefliesConnecting, setFirefliesConnecting] = useState(false)
  const [firefliesDisconnecting, setFirefliesDisconnecting] = useState(false)
  const [showFirefliesInput, setShowFirefliesInput] = useState(false)
  
  // Fetch coach settings directly (independent of CoachProvider)
  useEffect(() => {
    const fetchCoachSettings = async () => {
      try {
        const { data, error } = await api.get<{ is_enabled: boolean }>('/api/v1/coach/settings')
        if (!error && data) {
          setCoachEnabled(data.is_enabled)
        }
      } catch (err) {
        logger.error('Failed to fetch coach settings', err, { source: 'SettingsPage' })
      } finally {
        setCoachSettingsLoading(false)
      }
    }
    fetchCoachSettings()
  }, [])
  
  // Fetch style guide
  useEffect(() => {
    const fetchStyleGuide = async () => {
      try {
        const { data, error } = await api.get<typeof styleGuide>('/api/v1/profile/sales/style-guide')
        if (!error && data) {
          setStyleGuide(data)
          setOriginalStyleGuide(data)
        }
      } catch (err) {
        logger.error('Failed to fetch style guide', err, { source: 'SettingsPage' })
      } finally {
        setStyleGuideLoading(false)
      }
    }
    fetchStyleGuide()
  }, [])
  
  // Fetch calendar integration status
  const fetchCalendarStatus = useCallback(async () => {
    setCalendarLoading(true)
    setCalendarError(null)
    try {
      const { data, error } = await api.get<CalendarStatus>('/api/v1/calendar/status')
      if (error) {
        setCalendarError(error.message || 'Failed to load calendar status')
      } else if (data) {
        setCalendarStatus(data)
      }
    } catch (err) {
      logger.error('Failed to fetch calendar status', err, { source: 'SettingsPage' })
      setCalendarError('Failed to load calendar status')
    } finally {
      setCalendarLoading(false)
    }
  }, [])
  
  useEffect(() => {
    fetchCalendarStatus()
  }, [fetchCalendarStatus])
  
  // Fetch recording integrations status
  const fetchIntegrationsStatus = useCallback(async () => {
    setIntegrationsLoading(true)
    try {
      const { data, error } = await api.get<IntegrationsStatus>('/api/v1/integrations/status')
      if (!error && data) {
        setIntegrationsStatus(data)
      }
    } catch (err) {
      logger.error('Failed to fetch integrations status', err, { source: 'SettingsPage' })
    } finally {
      setIntegrationsLoading(false)
    }
  }, [])
  
  useEffect(() => {
    fetchIntegrationsStatus()
  }, [fetchIntegrationsStatus])
  
  // Handle Fireflies connect
  const handleFirefliesConnect = async () => {
    if (!firefliesApiKey.trim()) {
      toast({
        title: 'API Key Required',
        description: 'Please enter your Fireflies API key',
        variant: 'destructive',
      })
      return
    }
    
    setFirefliesConnecting(true)
    try {
      const { data, error } = await api.post<{ success: boolean; account_email?: string; account_name?: string }>(
        '/api/v1/integrations/fireflies/connect',
        { api_key: firefliesApiKey }
      )
      
      if (error) {
        throw new Error(error.message || 'Failed to connect Fireflies')
      }
      
      toast({
        title: tIntegrations('recordings.connectSuccess') || 'Fireflies Connected',
        description: data?.account_email ? `Connected as ${data.account_email}` : undefined,
      })
      
      setFirefliesApiKey('')
      setShowFirefliesInput(false)
      fetchIntegrationsStatus()
      
    } catch (err) {
      logger.error('Fireflies connect failed', err, { source: 'SettingsPage' })
      toast({
        title: tErrors('generic'),
        description: err instanceof Error ? err.message : 'Failed to connect Fireflies',
        variant: 'destructive',
      })
    } finally {
      setFirefliesConnecting(false)
    }
  }
  
  // Handle Fireflies disconnect
  const handleFirefliesDisconnect = async () => {
    const confirmed = await confirm({
      title: 'Disconnect Fireflies?',
      description: 'Your imported recordings will be kept, but no new recordings will be synced.',
      confirmLabel: 'Disconnect',
      variant: 'danger',
    })
    
    if (!confirmed) return
    
    setFirefliesDisconnecting(true)
    try {
      const { error } = await api.delete('/api/v1/integrations/fireflies/disconnect')
      
      if (error) {
        throw new Error(error.message || 'Failed to disconnect')
      }
      
      toast({
        title: 'Fireflies Disconnected',
      })
      
      fetchIntegrationsStatus()
      
    } catch (err) {
      logger.error('Fireflies disconnect failed', err, { source: 'SettingsPage' })
      toast({
        title: tErrors('generic'),
        description: err instanceof Error ? err.message : 'Failed to disconnect',
        variant: 'destructive',
      })
    } finally {
      setFirefliesDisconnecting(false)
    }
  }
  
  // Handle Google Calendar OAuth popup
  const handleGoogleConnect = async () => {
    setGoogleConnecting(true)
    try {
      // Get OAuth URL from backend
      const { data, error } = await api.get<{ auth_url: string; state: string }>('/api/v1/calendar/auth/google')
      
      if (error || !data) {
        throw new Error(error?.message || 'Failed to start Google authorization')
      }
      
      // Store state for verification
      sessionStorage.setItem('google_calendar_state', data.state)
      
      // Open OAuth popup
      const width = 500
      const height = 600
      const left = window.screenX + (window.outerWidth - width) / 2
      const top = window.screenY + (window.outerHeight - height) / 2
      
      const popup = window.open(
        data.auth_url,
        'google_calendar_auth',
        `width=${width},height=${height},left=${left},top=${top},popup=1`
      )
      
      // Poll for popup close or message
      const pollTimer = setInterval(() => {
        if (popup?.closed) {
          clearInterval(pollTimer)
          setGoogleConnecting(false)
          // Refresh status to check if connection was successful
          fetchCalendarStatus()
        }
      }, 500)
      
    } catch (err) {
      logger.error('Failed to start Google OAuth', err, { source: 'SettingsPage' })
      toast({
        title: tErrors('generic'),
        description: tIntegrations('status.error'),
        variant: 'destructive',
      })
      setGoogleConnecting(false)
    }
  }
  
  // Listen for OAuth callback message from popup
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Verify origin
      if (event.origin !== window.location.origin) return
      
      if (event.data?.type === 'google_calendar_connected') {
        setGoogleConnecting(false)
        fetchCalendarStatus()
        toast({
          title: tIntegrations('calendar.connected'),
          description: event.data.email ? `Connected as ${event.data.email}` : undefined,
        })
      } else if (event.data?.type === 'google_calendar_error') {
        setGoogleConnecting(false)
        toast({
          title: tErrors('generic'),
          description: event.data.error || tIntegrations('status.error'),
          variant: 'destructive',
        })
      } else if (event.data?.type === 'microsoft_calendar_connected') {
        setMicrosoftConnecting(false)
        fetchCalendarStatus()
        toast({
          title: tIntegrations('calendar.connected'),
          description: event.data.email ? `Connected as ${event.data.email}` : undefined,
        })
      } else if (event.data?.type === 'microsoft_calendar_error') {
        setMicrosoftConnecting(false)
        toast({
          title: tErrors('generic'),
          description: event.data.error || tIntegrations('status.error'),
          variant: 'destructive',
        })
      }
    }
    
    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [fetchCalendarStatus, toast, tErrors, tIntegrations])
  
  // Handle Microsoft Calendar OAuth popup
  const handleMicrosoftConnect = async () => {
    setMicrosoftConnecting(true)
    try {
      // Get OAuth URL from backend
      const { data, error } = await api.get<{ auth_url: string; state: string }>('/api/v1/calendar/auth/microsoft')
      
      if (error || !data) {
        throw new Error(error?.message || 'Failed to start Microsoft authorization')
      }
      
      // Store state for verification
      sessionStorage.setItem('microsoft_calendar_state', data.state)
      
      // Open OAuth popup
      const width = 500
      const height = 700
      const left = window.screenX + (window.outerWidth - width) / 2
      const top = window.screenY + (window.outerHeight - height) / 2
      
      window.open(
        data.auth_url,
        'microsoft_calendar_auth',
        `width=${width},height=${height},left=${left},top=${top},popup=1`
      )
      
    } catch (err) {
      logger.error('Failed to start Microsoft OAuth', err, { source: 'SettingsPage' })
      toast({
        title: tErrors('generic'),
        description: tIntegrations('status.error'),
        variant: 'destructive',
      })
      setMicrosoftConnecting(false)
    }
  }
  
  // Handle calendar sync
  const handleCalendarSync = async () => {
    setCalendarSyncing(true)
    try {
      const { data, error } = await api.post<{
        synced_meetings: number
        new_meetings: number
        updated_meetings: number
        deleted_meetings: number
      }>('/api/v1/calendar/sync', {})
      
      if (error) {
        throw new Error(error.message || 'Sync failed')
      }
      
      toast({
        title: tIntegrations('calendar.syncNow'),
        description: `${data?.new_meetings || 0} new, ${data?.updated_meetings || 0} updated meetings`,
      })
      
      // Refresh status
      fetchCalendarStatus()
      
    } catch (err) {
      logger.error('Calendar sync failed', err, { source: 'SettingsPage' })
      toast({
        title: tErrors('generic'),
        description: err instanceof Error ? err.message : 'Sync failed',
        variant: 'destructive',
      })
    } finally {
      setCalendarSyncing(false)
    }
  }
  
  // Handle calendar disconnect
  const handleCalendarDisconnect = async (provider: 'google' | 'microsoft') => {
    const providerName = provider === 'google' ? 'Google Calendar' : 'Microsoft 365'
    
    // Confirm before disconnecting with nice dialog
    const confirmed = await confirm({
      title: tIntegrations('calendar.disconnectConfirmTitle'),
      description: tIntegrations('calendar.disconnectConfirmDesc'),
      confirmLabel: tIntegrations('calendar.disconnect'),
      variant: 'danger',
    })
    
    if (!confirmed) return
    
    setDisconnecting(provider)
    try {
      const { error } = await api.delete(`/api/v1/calendar/disconnect/${provider}`)
      
      if (error) {
        throw new Error(error.message || 'Disconnect failed')
      }
      
      toast({
        title: tIntegrations('calendar.disconnectSuccess'),
      })
      
      // Refresh status
      fetchCalendarStatus()
      
    } catch (err) {
      logger.error('Calendar disconnect failed', err, { source: 'SettingsPage' })
      toast({
        title: tIntegrations('calendar.disconnectFailed'),
        description: err instanceof Error ? err.message : 'Disconnect failed',
        variant: 'destructive',
      })
    } finally {
      setDisconnecting(null)
    }
  }
  
  // Local state for form
  const [appLanguage, setAppLanguage] = useState('en')
  const [outputLanguage, setOutputLanguage] = useState('en')
  const [emailLanguage, setEmailLanguage] = useState('en')

  // Sync local state with settings when loaded
  // Also sync cookie with database if they differ
  useEffect(() => {
    if (!settingsLoading && settings && settingsLoaded) {
      setAppLanguage(settings.app_language)
      setOutputLanguage(settings.output_language)
      setEmailLanguage(settings.email_language)
      
      // If database app_language differs from current locale (cookie), update the cookie
      if (settings.app_language && settings.app_language !== currentLocale) {
        document.cookie = `NEXT_LOCALE=${settings.app_language}; path=/; max-age=31536000`
        // Reload to apply the correct language
        window.location.reload()
      }
    }
  }, [settings, settingsLoading, settingsLoaded, currentLocale])

  useEffect(() => {
    const getUser = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) {
        router.push('/login')
        return
      }
      setUser(user)
      setLoading(false)
    }
    getUser()
  }, [supabase, router])

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateSettings({
        app_language: appLanguage,
        output_language: outputLanguage,
        email_language: emailLanguage,
      })

      toast({
        title: t('saved'),
        description: t('savedDesc'),
      })

      // If app language changed, update cookie and reload
      if (appLanguage !== settings.app_language) {
        document.cookie = `NEXT_LOCALE=${appLanguage}; path=/; max-age=31536000`
        // Small delay before reload to show toast
        setTimeout(() => {
          window.location.reload()
        }, 500)
      }
    } catch (error) {
      logger.error('Failed to save settings', error, { source: 'SettingsPage' })
      toast({
        title: t('error'),
        description: t('errorDesc'),
        variant: 'destructive',
      })
    } finally {
      setSaving(false)
    }
  }

  // Check if there are unsaved changes
  const hasChanges = 
    appLanguage !== settings.app_language ||
    outputLanguage !== settings.output_language ||
    emailLanguage !== settings.email_language

  const handleUpgradeToPlan = async (planId: string) => {
    setBillingActionLoading(true)
    try {
      const checkoutUrl = await createCheckoutSession(planId)
      if (checkoutUrl) {
        window.location.href = checkoutUrl
      } else {
        throw new Error('No checkout URL returned')
      }
    } catch (error) {
      logger.error('Failed to start checkout', error, { source: 'SettingsPage' })
      toast({
        title: tErrors('generic'),
        description: error instanceof Error ? error.message : tBilling('checkoutError'),
        variant: 'destructive',
      })
    } finally {
      setBillingActionLoading(false)
    }
  }

  const handleManageSubscription = async () => {
    setBillingActionLoading(true)
    try {
      const portalUrl = await openBillingPortal()
      window.location.href = portalUrl
    } catch (error) {
      logger.error('Failed to open portal', error, { source: 'SettingsPage' })
      toast({
        title: tErrors('generic'),
        description: tBilling('portalError'),
        variant: 'destructive',
      })
    } finally {
      setBillingActionLoading(false)
    }
  }

  // Coach handlers
  const handleCoachToggle = async (enabled: boolean) => {
    setCoachToggling(true)
    try {
      // Update settings via API directly
      const { error } = await api.patch('/api/v1/coach/settings', { 
        is_enabled: enabled,
        widget_state: enabled ? 'minimized' : 'hidden'
      })
      
      if (error) {
        throw new Error(error.message || 'Failed to update settings')
      }
      
      // Update local state immediately
      setCoachEnabled(enabled)
      
      toast({
        title: enabled ? t('coach.enabled') : t('coach.disabled'),
        description: enabled ? t('coach.enabledDesc') : t('coach.disabledDesc'),
      })
      
      // Reload page to ensure coach widget updates
      window.location.reload()
    } catch (error) {
      logger.error('Failed to toggle coach', error, { source: 'SettingsPage' })
      toast({
        title: tErrors('generic'),
        variant: 'destructive',
      })
    } finally {
      setCoachToggling(false)
    }
  }

  const handleCoachReset = async () => {
    setCoachResetting(true)
    try {
      // Reset endpoint now also enables coach
      const { error } = await api.post('/api/v1/coach/suggestions/reset', {})
      if (error) {
        throw new Error(error.message || 'Reset failed')
      }
      
      toast({
        title: t('coach.reset'),
        description: t('coach.resetDesc'),
      })
      // Refresh the page to reset all coach state
      window.location.reload()
    } catch (error) {
      logger.error('Failed to reset coach', error, { source: 'SettingsPage' })
      toast({
        title: tErrors('generic'),
        variant: 'destructive',
      })
      setCoachResetting(false)
    }
  }
  
  // Style guide handlers
  const updateStyleField = (field: keyof typeof styleGuide, value: string | boolean) => {
    setStyleGuide(prev => ({ ...prev, [field]: value }))
    setStyleHasChanges(true)
  }
  
  const handleStyleSave = async () => {
    setStyleSaving(true)
    try {
      const { error } = await api.put('/api/v1/profile/sales/style-guide', styleGuide)
      if (error) {
        throw new Error(error.message || 'Save failed')
      }
      
      setOriginalStyleGuide(styleGuide)
      setStyleHasChanges(false)
      
      toast({
        title: t('style.saved'),
        description: t('style.savedDesc'),
      })
    } catch (error) {
      logger.error('Failed to save style guide', error, { source: 'SettingsPage' })
      toast({
        title: tErrors('generic'),
        variant: 'destructive',
      })
    } finally {
      setStyleSaving(false)
    }
  }

  const getPlanBadge = () => {
    if (!subscription) return null
    
    if (subscription.plan_id === 'free') {
      return <Badge variant="secondary">Free</Badge>
    }
    if (subscription.is_trialing) {
      return <Badge className="bg-amber-500">Trial</Badge>
    }
    // v4 plans
    if (subscription.plan_id === 'pro_monthly' || subscription.plan_id === 'pro_yearly') {
      return <Badge className="bg-gradient-to-r from-blue-500 to-indigo-500">Pro</Badge>
    }
    if (subscription.plan_id === 'pro_plus_monthly' || subscription.plan_id === 'pro_plus_yearly') {
      return <Badge className="bg-gradient-to-r from-indigo-500 to-purple-500">Pro+</Badge>
    }
    // Legacy v2/v3 plans
    if (subscription.plan_id === 'light_solo' || subscription.plan_id === 'pro_solo') {
      return <Badge className="bg-gradient-to-r from-blue-500 to-indigo-500">Pro (Legacy)</Badge>
    }
    if (subscription.plan_id === 'unlimited_solo') {
      return <Badge className="bg-gradient-to-r from-indigo-500 to-purple-500">Pro+ (Legacy)</Badge>
    }
    if (subscription.plan_id.startsWith('solo')) {
      return <Badge className="bg-gradient-to-r from-blue-500 to-indigo-500">Solo</Badge>
    }
    if (subscription.plan_id === 'teams' || subscription.plan_id === 'enterprise') {
      return <Badge className="bg-gradient-to-r from-purple-500 to-pink-500">Enterprise</Badge>
    }
    return null
  }

  if (loading || settingsLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-slate-900">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <DashboardLayout user={user}>
      <div className="p-6 max-w-4xl">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => router.push('/dashboard')}
            className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white mb-4 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            {tCommon('back')}
          </button>
          
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800">
              <Settings className="h-6 w-6 text-slate-600 dark:text-slate-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                {t('title')}
              </h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {t('description')}
              </p>
            </div>
          </div>
        </div>

        {/* Two-column layout for better overview */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* LEFT COLUMN */}
          <div className="space-y-6">
            {/* Language Settings Card */}
            <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Globe className="h-5 w-5 text-blue-500" />
                <CardTitle>{t('language.title')}</CardTitle>
              </div>
              <CardDescription>
                {t('language.description')}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* App Language */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-900 dark:text-white flex items-center gap-2">
                  <Globe className="h-4 w-4 text-slate-400" />
                  {t('language.appLanguage')}
                </label>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {t('language.appLanguageDesc')}
                </p>
                <LanguageSelect
                  value={appLanguage}
                  onChange={setAppLanguage}
                />
              </div>

              {/* Output Language */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-900 dark:text-white flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-slate-400" />
                  {t('language.outputLanguage')}
                </label>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {t('language.outputLanguageDesc')}
                </p>
                <LanguageSelect
                  value={outputLanguage}
                  onChange={setOutputLanguage}
                />
                <p className="text-xs text-slate-400 dark:text-slate-500 italic">
                  💡 {t('language.outputLanguageHint')}
                </p>
              </div>

              {/* Email Language */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-900 dark:text-white flex items-center gap-2">
                  <Mail className="h-4 w-4 text-slate-400" />
                  {t('language.emailLanguage')}
                </label>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {t('language.emailLanguageDesc')}
                </p>
                <LanguageSelect
                  value={emailLanguage}
                  onChange={setEmailLanguage}
                />
                <p className="text-xs text-slate-400 dark:text-slate-500 italic">
                  💡 {t('language.emailLanguageHint')}
                </p>
              </div>

              {/* Save Button */}
              <div className="pt-4 border-t">
                <Button 
                  onClick={handleSave} 
                  disabled={saving || !hasChanges}
                  className="gap-2"
                >
                  {saving ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      {t('saving')}
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4" />
                      {t('save')}
                    </>
                  )}
                </Button>
                {hasChanges && (
                  <span className="ml-3 text-sm text-amber-600 dark:text-amber-400">
                    {t('unsavedChanges')}
                  </span>
                )}
              </div>
            </CardContent>
          </Card>

            {/* AI Coach Settings */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Brain className="h-5 w-5 text-indigo-500" />
                  <CardTitle>{t('coach.title')}</CardTitle>
                </div>
              <CardDescription>
                {t('coach.description')}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Enable/Disable Coach */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <label className="text-sm font-medium text-slate-900 dark:text-white flex items-center gap-2">
                    <Power className="h-4 w-4 text-slate-400" />
                    {t('coach.enableLabel')}
                  </label>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {t('coach.enableDesc')}
                  </p>
                </div>
{coachSettingsLoading ? (
                  <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
                ) : (
                  <Switch
                    checked={coachEnabled ?? true}
                    onCheckedChange={handleCoachToggle}
                    disabled={coachToggling}
                  />
                )}
              </div>

              {/* Reset Snoozed Suggestions */}
              <div className="pt-4 border-t">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <label className="text-sm font-medium text-slate-900 dark:text-white flex items-center gap-2">
                      <RotateCcw className="h-4 w-4 text-slate-400" />
                      {t('coach.resetLabel')}
                    </label>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {t('coach.resetHint')}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCoachReset}
                    disabled={coachResetting}
                    className="gap-2"
                  >
                    {coachResetting ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <RotateCcw className="h-4 w-4" />
                    )}
                    {t('coach.resetButton')}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Communication Style Settings */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Palette className="h-5 w-5 text-pink-500" />
                <CardTitle>{t('style.title')}</CardTitle>
              </div>
              <CardDescription>
                {t('style.description')}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {styleGuideLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
                </div>
              ) : (
                <>
                  {/* Tone */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-900 dark:text-white flex items-center gap-2">
                      <MessageSquare className="h-4 w-4 text-slate-400" />
                      {t('style.tone')}
                    </label>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {t('style.toneDesc')}
                    </p>
                    <select
                      value={styleGuide.tone}
                      onChange={(e) => updateStyleField('tone', e.target.value)}
                      className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm"
                    >
                      <option value="direct">{t('style.toneDirect')}</option>
                      <option value="warm">{t('style.toneWarm')}</option>
                      <option value="formal">{t('style.toneFormal')}</option>
                      <option value="casual">{t('style.toneCasual')}</option>
                      <option value="professional">{t('style.toneProfessional')}</option>
                    </select>
                  </div>

                  {/* Formality */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-900 dark:text-white flex items-center gap-2">
                      <Type className="h-4 w-4 text-slate-400" />
                      {t('style.formality')}
                    </label>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {t('style.formalityDesc')}
                    </p>
                    <select
                      value={styleGuide.formality}
                      onChange={(e) => updateStyleField('formality', e.target.value)}
                      className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm"
                    >
                      <option value="formal">{t('style.formalityFormal')}</option>
                      <option value="professional">{t('style.formalityProfessional')}</option>
                      <option value="casual">{t('style.formalityCasual')}</option>
                    </select>
                  </div>

                  {/* Emoji Usage */}
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <label className="text-sm font-medium text-slate-900 dark:text-white flex items-center gap-2">
                        <Smile className="h-4 w-4 text-slate-400" />
                        {t('style.emoji')}
                      </label>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {t('style.emojiDesc')}
                      </p>
                    </div>
                    <Switch
                      checked={styleGuide.emoji_usage}
                      onCheckedChange={(checked) => updateStyleField('emoji_usage', checked)}
                    />
                  </div>

                  {/* Writing Length */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-900 dark:text-white flex items-center gap-2">
                      <FileText className="h-4 w-4 text-slate-400" />
                      {t('style.length')}
                    </label>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {t('style.lengthDesc')}
                    </p>
                    <select
                      value={styleGuide.writing_length}
                      onChange={(e) => updateStyleField('writing_length', e.target.value)}
                      className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm"
                    >
                      <option value="concise">{t('style.lengthConcise')}</option>
                      <option value="detailed">{t('style.lengthDetailed')}</option>
                    </select>
                  </div>

                  {/* Email Sign-off */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-900 dark:text-white flex items-center gap-2">
                      <Mail className="h-4 w-4 text-slate-400" />
                      {t('style.signoff')}
                    </label>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {t('style.signoffDesc')}
                    </p>
                    <input
                      type="text"
                      value={styleGuide.signoff}
                      onChange={(e) => updateStyleField('signoff', e.target.value)}
                      placeholder="Best regards"
                      className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm"
                    />
                  </div>

                  {/* Save Button */}
                  <div className="pt-4 border-t">
                    <Button 
                      onClick={handleStyleSave} 
                      disabled={styleSaving || !styleHasChanges}
                      className="gap-2"
                    >
                      {styleSaving ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          {t('saving')}
                        </>
                      ) : (
                        <>
                          <Save className="h-4 w-4" />
                          {t('save')}
                        </>
                      )}
                    </Button>
                    {styleHasChanges && (
                      <span className="ml-3 text-sm text-amber-600 dark:text-amber-400">
                        {t('unsavedChanges')}
                      </span>
                    )}
                  </div>
                </>
              )}
            </CardContent>
          </Card>
          </div>

          {/* RIGHT COLUMN */}
          <div className="space-y-6">
          {/* Subscription & Billing */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CreditCard className="h-5 w-5 text-emerald-500" />
                  <CardTitle>{t('sections.subscription')}</CardTitle>
                </div>
                {getPlanBadge()}
              </div>
              <CardDescription>
                {t('subscription.description')}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {billingLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
                </div>
              ) : (
                <>
                  {/* Current Plan Info */}
                  <div className="p-4 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-slate-600 dark:text-slate-400">
                        {tBilling('currentPlan')}
                      </span>
                      {subscription?.is_trialing && (
                        <span className="text-xs text-amber-600 dark:text-amber-400">
                          {tBilling('trialEnds')} {subscription.trial_end ? new Date(subscription.trial_end).toLocaleDateString() : tBilling('soon')}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {subscription?.plan_id !== 'free' && (
                        <Crown className="h-5 w-5 text-amber-500" />
                      )}
                      <span className="text-lg font-semibold text-slate-900 dark:text-white">
                        {subscription?.plan_name || 'Free'}
                      </span>
                      {subscription?.price_cents && subscription.price_cents > 0 && (
                        <span className="text-sm text-slate-500">
                          €{(subscription.price_cents / 100).toFixed(2).replace('.', ',')}{subscription.billing_interval === 'year' ? tBilling('perYear') : tBilling('perMonth')}
                        </span>
                      )}
                    </div>
                    {subscription?.cancel_at_period_end && (
                      <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                        ⚠️ {tBilling('cancelWarning', { date: subscription.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : '' })}
                      </p>
                    )}
                  </div>

                  {/* Credit Usage - v4: Credit-based system */}
                  <CreditUsage />
                  
                  {/* Buy more credits + View details */}
                  <div className="flex items-center justify-between pt-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => router.push('/dashboard/credits')}
                      className="gap-2 text-slate-500"
                    >
                      <TrendingUp className="h-4 w-4" />
                      Bekijk alle transacties
                      <ArrowRight className="h-3 w-3" />
                    </Button>
                    <CreditPacksModal />
                  </div>


                  {/* Upgrade Options - Context-aware */}
                  <div className="pt-4 border-t border-slate-200 dark:border-slate-700">
                    {/* FREE USERS: Show both plan options */}
                    {(!subscription || subscription.plan_id === 'free' || !subscription.is_paid) && (
                      <div className="space-y-4">
                        <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300">
                          {tBilling('upgradePlan')}
                        </h4>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          {/* Pro Card */}
                          <div className="relative p-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 hover:border-blue-300 dark:hover:border-blue-700 transition-colors">
                            <div className="flex items-center gap-2 mb-2">
                              <Zap className="h-5 w-5 text-blue-500" />
                              <span className="font-semibold text-slate-900 dark:text-white">Pro</span>
                            </div>
                            <div className="mb-3">
                              <div className="text-xs text-slate-400 line-through">€79,95</div>
                              <div className="flex items-baseline gap-0.5">
                                <span className="text-2xl font-bold text-slate-900 dark:text-white">€49,95</span>
                                <span className="text-sm text-slate-500">/mo</span>
                              </div>
                            </div>
                            <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">{tBilling('plans.v4.pro.description') || 'Unlimited flows'}</p>
                            <Button 
                              size="sm"
                              onClick={() => handleUpgradeToPlan('pro_monthly')}
                              disabled={billingActionLoading}
                              className="w-full gap-2"
                            >
                              {billingActionLoading ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <ArrowRight className="h-4 w-4" />
                              )}
                              {tBilling('pricing.choosePro') || 'Choose Pro'}
                            </Button>
                          </div>
                          
                          {/* Pro+ Card */}
                          <div className="relative p-4 rounded-lg border-2 border-purple-300 dark:border-purple-700 bg-purple-50 dark:bg-purple-900/20 hover:border-purple-400 dark:hover:border-purple-600 transition-colors">
                            <div className="absolute -top-2 right-3">
                              <Badge className="bg-purple-500 text-white text-xs">{tBilling('pricing.popular') || 'Popular'}</Badge>
                            </div>
                            <div className="flex items-center gap-2 mb-2">
                              <Crown className="h-5 w-5 text-purple-500" />
                              <span className="font-semibold text-slate-900 dark:text-white">Pro+</span>
                            </div>
                            <div className="mb-3">
                              <div className="text-xs text-slate-400 line-through">€99,95</div>
                              <div className="flex items-baseline gap-0.5">
                                <span className="text-2xl font-bold text-slate-900 dark:text-white">€69,95</span>
                                <span className="text-sm text-slate-500">/mo</span>
                              </div>
                            </div>
                            <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">{tBilling('plans.v4.proPlus.description') || 'Includes AI Notetaker'}</p>
                            <Button 
                              size="sm"
                              onClick={() => handleUpgradeToPlan('pro_plus_monthly')}
                              disabled={billingActionLoading}
                              className="w-full gap-2 bg-purple-600 hover:bg-purple-700"
                            >
                              {billingActionLoading ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Sparkles className="h-4 w-4" />
                              )}
                              {tBilling('pricing.chooseProPlus') || 'Choose Pro+'}
                            </Button>
                          </div>
                        </div>
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => router.push('/pricing')}
                          className="gap-2 text-slate-500"
                        >
                          {tBilling('pricing.compareFeatures') || 'Compare all features'} <ArrowRight className="h-3 w-3" />
                        </Button>
                      </div>
                    )}

                    {/* PRO USERS: Show upgrade to Pro+ + Manage */}
                    {subscription?.is_paid && (subscription.plan_id === 'pro_monthly' || subscription.plan_id === 'pro_yearly' || subscription.plan_id === 'pro_solo' || subscription.plan_id === 'light_solo') && (
                      <div className="space-y-4">
                        <div className="flex flex-wrap gap-3">
                          <Button 
                            variant="outline" 
                            onClick={handleManageSubscription}
                            disabled={billingActionLoading}
                            className="gap-2"
                          >
                            {billingActionLoading ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <ExternalLink className="h-4 w-4" />
                            )}
                            {tBilling('manageSubscription')}
                          </Button>
                          <Button 
                            onClick={() => handleUpgradeToPlan('pro_plus_monthly')}
                            disabled={billingActionLoading}
                            className="gap-2 bg-purple-600 hover:bg-purple-700"
                          >
                            {billingActionLoading ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Crown className="h-4 w-4" />
                            )}
                            {tBilling('pricing.goProPlus') || 'Upgrade to Pro+'}
                          </Button>
                        </div>
                        <p className="text-xs text-slate-500">
                          Pro+ includes AI Notetaker — automatically joins & records your meetings
                        </p>
                      </div>
                    )}

                    {/* PRO+ USERS: Only Manage */}
                    {subscription?.is_paid && (subscription.plan_id === 'pro_plus_monthly' || subscription.plan_id === 'pro_plus_yearly' || subscription.plan_id === 'unlimited_solo') && (
                      <div className="flex items-center gap-3">
                        <Button 
                          variant="outline" 
                          onClick={handleManageSubscription}
                          disabled={billingActionLoading}
                          className="gap-2"
                        >
                          {billingActionLoading ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <ExternalLink className="h-4 w-4" />
                          )}
                          {tBilling('manageSubscription')}
                        </Button>
                        <span className="text-sm text-green-600 dark:text-green-400 flex items-center gap-1">
                          <Check className="h-4 w-4" />
                          {tBilling('pricing.bestPlan') || 'You have the complete package!'}
                        </span>
                      </div>
                    )}
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Integrations */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Link className="h-5 w-5 text-purple-500" />
                <CardTitle>{t('sections.integrations')}</CardTitle>
              </div>
              <CardDescription>
                {tIntegrations('subtitle')}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Calendar Integrations */}
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-blue-500" />
                  <h4 className="text-sm font-medium text-slate-900 dark:text-white">
                    {tIntegrations('calendar.title')}
                  </h4>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {tIntegrations('calendar.description')}
                </p>
                
                {calendarLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
                    <span className="ml-2 text-sm text-slate-500">{tIntegrations('status.checking')}</span>
                  </div>
                ) : calendarError ? (
                  <div className="flex items-center justify-between p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                    <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
                      <AlertCircle className="h-4 w-4" />
                      <span className="text-sm">{tIntegrations('status.error')}</span>
                    </div>
                    <Button variant="ghost" size="sm" onClick={fetchCalendarStatus} className="gap-1">
                      <RefreshCw className="h-3 w-3" />
                      {tIntegrations('status.retry')}
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {/* Google Calendar */}
                    <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-white dark:bg-slate-700 flex items-center justify-center shadow-sm">
                          <svg className="w-5 h-5" viewBox="0 0 24 24">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                          </svg>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-900 dark:text-white">
                            {tIntegrations('calendar.google')}
                          </p>
                          {calendarStatus?.google.connected ? (
                            <p className="text-xs text-slate-500">
                              {calendarStatus.google.email} • {tIntegrations('calendar.meetingsCount', { count: calendarStatus.google.meeting_count })}
                            </p>
                          ) : (
                            <p className="text-xs text-slate-400">{tIntegrations('calendar.notConnected')}</p>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        {calendarStatus?.google.connected ? (
                          <>
                            {calendarStatus.google.needs_reauth ? (
                              <Button 
                                variant="outline" 
                                size="sm" 
                                onClick={handleGoogleConnect}
                                disabled={googleConnecting}
                                className="gap-1 text-amber-600 border-amber-300"
                              >
                                {googleConnecting ? (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                  <AlertCircle className="h-3 w-3" />
                                )}
                                {tIntegrations('calendar.reconnect')}
                              </Button>
                            ) : (
                              <>
                                <div className="flex items-center gap-2">
                                  <Badge variant="secondary" className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                                    <Check className="h-3 w-3 mr-1" />
                                    {tIntegrations('calendar.connected')}
                                  </Badge>
                                  <Button 
                                    variant="ghost" 
                                    size="sm" 
                                    onClick={() => handleCalendarDisconnect('google')}
                                    disabled={disconnecting === 'google' || calendarSyncing}
                                    className="h-7 w-7 p-0 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                                  >
                                    {disconnecting === 'google' ? (
                                      <Loader2 className="h-3 w-3 animate-spin" />
                                    ) : (
                                      <Power className="h-3 w-3" />
                                    )}
                                  </Button>
                                </div>
                                <Button 
                                  variant="outline" 
                                  size="sm" 
                                  onClick={handleCalendarSync}
                                  disabled={calendarSyncing || disconnecting === 'google'}
                                  className="gap-1"
                                >
                                  {calendarSyncing ? (
                                    <>
                                      <Loader2 className="h-3 w-3 animate-spin" />
                                      {tIntegrations('calendar.syncing')}
                                    </>
                                  ) : (
                                    <>
                                      <RefreshCw className="h-3 w-3" />
                                      {tIntegrations('calendar.syncNow')}
                                    </>
                                  )}
                                </Button>
                              </>
                            )}
                          </>
                        ) : (
                          <Button 
                            variant="outline" 
                            size="sm" 
                            onClick={handleGoogleConnect}
                            disabled={googleConnecting}
                            className="gap-1"
                          >
                            {googleConnecting ? (
                              <>
                                <Loader2 className="h-3 w-3 animate-spin" />
                                {tCommon('loading')}
                              </>
                            ) : (
                              tIntegrations('calendar.connect')
                            )}
                          </Button>
                        )}
                      </div>
                    </div>
                    
                    {/* Microsoft 365 */}
                    <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-white dark:bg-slate-700 flex items-center justify-center shadow-sm">
                          <svg className="w-5 h-5" viewBox="0 0 24 24">
                            <path fill="#f25022" d="M1 1h10v10H1z"/>
                            <path fill="#00a4ef" d="M1 13h10v10H1z"/>
                            <path fill="#7fba00" d="M13 1h10v10H13z"/>
                            <path fill="#ffb900" d="M13 13h10v10H13z"/>
                          </svg>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-900 dark:text-white">
                            {tIntegrations('calendar.microsoft')}
                          </p>
                          {calendarStatus?.microsoft.connected ? (
                            <p className="text-xs text-slate-500">
                              {calendarStatus.microsoft.email} • {tIntegrations('calendar.meetingsCount', { count: calendarStatus.microsoft.meeting_count })}
                            </p>
                          ) : (
                            <p className="text-xs text-slate-400">{tIntegrations('calendar.notConnected')}</p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {calendarStatus?.microsoft.connected ? (
                          <>
                            <div className="flex items-center gap-2">
                              <Badge variant="secondary" className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                                <Check className="h-3 w-3 mr-1" />
                                {tIntegrations('calendar.connected')}
                              </Badge>
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                onClick={() => handleCalendarDisconnect('microsoft')}
                                disabled={disconnecting === 'microsoft' || calendarSyncing}
                                className="h-7 w-7 p-0 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                              >
                                {disconnecting === 'microsoft' ? (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                  <Power className="h-3 w-3" />
                                )}
                              </Button>
                            </div>
                          </>
                        ) : (
                          <Button 
                            variant="outline" 
                            size="sm" 
                            onClick={handleMicrosoftConnect}
                            disabled={microsoftConnecting}
                            className="gap-1"
                          >
                            {microsoftConnecting ? (
                              <>
                                <Loader2 className="h-3 w-3 animate-spin" />
                                {tCommon('loading')}
                              </>
                            ) : (
                              tIntegrations('calendar.connect')
                            )}
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
              
              {/* Recording Integrations */}
              <div className="pt-4 border-t border-slate-200 dark:border-slate-700 space-y-4">
                <div className="flex items-center gap-2">
                  <Mic className="h-4 w-4 text-pink-500" />
                  <h4 className="text-sm font-medium text-slate-900 dark:text-white">
                    {tIntegrations('recordings.title')}
                  </h4>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {tIntegrations('recordings.description')}
                </p>
                
                {integrationsLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
                    <span className="ml-2 text-sm text-slate-500">{tIntegrations('status.checking')}</span>
                  </div>
                ) : (
                <div className="space-y-3">
                  {/* Fireflies.ai - Now functional */}
                  <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center shadow-sm">
                          <span className="text-white text-xs font-bold">🔥</span>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-900 dark:text-white">
                            {tIntegrations('recordings.fireflies')}
                          </p>
                          {integrationsStatus?.fireflies.connected ? (
                            <p className="text-xs text-slate-500">
                              {integrationsStatus.fireflies.account_email || integrationsStatus.fireflies.account_name}
                              {integrationsStatus.fireflies.pending_recordings > 0 && (
                                <span className="ml-1 text-amber-500">
                                  • {integrationsStatus.fireflies.pending_recordings} pending
                                </span>
                              )}
                            </p>
                          ) : (
                            <p className="text-xs text-slate-400">{tIntegrations('recordings.notConnected')}</p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {integrationsStatus?.fireflies.connected ? (
                          <>
                            <Badge variant="secondary" className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                              <Check className="h-3 w-3 mr-1" />
                              {tIntegrations('calendar.connected')}
                            </Badge>
                            <Button 
                              variant="ghost" 
                              size="sm" 
                              onClick={handleFirefliesDisconnect}
                              disabled={firefliesDisconnecting}
                              className="h-7 w-7 p-0 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                            >
                              {firefliesDisconnecting ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                <Power className="h-3 w-3" />
                              )}
                            </Button>
                          </>
                        ) : (
                          <Button 
                            variant="outline" 
                            size="sm" 
                            onClick={() => setShowFirefliesInput(!showFirefliesInput)}
                            className="gap-1"
                          >
                            {showFirefliesInput ? 'Cancel' : tIntegrations('recordings.connect')}
                          </Button>
                        )}
                      </div>
                    </div>
                    
                    {/* API Key Input - shown when connecting */}
                    {showFirefliesInput && !integrationsStatus?.fireflies.connected && (
                      <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-700">
                        <div className="space-y-2">
                          <label className="text-xs font-medium text-slate-600 dark:text-slate-400">
                            Fireflies API Key
                          </label>
                          <p className="text-xs text-slate-400">
                            Get your API key from{' '}
                            <a 
                              href="https://app.fireflies.ai/settings#DeveloperSettings" 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="text-blue-500 hover:underline"
                            >
                              Fireflies Settings → Developer Settings
                            </a>
                          </p>
                          <div className="flex gap-2">
                            <input
                              type="password"
                              value={firefliesApiKey}
                              onChange={(e) => setFirefliesApiKey(e.target.value)}
                              placeholder="ff_xxxxxxxxxxxxxxxx"
                              className="flex-1 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm"
                            />
                            <Button
                              size="sm"
                              onClick={handleFirefliesConnect}
                              disabled={firefliesConnecting || !firefliesApiKey.trim()}
                              className="gap-1"
                            >
                              {firefliesConnecting ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Check className="h-4 w-4" />
                              )}
                              Connect
                            </Button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {/* Zoom - Coming in Phase 3 */}
                  <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 opacity-60">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-[#2D8CFF] flex items-center justify-center shadow-sm">
                        <span className="text-white text-xs font-bold">Z</span>
                      </div>
                      <div>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">
                          {tIntegrations('recordings.zoom')}
                        </p>
                        <p className="text-xs text-slate-400">{tIntegrations('recordings.notConnected')}</p>
                      </div>
                    </div>
                    <Button variant="outline" size="sm" disabled className="gap-1">
                      {tIntegrations('recordings.connect')}
                      <Badge variant="secondary" className="text-xs ml-1">Soon</Badge>
                    </Button>
                  </div>
                  
                  {/* Microsoft Teams - Uses Microsoft Calendar connection */}
                  <div className={`flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 ${!calendarStatus?.microsoft.connected ? 'opacity-60' : ''}`}>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-[#6264A7] flex items-center justify-center shadow-sm">
                        <span className="text-white text-xs font-bold">T</span>
                      </div>
                      <div>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">
                          {tIntegrations('recordings.teams')}
                        </p>
                        {calendarStatus?.microsoft.connected ? (
                          <p className="text-xs text-slate-500">
                            {calendarStatus.microsoft.email} • {integrationsStatus?.teams.pending_recordings || 0} pending
                          </p>
                        ) : (
                          <p className="text-xs text-slate-400">Connect Microsoft 365 Calendar first</p>
                        )}
                      </div>
                    </div>
                    {calendarStatus?.microsoft.connected ? (
                      <Badge variant="secondary" className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                        <Check className="h-3 w-3 mr-1" />
                        {tIntegrations('recordings.connected')}
                      </Badge>
                    ) : (
                      <Button variant="outline" size="sm" disabled className="gap-1">
                        {tIntegrations('recordings.connect')}
                      </Button>
                    )}
                  </div>
                </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Auto-Record Settings */}
          <AutoRecordSettings />

          {/* Coming Soon: Notifications */}
          <Card className="opacity-60">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Bell className="h-5 w-5 text-orange-500" />
                <CardTitle className="flex items-center gap-2">
                  {t('sections.notifications')}
                  <Badge variant="secondary" className="text-xs">
                    {t('comingSoon')}
                  </Badge>
                </CardTitle>
              </div>
              <CardDescription>
                {t('notifications.description')}
              </CardDescription>
            </CardHeader>
          </Card>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}

