'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { 
  Shield, 
  Download, 
  Trash2, 
  Loader2, 
  ExternalLink,
  Check,
  Clock,
  AlertTriangle,
  FileText,
  User,
  Building2,
  Calendar,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  X
} from 'lucide-react'
import { useTranslations } from 'next-intl'
import { useToast } from '@/components/ui/use-toast'
import { useConfirmDialog } from '@/components/confirm-dialog'
import { api } from '@/lib/api'
import { logger } from '@/lib/logger'

interface DataCategory {
  category: string
  description: string
  count: number
  last_updated: string | null
}

interface DataSummary {
  user_id: string
  email: string
  account_created_at: string
  has_sales_profile: boolean
  has_company_profile: boolean
  data_categories: DataCategory[]
  connected_calendars: string[]
  connected_integrations: string[]
  subscription_plan: string
  subscription_status: string
}

interface ExportStatus {
  export_id: string
  status: 'pending' | 'processing' | 'ready' | 'downloaded' | 'expired' | 'failed'
  requested_at: string
  completed_at: string | null
  download_url: string | null
  download_expires_at: string | null
  file_size_bytes: number | null
  expires_at: string | null
}

interface DeletionStatus {
  has_pending_deletion: boolean
  deletion_request_id: string | null
  status: string | null
  scheduled_for: string | null
  can_cancel: boolean
  requested_at: string | null
  reason: string | null
}

