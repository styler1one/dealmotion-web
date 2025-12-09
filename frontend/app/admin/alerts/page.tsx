'use client'

import { useEffect, useState, useCallback } from 'react'
import { adminApi } from '@/lib/admin-api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'
import type { AdminAlert, AlertListResponse } from '@/types/admin'

export default function AdminAlertsPage() {
  const [alerts, setAlerts] = useState<AdminAlert[]>([])
  const [activeCount, setActiveCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('active')
  const [severityFilter, setSeverityFilter] = useState<string>('')
  const [selectedAlert, setSelectedAlert] = useState<AdminAlert | null>(null)
  const [resolveNotes, setResolveNotes] = useState('')
  const [actionLoading, setActionLoading] = useState(false)

  const fetchAlerts = useCallback(async () => {
    try {
      setLoading(true)
      const data = await adminApi.listAlerts({
        status: statusFilter || undefined,
        severity: severityFilter || undefined,
        limit: 100,
      })
      setAlerts(data.alerts)
      setActiveCount(data.activeCount)
    } catch (err) {
      console.error('Failed to fetch alerts:', err)
    } finally {
      setLoading(false)
    }
  }, [statusFilter, severityFilter])

  useEffect(() => {
    fetchAlerts()
  }, [fetchAlerts])

  const handleAcknowledge = async (alertId: string) => {
    setActionLoading(true)
    try {
      await adminApi.acknowledgeAlert(alertId)
      fetchAlerts()
    } catch (err) {
      console.error('Failed to acknowledge:', err)
    } finally {
      setActionLoading(false)
    }
  }

  const handleResolve = async () => {
    if (!selectedAlert) return
    setActionLoading(true)
    try {
      await adminApi.resolveAlert(selectedAlert.id, { notes: resolveNotes })
      setSelectedAlert(null)
      setResolveNotes('')
      fetchAlerts()
    } catch (err) {
      console.error('Failed to resolve:', err)
    } finally {
      setActionLoading(false)
    }
  }

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical': return <Icons.alertCircle className="h-5 w-5 text-red-500" />
      case 'error': return <Icons.alertTriangle className="h-5 w-5 text-orange-500" />
      case 'warning': return <Icons.alertTriangle className="h-5 w-5 text-yellow-500" />
      default: return <Icons.info className="h-5 w-5 text-blue-500" />
    }
  }

  const getSeverityBadge = (severity: string) => {
    const colors = {
      critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
      error: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
      warning: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
      info: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    }
    return (
      <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium capitalize', colors[severity as keyof typeof colors])}>
        {severity}
      </span>
    )
  }

  const getStatusBadge = (status: string) => {
    const colors = {
      active: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
      acknowledged: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
      resolved: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    }
    return (
      <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium capitalize', colors[status as keyof typeof colors])}>
        {status}
      </span>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Alerts</h1>
          <p className="text-sm text-slate-500">
            {activeCount} active alert{activeCount !== 1 ? 's' : ''}
          </p>
        </div>
        <Button onClick={fetchAlerts}>
          <Icons.refresh className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex gap-4">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-10 px-3 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
            >
              <option value="">All Status</option>
              <option value="active">Active</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="resolved">Resolved</option>
            </select>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="h-10 px-3 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
            >
              <option value="">All Severity</option>
              <option value="critical">Critical</option>
              <option value="error">Error</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Alerts List */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Icons.spinner className="h-6 w-6 animate-spin text-teal-500" />
            </div>
          ) : alerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-slate-500">
              <Icons.checkCircle className="h-12 w-12 text-green-500 mb-4" />
              <span>No alerts found</span>
            </div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {alerts.map((alert) => (
                <div 
                  key={alert.id}
                  className={cn(
                    'p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors',
                    alert.status === 'active' && 'bg-red-50/50 dark:bg-red-900/10'
                  )}
                >
                  <div className="flex items-start gap-4">
                    <div className="flex-shrink-0">
                      {getSeverityIcon(alert.severity)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-slate-900 dark:text-white">
                          {alert.title}
                        </span>
                        {getSeverityBadge(alert.severity)}
                        {getStatusBadge(alert.status)}
                      </div>
                      {alert.description && (
                        <p className="text-sm text-slate-500 mb-2">
                          {alert.description}
                        </p>
                      )}
                      <div className="flex items-center gap-4 text-xs text-slate-400">
                        <span>Type: {alert.alertType}</span>
                        {alert.targetName && <span>Target: {alert.targetName}</span>}
                        <span>{new Date(alert.createdAt).toLocaleString()}</span>
                      </div>
                      {alert.resolutionNotes && (
                        <div className="mt-2 p-2 bg-green-50 dark:bg-green-900/20 rounded text-sm text-green-700 dark:text-green-400">
                          Resolution: {alert.resolutionNotes}
                        </div>
                      )}
                    </div>
                    <div className="flex-shrink-0 flex gap-2">
                      {alert.status === 'active' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleAcknowledge(alert.id)}
                          disabled={actionLoading}
                        >
                          Acknowledge
                        </Button>
                      )}
                      {alert.status !== 'resolved' && (
                        <Button
                          size="sm"
                          onClick={() => setSelectedAlert(alert)}
                        >
                          Resolve
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Resolve Dialog */}
      {selectedAlert && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>Resolve Alert</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="font-medium">{selectedAlert.title}</div>
                <div className="text-sm text-slate-500">{selectedAlert.description}</div>
              </div>
              <Textarea
                placeholder="Resolution notes (optional)..."
                value={resolveNotes}
                onChange={(e) => setResolveNotes(e.target.value)}
              />
              <div className="flex gap-2 justify-end">
                <Button variant="outline" onClick={() => setSelectedAlert(null)}>
                  Cancel
                </Button>
                <Button onClick={handleResolve} disabled={actionLoading}>
                  {actionLoading ? <Icons.spinner className="h-4 w-4 animate-spin mr-2" /> : null}
                  Resolve
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}

