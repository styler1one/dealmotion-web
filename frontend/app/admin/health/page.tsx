'use client'

import { useEffect, useState, useMemo } from 'react'
import { adminApi } from '@/lib/admin-api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'
import type { 
  HealthOverview, 
  JobHealthResponse, 
  ServiceStatus, 
  JobStats,
  ServiceUptime,
  HealthTrendsResponse,
  IncidentsResponse,
  RecentIncident
} from '@/types/admin'

export default function AdminHealthPage() {
  const [health, setHealth] = useState<HealthOverview | null>(null)
  const [jobs, setJobs] = useState<JobHealthResponse | null>(null)
  const [uptime, setUptime] = useState<ServiceUptime[]>([])
  const [trends, setTrends] = useState<HealthTrendsResponse | null>(null)
  const [incidents, setIncidents] = useState<IncidentsResponse | null>(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('overview')
  
  // Track loading state per section for progressive loading
  const [loadingStates, setLoadingStates] = useState({
    jobs: true,
    uptime: true,
    trends: true,
    incidents: true,
    health: true,
  })

  const fetchData = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true)
      } else {
        setInitialLoading(true)
        setLoadingStates({ jobs: true, uptime: true, trends: true, incidents: true, health: true })
      }
      setError(null)
      
      // Fire all requests but update state as each completes (progressive loading)
      // Load fast endpoints first, slow health check last
      
      // Fast endpoints - load in parallel
      adminApi.getJobHealth()
        .then(data => {
          setJobs(data)
          setLoadingStates(prev => ({ ...prev, jobs: false }))
        })
        .catch(err => console.error('Failed to fetch jobs:', err))
      
      adminApi.getServiceUptime()
        .then(data => {
          setUptime(data)
          setLoadingStates(prev => ({ ...prev, uptime: false }))
        })
        .catch(err => console.error('Failed to fetch uptime:', err))
      
      adminApi.getHealthTrends(30)
        .then(data => {
          setTrends(data)
          setLoadingStates(prev => ({ ...prev, trends: false }))
        })
        .catch(err => console.error('Failed to fetch trends:', err))
      
      adminApi.getRecentIncidents(50)
        .then(data => {
          setIncidents(data)
          setLoadingStates(prev => ({ ...prev, incidents: false }))
        })
        .catch(err => console.error('Failed to fetch incidents:', err))
      
      // Slow endpoint - real-time health checks to external services
      adminApi.getHealthOverview()
        .then(data => {
          setHealth(data)
          setLoadingStates(prev => ({ ...prev, health: false }))
          setInitialLoading(false)
          setRefreshing(false)
        })
        .catch(err => {
          console.error('Failed to fetch health overview:', err)
          setError(err instanceof Error ? err.message : 'Failed to load health data')
          setInitialLoading(false)
          setRefreshing(false)
        })
        
    } catch (err) {
      console.error('Failed to fetch health data:', err)
      setError(err instanceof Error ? err.message : 'Failed to load health data')
      setInitialLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchData()
    // Auto-refresh every 60 seconds
    const interval = setInterval(() => fetchData(true), 60000)
    return () => clearInterval(interval)
  }, [])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <Icons.checkCircle className="h-5 w-5 text-emerald-500" />
      case 'degraded':
        return <Icons.alertTriangle className="h-5 w-5 text-amber-500" />
      case 'down':
        return <Icons.xCircle className="h-5 w-5 text-red-500" />
      default:
        return <Icons.helpCircle className="h-5 w-5 text-slate-400" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'text-emerald-500'
      case 'degraded': return 'text-amber-500'
      case 'down': return 'text-red-500'
      default: return 'text-slate-400'
    }
  }

  const getStatusBgColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-emerald-500'
      case 'degraded': return 'bg-amber-500'
      case 'down': return 'bg-red-500'
      default: return 'bg-slate-400'
    }
  }

  const getOverallStatusBadge = (status: string) => {
    const config = {
      healthy: { bg: 'bg-emerald-100 dark:bg-emerald-900/30', text: 'text-emerald-700 dark:text-emerald-400', label: 'All Systems Operational' },
      degraded: { bg: 'bg-amber-100 dark:bg-amber-900/30', text: 'text-amber-700 dark:text-amber-400', label: 'Partial Degradation' },
      down: { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-400', label: 'Major Outage' },
    }
    const c = config[status as keyof typeof config] || config.degraded
    return (
      <Badge className={cn(c.bg, c.text, 'font-medium')}>
        {c.label}
      </Badge>
    )
  }

  const getUptimeColor = (percent: number) => {
    if (percent >= 99.9) return 'text-emerald-500'
    if (percent >= 99) return 'text-emerald-400'
    if (percent >= 95) return 'text-amber-500'
    return 'text-red-500'
  }

  // Calculate uptime bars for mini chart
  const getUptimeBars = (serviceName: string) => {
    // Handle both camelCase and snake_case
    const serviceTrend = trends?.services.find(s => 
      (s.serviceName || (s as any).service_name) === serviceName
    )
    const trendData = serviceTrend?.trendData || (serviceTrend as any)?.trend_data || []
    if (!serviceTrend || trendData.length === 0) return []
    
    // Get last 30 days
    return trendData.slice(-30).map((d: any) => ({
      date: d.date,
      uptime: d.uptimePercent ?? d.uptime_percent ?? 100,
      incidents: d.incidentCount ?? d.incident_count ?? 0
    }))
  }

  // Section loading skeleton component
  const SectionSkeleton = ({ rows = 3 }: { rows?: number }) => (
    <div className="space-y-4 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 p-4 rounded-lg bg-slate-100 dark:bg-slate-800">
          <div className="w-12 h-12 rounded-full bg-slate-200 dark:bg-slate-700" />
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-1/3" />
            <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded w-2/3" />
          </div>
          <div className="h-6 w-16 bg-slate-200 dark:bg-slate-700 rounded" />
        </div>
      ))}
    </div>
  )

  if (error) {
    return (
      <div className="flex items-center justify-center py-24">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6 text-center">
            <Icons.alertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">Failed to load health data</h2>
            <p className="text-slate-500 mb-4">{error}</p>
            <Button onClick={() => fetchData()}>
              <Icons.refresh className="h-4 w-4 mr-2" />
              Try Again
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">System Health</h1>
          {health && (
            <div className="flex items-center gap-3 mt-2">
              {getOverallStatusBadge(health.overallStatus)}
              <span className="text-sm text-slate-500">
                Last updated: {new Date(health.lastUpdated).toLocaleTimeString()}
              </span>
            </div>
          )}
        </div>
        <Button onClick={() => fetchData(true)} disabled={refreshing}>
          <Icons.refresh className={cn("h-4 w-4 mr-2", refreshing && "animate-spin")} />
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </Button>
      </div>

      {/* Status Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-l-4 border-l-emerald-500">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">Healthy</p>
                <p className="text-3xl font-bold text-emerald-500">{health?.healthyCount || 0}</p>
              </div>
              <Icons.checkCircle className="h-10 w-10 text-emerald-100 dark:text-emerald-900" />
            </div>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-amber-500">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">Degraded</p>
                <p className="text-3xl font-bold text-amber-500">{health?.degradedCount || 0}</p>
              </div>
              <Icons.alertTriangle className="h-10 w-10 text-amber-100 dark:text-amber-900" />
            </div>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-red-500">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">Down</p>
                <p className="text-3xl font-bold text-red-500">{health?.downCount || 0}</p>
              </div>
              <Icons.xCircle className="h-10 w-10 text-red-100 dark:text-red-900" />
            </div>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-blue-500">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">Jobs Success (24h)</p>
                <p className={cn(
                  "text-3xl font-bold",
                  (jobs?.overallSuccessRate || 0) >= 95 ? 'text-emerald-500' :
                  (jobs?.overallSuccessRate || 0) >= 80 ? 'text-amber-500' : 'text-red-500'
                )}>
                  {jobs?.overallSuccessRate || 0}%
                </p>
              </div>
              <Icons.activity className="h-10 w-10 text-blue-100 dark:text-blue-900" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4 lg:w-auto lg:inline-grid">
          <TabsTrigger value="overview">Services</TabsTrigger>
          <TabsTrigger value="uptime">Uptime</TabsTrigger>
          <TabsTrigger value="jobs">Jobs</TabsTrigger>
          <TabsTrigger value="incidents">Incidents</TabsTrigger>
        </TabsList>

        {/* Services Tab */}
        <TabsContent value="overview" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Service Status</CardTitle>
              <CardDescription>Real-time health status of all external services</CardDescription>
            </CardHeader>
            <CardContent>
              {loadingStates.health ? (
                <SectionSkeleton rows={6} />
              ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {health?.services.map((service: ServiceStatus) => {
                  // Handle both camelCase and snake_case
                  const svc = service as any
                  const displayName = service.displayName || svc.display_name || service.name
                  const responseTime = service.responseTimeMs ?? svc.response_time_ms
                  const errorMsg = service.errorMessage || svc.error_message
                  const isCrit = service.isCritical ?? svc.is_critical
                  
                  return (
                    <div 
                      key={service.name}
                      className={cn(
                        'flex items-center gap-4 p-4 rounded-xl border transition-colors',
                        service.status === 'healthy' ? 'border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-900/10' :
                        service.status === 'degraded' ? 'border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-900/10' :
                        service.status === 'down' ? 'border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10' :
                        'border-slate-200 dark:border-slate-700'
                      )}
                    >
                      <div className={cn(
                        'flex items-center justify-center w-12 h-12 rounded-full',
                        service.status === 'healthy' ? 'bg-emerald-100 dark:bg-emerald-900/30' :
                        service.status === 'degraded' ? 'bg-amber-100 dark:bg-amber-900/30' :
                        service.status === 'down' ? 'bg-red-100 dark:bg-red-900/30' :
                        'bg-slate-100 dark:bg-slate-800'
                      )}>
                        {getStatusIcon(service.status)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-900 dark:text-white">
                            {displayName}
                          </span>
                          {isCrit && (
                            <Badge variant="outline" className="text-xs">Critical</Badge>
                          )}
                        </div>
                        <p className="text-sm text-slate-500 truncate">
                          {errorMsg || service.details || 'No details'}
                        </p>
                      </div>
                      <div className="text-right">
                        {responseTime ? (
                          <div className={cn(
                            'text-sm font-medium',
                            responseTime < 500 ? 'text-emerald-500' :
                            responseTime < 1000 ? 'text-amber-500' : 'text-red-500'
                          )}>
                            {responseTime}ms
                          </div>
                        ) : (
                          <div className="text-sm text-slate-400">—</div>
                        )}
                        <div className="text-xs text-slate-400 capitalize">{service.status}</div>
                      </div>
                    </div>
                  )
                })}
              </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Uptime Tab */}
        <TabsContent value="uptime" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Service Uptime</CardTitle>
              <CardDescription>Historical uptime percentages and response times</CardDescription>
            </CardHeader>
            <CardContent>
              {loadingStates.uptime ? (
                <SectionSkeleton rows={6} />
              ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-sm text-slate-500 border-b dark:border-slate-700">
                      <th className="pb-3 font-medium">Service</th>
                      <th className="pb-3 font-medium text-center">24h</th>
                      <th className="pb-3 font-medium text-center">7 days</th>
                      <th className="pb-3 font-medium text-center">30 days</th>
                      <th className="pb-3 font-medium text-center">Avg Response</th>
                      <th className="pb-3 font-medium">Last 30 Days</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y dark:divide-slate-700">
                    {uptime.map((service) => {
                      const bars = getUptimeBars(service.serviceName)
                      // Handle both camelCase and snake_case responses
                      const uptime24h = service.uptimePercent24h ?? (service as any).uptime_percent_24h ?? 100
                      const uptime7d = service.uptimePercent7d ?? (service as any).uptime_percent_7d ?? 100
                      const uptime30d = service.uptimePercent30d ?? (service as any).uptime_percent_30d ?? 100
                      const avgResponse = service.avgResponseTimeMs ?? (service as any).avg_response_time_ms
                      return (
                        <tr key={service.serviceName || (service as any).service_name} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                          <td className="py-4">
                            <span className="font-medium text-slate-900 dark:text-white">
                              {service.displayName || (service as any).display_name}
                            </span>
                          </td>
                          <td className="py-4 text-center">
                            <span className={cn('font-semibold', getUptimeColor(uptime24h))}>
                              {uptime24h.toFixed(1)}%
                            </span>
                          </td>
                          <td className="py-4 text-center">
                            <span className={cn('font-semibold', getUptimeColor(uptime7d))}>
                              {uptime7d.toFixed(1)}%
                            </span>
                          </td>
                          <td className="py-4 text-center">
                            <span className={cn('font-semibold', getUptimeColor(uptime30d))}>
                              {uptime30d.toFixed(1)}%
                            </span>
                          </td>
                          <td className="py-4 text-center">
                            {avgResponse ? (
                              <span className="text-slate-600 dark:text-slate-400">
                                {avgResponse}ms
                              </span>
                            ) : (
                              <span className="text-slate-400">—</span>
                            )}
                          </td>
                          <td className="py-4">
                            {/* Mini uptime chart */}
                            <div className="flex items-end gap-[2px] h-6">
                              {bars.length > 0 ? bars.map((bar: { date: string; uptime: number; incidents: number }, i: number) => (
                                <div
                                  key={i}
                                  className={cn(
                                    'w-1.5 rounded-sm transition-colors',
                                    (bar.uptime ?? 100) >= 99.9 ? 'bg-emerald-400' :
                                    (bar.uptime ?? 100) >= 95 ? 'bg-amber-400' : 'bg-red-400'
                                  )}
                                  style={{ height: `${Math.max(4, (bar.uptime ?? 100) / 100 * 24)}px` }}
                                  title={`${bar.date}: ${(bar.uptime ?? 100).toFixed(1)}%`}
                                />
                              )) : (
                                <span className="text-xs text-slate-400">No data</span>
                              )}
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Jobs Tab */}
        <TabsContent value="jobs" className="mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Job Success Rates (24h)</CardTitle>
                <CardDescription>
                  Overall: {jobs?.overallSuccessRate ?? (jobs as any)?.overall_success_rate ?? 0}% • 
                  Total: {jobs?.totalJobs24h ?? (jobs as any)?.total_jobs_24h ?? 0} jobs • 
                  Failed: {jobs?.totalFailed24h ?? (jobs as any)?.total_failed_24h ?? 0}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loadingStates.jobs ? (
                  <SectionSkeleton rows={5} />
                ) : (
                <div className="space-y-6">
                  {jobs?.jobs.map((job: JobStats) => {
                    // Handle both camelCase and snake_case
                    const j = job as any
                    const displayName = job.displayName || j.display_name || job.name
                    const successRate = job.successRate ?? j.success_rate ?? 0
                    const total = job.total24h ?? j.total_24h ?? 0
                    const pending = job.pending ?? j.pending ?? 0
                    const completed = job.completed ?? j.completed ?? 0
                    const failed = job.failed ?? j.failed ?? 0
                    
                    return (
                      <div key={job.name} className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-slate-900 dark:text-white">
                              {displayName}
                            </span>
                            {pending > 0 && (
                              <Badge variant="outline" className="text-xs">
                                {pending} pending
                              </Badge>
                            )}
                          </div>
                          <div className="text-sm text-slate-500">
                            {completed}/{total}
                            {failed > 0 && (
                              <span className="text-red-500 ml-2">({failed} failed)</span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="flex-1 h-3 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                            <div 
                              className={cn(
                                'h-full rounded-full transition-all duration-500',
                                successRate >= 95 ? 'bg-emerald-500' :
                                successRate >= 80 ? 'bg-amber-500' : 'bg-red-500'
                              )}
                              style={{ width: `${successRate}%` }}
                            />
                          </div>
                          <span className={cn(
                            'text-sm font-bold min-w-[50px] text-right',
                            successRate >= 95 ? 'text-emerald-500' :
                            successRate >= 80 ? 'text-amber-500' : 'text-red-500'
                          )}>
                            {successRate}%
                          </span>
                        </div>
                      </div>
                    )
                  })}

                  {(!jobs || jobs.jobs.length === 0) && (
                    <div className="text-center py-8 text-slate-500">
                      No job data available
                    </div>
                  )}
                </div>
                )}
              </CardContent>
            </Card>

            {/* Quick Stats */}
            <div className="space-y-4">
              <Card className="bg-gradient-to-br from-emerald-500 to-emerald-600 text-white">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-emerald-100 text-sm">Completed Jobs (24h)</p>
                      <p className="text-4xl font-bold mt-1">
                        {jobs?.jobs.reduce((sum, j) => sum + j.completed, 0) || 0}
                      </p>
                    </div>
                    <Icons.checkCircle className="h-14 w-14 text-emerald-300/50" />
                  </div>
                </CardContent>
              </Card>
              
              <Card className="bg-gradient-to-br from-red-500 to-red-600 text-white">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-red-100 text-sm">Failed Jobs (24h)</p>
                      <p className="text-4xl font-bold mt-1">
                        {jobs?.totalFailed24h ?? (jobs as any)?.total_failed_24h ?? 0}
                      </p>
                    </div>
                    <Icons.xCircle className="h-14 w-14 text-red-300/50" />
                  </div>
                </CardContent>
              </Card>
              
              <Card className="bg-gradient-to-br from-blue-500 to-blue-600 text-white">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-blue-100 text-sm">Total Jobs (24h)</p>
                      <p className="text-4xl font-bold mt-1">
                        {jobs?.totalJobs24h ?? (jobs as any)?.total_jobs_24h ?? 0}
                      </p>
                    </div>
                    <Icons.activity className="h-14 w-14 text-blue-300/50" />
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* Incidents Tab */}
        <TabsContent value="incidents" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Recent Incidents</CardTitle>
              <CardDescription>
                {incidents?.total || 0} incidents recorded
              </CardDescription>
            </CardHeader>
            <CardContent>
              {incidents && incidents.incidents.length > 0 ? (
                <div className="space-y-3">
                  {incidents.incidents.map((incident: RecentIncident) => {
                    // Handle both camelCase and snake_case
                    const inc = incident as any
                    const displayName = incident.displayName || inc.display_name || incident.serviceName || inc.service_name
                    const errorMsg = incident.errorMessage || inc.error_message
                    const occurredAt = incident.occurredAt || inc.occurred_at
                    
                    return (
                      <div 
                        key={incident.id}
                        className={cn(
                          'flex items-center gap-4 p-4 rounded-lg border',
                          incident.status === 'degraded' ? 'border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-900/10' :
                          'border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10'
                        )}
                      >
                        {getStatusIcon(incident.status)}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-slate-900 dark:text-white">
                              {displayName}
                            </span>
                            <Badge variant="outline" className={cn(
                              'text-xs capitalize',
                              incident.status === 'degraded' ? 'border-amber-300 text-amber-600' : 'border-red-300 text-red-600'
                            )}>
                              {incident.status}
                            </Badge>
                          </div>
                          <p className="text-sm text-slate-500 truncate">
                            {errorMsg || 'No details available'}
                          </p>
                        </div>
                        <div className="text-right text-sm text-slate-500">
                          {occurredAt ? new Date(occurredAt).toLocaleString() : '-'}
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Icons.checkCircle className="h-12 w-12 text-emerald-300 mx-auto mb-4" />
                  <p className="text-slate-500">No incidents recorded</p>
                  <p className="text-sm text-slate-400">All systems have been operating normally</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