export function PrivacySettings() {
  const router = useRouter()
  const t = useTranslations('settings.privacy')
  const tCommon = useTranslations('common')
  const tErrors = useTranslations('errors')
  const { toast } = useToast()
  const { confirm } = useConfirmDialog()
  
  const [dataSummary, setDataSummary] = useState<DataSummary | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(true)
  const [summaryExpanded, setSummaryExpanded] = useState(false)
  
  const [exportStatus, setExportStatus] = useState<ExportStatus | null>(null)
  const [exportLoading, setExportLoading] = useState(false)
  const [exportPolling, setExportPolling] = useState(false)
  
  const [deletionStatus, setDeletionStatus] = useState<DeletionStatus | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleteReason, setDeleteReason] = useState('')
  
  // Fetch data summary
  const fetchDataSummary = useCallback(async () => {
    try {
      const { data, error } = await api.get<DataSummary>('/api/v1/user/data-summary')
      if (!error && data) {
        setDataSummary(data)
      }
    } catch (err) {
      logger.error('Failed to fetch data summary', err, { source: 'PrivacySettings' })
    } finally {
      setSummaryLoading(false)
    }
  }, [])
  
  // Fetch deletion status
  const fetchDeletionStatus = useCallback(async () => {
    try {
      const { data, error } = await api.get<DeletionStatus>('/api/v1/user/delete/status')
      if (!error && data) {
        setDeletionStatus(data)
      }
    } catch (err) {
      logger.error('Failed to fetch deletion status', err, { source: 'PrivacySettings' })
    }
  }, [])
  
  // Fetch latest export status
  const fetchExportStatus = useCallback(async () => {
    try {
      const { data, error } = await api.get<{ exports: ExportStatus[], total: number }>('/api/v1/user/exports')
      if (!error && data && data.exports.length > 0) {
        // Get the most recent export
        const latestExport = data.exports[0]
        setExportStatus(latestExport)
        
        // If processing, continue polling
        if (latestExport.status === 'pending' || latestExport.status === 'processing') {
          setExportPolling(true)
        } else {
          setExportPolling(false)
        }
      }
    } catch (err) {
      logger.error('Failed to fetch export status', err, { source: 'PrivacySettings' })
    }
  }, [])
  
  useEffect(() => {
    fetchDataSummary()
    fetchDeletionStatus()
    fetchExportStatus()
  }, [fetchDataSummary, fetchDeletionStatus, fetchExportStatus])
  
  // Poll for export status when processing
  useEffect(() => {
    if (!exportPolling) return
    
    const interval = setInterval(() => {
      fetchExportStatus()
    }, 5000) // Poll every 5 seconds
    
    return () => clearInterval(interval)
  }, [exportPolling, fetchExportStatus])
  
  // Handle data export request
  const handleRequestExport = async () => {
    setExportLoading(true)
    try {
      const { data, error } = await api.post<{ 
        success: boolean
        export_id: string
        message?: string
        rate_limited?: boolean
        already_ready?: boolean
        hours_remaining?: number
      }>('/api/v1/user/export', {})
      
      if (error) {
        throw new Error(error.message || 'Export request failed')
      }
      
      // Handle rate limiting
      if (data?.rate_limited) {
        toast({
          title: t('downloadData.rateLimited'),
          description: t('downloadData.rateLimitedDesc', { hours: data.hours_remaining || 24 }),
          variant: 'destructive',
        })
        return
      }
      
      // If export is already ready, just refresh
      if (data?.already_ready) {
        toast({
          title: t('downloadData.alreadyReady'),
          description: t('downloadData.alreadyReadyDesc'),
        })
        fetchExportStatus()
        return
      }
      
      toast({
        title: t('downloadData.requested'),
        description: t('downloadData.requestedDesc'),
      })
      
      // Start polling for status
      setExportPolling(true)
      fetchExportStatus()
      
    } catch (err) {
      logger.error('Export request failed', err, { source: 'PrivacySettings' })
      toast({
        title: t('downloadData.failed'),
        description: t('downloadData.failedDesc'),
        variant: 'destructive',
      })
    } finally {
      setExportLoading(false)
    }
  }
  
  // Handle download click
  const handleDownload = async () => {
    if (!exportStatus?.download_url) return
    
    try {
      // Record the download
      await api.post(`/api/v1/user/export/${exportStatus.export_id}/download`, {})
      
      // Open download URL
      window.open(exportStatus.download_url, '_blank')
    } catch (err) {
      logger.error('Download tracking failed', err, { source: 'PrivacySettings' })
    }
  }
  
  // Handle retry export (for stuck exports)
  const handleRetryExport = async () => {
    if (!exportStatus) return
    
    setExportLoading(true)
    try {
      const { data, error } = await api.post<{ success: boolean; export_id: string }>(
        `/api/v1/user/export/${exportStatus.export_id}/retry`, 
        {}
      )
      
      if (error) {
        throw new Error(error.message || 'Retry failed')
      }
      
      toast({
        title: t('downloadData.requested'),
        description: t('downloadData.requestedDesc'),
      })
      
      // Start polling for status
      setExportPolling(true)
      fetchExportStatus()
      
    } catch (err) {
      logger.error('Export retry failed', err, { source: 'PrivacySettings' })
      toast({
        title: t('downloadData.failed'),
        description: t('downloadData.failedDesc'),
        variant: 'destructive',
      })
    } finally {
      setExportLoading(false)
    }
  }
  
  // Handle cancel export
  const handleCancelExport = async () => {
    if (!exportStatus) return
    
    try {
      await api.delete(`/api/v1/user/export/${exportStatus.export_id}`)
      
      toast({
        title: 'Export cancelled',
      })
      
      setExportStatus(null)
      setExportPolling(false)
      
    } catch (err) {
      logger.error('Export cancel failed', err, { source: 'PrivacySettings' })
    }
  }
  
  // Check if export is stuck (pending/processing for more than 2 minutes)
  const isExportStuck = exportStatus && 
    (exportStatus.status === 'pending' || exportStatus.status === 'processing') &&
    new Date().getTime() - new Date(exportStatus.requested_at).getTime() > 2 * 60 * 1000
  
  // Handle account deletion request
  const handleRequestDeletion = async () => {
    const confirmed = await confirm({
      title: t('deleteAccount.confirmTitle'),
      description: t('deleteAccount.confirmDesc'),
      confirmLabel: t('deleteAccount.confirmButton'),
      cancelLabel: t('deleteAccount.cancelButton'),
      variant: 'danger',
    })
    
    if (!confirmed) return
    
    setDeleteLoading(true)
    try {
      const { data, error } = await api.post<{ success: boolean; scheduled_for: string }>('/api/v1/user/delete', {
        confirm: true,
        reason: deleteReason || undefined,
      })
      
      if (error) {
        throw new Error(error.message || 'Deletion request failed')
      }
      
      toast({
        title: t('deleteAccount.scheduled'),
        description: t('deleteAccount.scheduledDesc', { 
          date: new Date(data?.scheduled_for || '').toLocaleDateString() 
        }),
      })
      
      // Refresh deletion status
      fetchDeletionStatus()
      
    } catch (err) {
      logger.error('Deletion request failed', err, { source: 'PrivacySettings' })
      toast({
        title: t('deleteAccount.failed'),
        description: t('deleteAccount.failedDesc'),
        variant: 'destructive',
      })
    } finally {
      setDeleteLoading(false)
    }
  }
  
  // Handle deletion cancellation
  const handleCancelDeletion = async () => {
    setDeleteLoading(true)
    try {
      const { error } = await api.post('/api/v1/user/delete/cancel', {})
      
      if (error) {
        throw new Error(error.message || 'Cancellation failed')
      }
      
      toast({
        title: t('deleteAccount.cancelled'),
        description: t('deleteAccount.cancelledDesc'),
      })
      
      // Refresh deletion status
      fetchDeletionStatus()
      
    } catch (err) {
      logger.error('Deletion cancellation failed', err, { source: 'PrivacySettings' })
      toast({
        title: tErrors('generic'),
        variant: 'destructive',
      })
    } finally {
      setDeleteLoading(false)
    }
  }
  
  const formatDate = (dateString: string | null) => {
    if (!dateString) return '-'
    return new Date(dateString).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }
  
  const formatFileSize = (bytes: number | null) => {
    if (!bytes) return '-'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }
  
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-teal-500" />
          <CardTitle>{t('title')}</CardTitle>
        </div>
        <CardDescription>
          {t('description')}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Data Overview Section */}
        <div className="space-y-4">
          <div 
            className="flex items-center justify-between cursor-pointer"
            onClick={() => setSummaryExpanded(!summaryExpanded)}
          >
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-slate-400" />
              <h4 className="text-sm font-medium text-slate-900 dark:text-white">
                {t('dataOverview.title')}
              </h4>
            </div>
            <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
              {summaryExpanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          </div>
          
          {summaryExpanded && (
            <div className="space-y-4 animate-in slide-in-from-top-2">
              {summaryLoading ? (
                <div className="flex items-center justify-center py-6">
                  <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
                </div>
              ) : dataSummary ? (
                <>
                  {/* Account Info */}
                  <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-500">{t('dataOverview.accountCreated')}</span>
                      <span className="font-medium text-slate-900 dark:text-white">
                        {formatDate(dataSummary.account_created_at)}
                      </span>
                    </div>
                  </div>
                  
                  {/* Profiles */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                      <div className="flex items-center gap-2 mb-1">
                        <User className="h-4 w-4 text-blue-500" />
                        <span className="text-xs text-slate-500">{t('dataOverview.salesProfile')}</span>
                      </div>
                      <Badge variant={dataSummary.has_sales_profile ? "secondary" : "outline"} className={dataSummary.has_sales_profile ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" : ""}>
                        {dataSummary.has_sales_profile ? (
                          <><Check className="h-3 w-3 mr-1" />{t('dataOverview.completed')}</>
                        ) : t('dataOverview.notCompleted')}
                      </Badge>
                    </div>
                    <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                      <div className="flex items-center gap-2 mb-1">
                        <Building2 className="h-4 w-4 text-purple-500" />
                        <span className="text-xs text-slate-500">{t('dataOverview.companyProfile')}</span>
                      </div>
                      <Badge variant={dataSummary.has_company_profile ? "secondary" : "outline"} className={dataSummary.has_company_profile ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" : ""}>
                        {dataSummary.has_company_profile ? (
                          <><Check className="h-3 w-3 mr-1" />{t('dataOverview.completed')}</>
                        ) : t('dataOverview.notCompleted')}
                      </Badge>
                    </div>
                  </div>
                  
                  {/* Data Categories */}
                  {dataSummary.data_categories.length > 0 && (
                    <div className="space-y-2">
                      {dataSummary.data_categories.map((cat) => (
                        <div key={cat.category} className="flex items-center justify-between text-sm py-1">
                          <span className="text-slate-600 dark:text-slate-400">{cat.category}</span>
                          <span className="font-medium text-slate-900 dark:text-white">
                            {cat.count}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* Connected Services */}
                  {(dataSummary.connected_calendars.length > 0 || dataSummary.connected_integrations.length > 0) && (
                    <div className="pt-2 border-t border-slate-200 dark:border-slate-700">
                      <div className="flex items-center gap-2 mb-2">
                        <Calendar className="h-4 w-4 text-slate-400" />
                        <span className="text-xs text-slate-500">{t('dataOverview.connections')}</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {dataSummary.connected_calendars.map((cal) => (
                          <Badge key={cal} variant="outline" className="text-xs">
                            {cal}
                          </Badge>
                        ))}
                        {dataSummary.connected_integrations.map((int) => (
                          <Badge key={int} variant="outline" className="text-xs">
                            {int}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-slate-500 text-center py-4">
                  {tErrors('generic')}
                </p>
              )}
            </div>
          )}
        </div>
        
        {/* Download Data Section */}
        <div className="pt-4 border-t border-slate-200 dark:border-slate-700 space-y-4">
          <div>
            <div className="flex items-center gap-2">
              <Download className="h-4 w-4 text-blue-500" />
              <h4 className="text-sm font-medium text-slate-900 dark:text-white">
                {t('downloadData.title')}
              </h4>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              {t('downloadData.description')}
            </p>
          </div>
          
          {/* Export Status */}
          {exportStatus && (
            <div className={`p-3 rounded-lg border ${
              exportStatus.status === 'ready' 
                ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800' 
                : exportStatus.status === 'failed' || exportStatus.status === 'expired'
                  ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                  : isExportStuck
                    ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800'
                    : 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
            }`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {exportStatus.status === 'ready' && <Check className="h-4 w-4 text-green-600" />}
                  {(exportStatus.status === 'pending' || exportStatus.status === 'processing') && !isExportStuck && (
                    <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                  )}
                  {isExportStuck && (
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                  )}
                  {(exportStatus.status === 'failed' || exportStatus.status === 'expired') && (
                    <AlertTriangle className="h-4 w-4 text-red-600" />
                  )}
                  <span className="text-sm font-medium">
                    {exportStatus.status === 'ready' && t('downloadData.ready')}
                    {(exportStatus.status === 'pending' || exportStatus.status === 'processing') && !isExportStuck && t('downloadData.processing')}
                    {isExportStuck && t('downloadData.stuck')}
                    {exportStatus.status === 'failed' && t('downloadData.failed')}
                    {exportStatus.status === 'expired' && t('downloadData.expired')}
                  </span>
                </div>
                {exportStatus.status === 'ready' && exportStatus.file_size_bytes && (
                  <span className="text-xs text-slate-500">
                    {formatFileSize(exportStatus.file_size_bytes)}
                  </span>
                )}
              </div>
              
              {exportStatus.status === 'ready' && (
                <>
                  {/* Expiration info */}
                  {exportStatus.expires_at && (
                    <p className="text-xs text-green-600 dark:text-green-400 mt-1 flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {t('downloadData.expiresIn', { 
                        hours: Math.max(1, Math.round((new Date(exportStatus.expires_at).getTime() - Date.now()) / (1000 * 60 * 60)))
                      })}
                    </p>
                  )}
                  
                  {exportStatus.download_url && (
                    <Button 
                      size="sm" 
                      className="w-full mt-3 gap-2"
                      onClick={handleDownload}
                    >
                      <Download className="h-4 w-4" />
                      {t('downloadData.download')}
                    </Button>
                  )}
                </>
              )}
              
              {/* Retry/Cancel buttons for stuck or failed exports */}
              {(isExportStuck || exportStatus.status === 'failed') && (
                <div className="flex gap-2 mt-3">
                  <Button 
                    size="sm"
                    variant="outline"
                    className="flex-1 gap-2"
                    onClick={handleRetryExport}
                    disabled={exportLoading}
                  >
                    {exportLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4" />
                    )}
                    {t('downloadData.retry')}
                  </Button>
                  <Button 
                    size="sm"
                    variant="ghost"
                    className="gap-2"
                    onClick={handleCancelExport}
                  >
                    <X className="h-4 w-4" />
                    {t('downloadData.cancel')}
                  </Button>
                </div>
              )}
            </div>
          )}
          
          {/* Don't show button if there's already a ready export */}
          {(!exportStatus || exportStatus.status !== 'ready') && (
            <Button
              variant="outline"
              onClick={handleRequestExport}
              disabled={exportLoading || exportPolling}
              className="gap-2"
            >
              {exportLoading || exportPolling ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t('downloadData.requesting')}
                </>
              ) : (
                <>
                  <Download className="h-4 w-4" />
                  {t('downloadData.button')}
              </>
            )}
          </Button>
          )}
          
          {/* Rate limit info */}
          <p className="text-xs text-slate-400 dark:text-slate-500 flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {t('downloadData.rateInfo')}
          </p>
        </div>
        
        {/* Legal Documents */}
        <div className="pt-4 border-t border-slate-200 dark:border-slate-700 space-y-3">
          <h4 className="text-sm font-medium text-slate-900 dark:text-white flex items-center gap-2">
            <FileText className="h-4 w-4 text-slate-400" />
            {t('legal.title')}
          </h4>
          
          <div className="grid grid-cols-2 gap-3">
            <a 
              href="/privacy" 
              target="_blank"
              className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 transition-colors"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-slate-900 dark:text-white">
                  {t('legal.privacyPolicy')}
                </span>
                <ExternalLink className="h-3 w-3 text-slate-400" />
              </div>
              <p className="text-xs text-slate-500">{t('legal.privacyPolicyDesc')}</p>
            </a>
            <a 
              href="/terms" 
              target="_blank"
              className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 transition-colors"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-slate-900 dark:text-white">
                  {t('legal.terms')}
                </span>
                <ExternalLink className="h-3 w-3 text-slate-400" />
              </div>
              <p className="text-xs text-slate-500">{t('legal.termsDesc')}</p>
            </a>
          </div>
        </div>
        
        {/* Delete Account Section */}
        <div className="pt-4 border-t border-slate-200 dark:border-slate-700 space-y-4">
          <div>
            <div className="flex items-center gap-2">
              <Trash2 className="h-4 w-4 text-red-500" />
              <h4 className="text-sm font-medium text-slate-900 dark:text-white">
                {t('deleteAccount.title')}
              </h4>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              {t('deleteAccount.description')}
            </p>
          </div>
          
          {/* Pending Deletion Status */}
          {deletionStatus?.has_pending_deletion && (
            <div className="p-4 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="h-4 w-4 text-amber-600" />
                <span className="text-sm font-medium text-amber-800 dark:text-amber-200">
                  {t('deleteAccount.scheduled')}
                </span>
              </div>
              <p className="text-sm text-amber-700 dark:text-amber-300 mb-3">
                {t('deleteAccount.scheduledDesc', { 
                  date: formatDate(deletionStatus.scheduled_for) 
                })}
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancelDeletion}
                disabled={deleteLoading}
                className="gap-2 border-amber-300 text-amber-700 hover:bg-amber-100 dark:border-amber-700 dark:text-amber-300"
              >
                {deleteLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {t('deleteAccount.cancelling')}
                  </>
                ) : (
                  t('deleteAccount.cancelDeletion')
                )}
              </Button>
            </div>
          )}
          
          {/* What happens when you delete */}
          {!deletionStatus?.has_pending_deletion && (
            <>
              <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800/50">
                <p className="text-xs font-medium text-red-800 dark:text-red-200 mb-2">
                  {t('deleteAccount.whatHappens')}
                </p>
                <ul className="text-xs text-red-700 dark:text-red-300 space-y-1 list-disc list-inside">
                  <li>{t('deleteAccount.deleteProfile')}</li>
                  <li>{t('deleteAccount.deleteContent')}</li>
                  <li>{t('deleteAccount.deleteFiles')}</li>
                  <li>{t('deleteAccount.anonBilling')}</li>
                </ul>
              </div>
              
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Clock className="h-3 w-3" />
                <span>{t('deleteAccount.gracePeriod')}: {t('deleteAccount.gracePeriodDesc')}</span>
              </div>
              
              <Button
                variant="destructive"
                onClick={handleRequestDeletion}
                disabled={deleteLoading}
                className="gap-2"
              >
                {deleteLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {t('deleteAccount.processing')}
                  </>
                ) : (
                  <>
                    <Trash2 className="h-4 w-4" />
                    {t('deleteAccount.button')}
                  </>
                )}
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

