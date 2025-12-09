'use client'

import { useEffect, useState } from 'react'
import { adminApi } from '@/lib/admin-api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'
import type { HealthOverview, JobHealthResponse, ServiceStatus, JobStats } from '@/types/admin'

export default function AdminHealthPage() {
  const [health, setHealth] = useState<HealthOverview | null>(null)
  const [jobs, setJobs] = useState<JobHealthResponse | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    try {
      setLoading(true)
      const [healthData, jobsData] = await Promise.all([
        adminApi.getHealthOverview(),
        adminApi.getJobHealth(),
      ])
      setHealth(healthData)
      setJobs(jobsData)
    } catch (err) {
      console.error('Failed to fetch health data:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <Icons.checkCircle className="h-5 w-5 text-green-500" />
      case 'degraded':
        return <Icons.alertTriangle className="h-5 w-5 text-yellow-500" />
      case 'down':
        return <Icons.xCircle className="h-5 w-5 text-red-500" />
      default:
        return <Icons.helpCircle className="h-5 w-5 text-slate-400" />
    }
  }

  const getOverallStatusBadge = (status: string) => {
    const colors = {
      healthy: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
      degraded: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
      down: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    }
    const labels = {
      healthy: 'All Systems Operational',
      degraded: 'Partial Degradation',
      down: 'Major Outage',
    }
    return (
      <span className={cn('px-3 py-1 rounded-full text-sm font-medium', colors[status as keyof typeof colors])}>
        {labels[status as keyof typeof labels]}
      </span>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Icons.spinner className="h-8 w-8 animate-spin text-teal-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">System Health</h1>
          {health && (
            <div className="flex items-center gap-2 mt-2">
              {getOverallStatusBadge(health.overallStatus)}
              <span className="text-sm text-slate-500">
                Last updated: {new Date(health.lastUpdated).toLocaleTimeString()}
              </span>
            </div>
          )}
        </div>
        <Button onClick={fetchData}>
          <Icons.refresh className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Services Status */}
      <Card>
        <CardHeader>
          <CardTitle>Services</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {health?.services.map((service: ServiceStatus) => (
              <div 
                key={service.name}
                className={cn(
                  'flex items-center gap-4 p-4 rounded-lg border',
                  service.status === 'healthy' ? 'border-green-200 dark:border-green-800' :
                  service.status === 'degraded' ? 'border-yellow-200 dark:border-yellow-800' :
                  'border-red-200 dark:border-red-800'
                )}
              >
                {getStatusIcon(service.status)}
                <div className="flex-1">
                  <div className="font-medium text-slate-900 dark:text-white">
                    {service.name}
                  </div>
                  <div className="text-sm text-slate-500">
                    {service.details}
                  </div>
                </div>
                {service.responseTimeMs && (
                  <div className="text-sm text-slate-400">
                    {service.responseTimeMs}ms
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Job Success Rates */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Job Success Rates (24h)
            {jobs && (
              <span className={cn(
                'px-2 py-0.5 rounded-full text-xs font-medium',
                jobs.overallSuccessRate >= 95 ? 'bg-green-100 text-green-700' :
                jobs.overallSuccessRate >= 80 ? 'bg-yellow-100 text-yellow-700' :
                'bg-red-100 text-red-700'
              )}>
                {jobs.overallSuccessRate}% overall
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {jobs?.jobs.map((job: JobStats) => (
              <div key={job.name} className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-medium capitalize">{job.name}</span>
                  <span className="text-sm text-slate-500">
                    {job.completed}/{job.total24h} completed
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div 
                      className={cn(
                        'h-full rounded-full transition-all',
                        job.successRate >= 95 ? 'bg-green-500' :
                        job.successRate >= 80 ? 'bg-yellow-500' :
                        'bg-red-500'
                      )}
                      style={{ width: `${job.successRate}%` }}
                    />
                  </div>
                  <span className={cn(
                    'text-sm font-medium min-w-[60px] text-right',
                    job.successRate >= 95 ? 'text-green-500' :
                    job.successRate >= 80 ? 'text-yellow-500' :
                    'text-red-500'
                  )}>
                    {job.successRate}%
                  </span>
                </div>
                {job.failed > 0 && (
                  <div className="text-xs text-red-500">
                    {job.failed} failed
                  </div>
                )}
              </div>
            ))}

            {(!jobs || jobs.jobs.length === 0) && (
              <div className="text-center py-8 text-slate-500">
                No job data available
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-full bg-green-100 dark:bg-green-900/30">
              <Icons.checkCircle className="h-6 w-6 text-green-500" />
            </div>
            <div>
              <div className="text-2xl font-bold text-green-500">
                {jobs?.jobs.reduce((sum, j) => sum + j.completed, 0) || 0}
              </div>
              <div className="text-sm text-slate-500">Completed (24h)</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-full bg-red-100 dark:bg-red-900/30">
              <Icons.xCircle className="h-6 w-6 text-red-500" />
            </div>
            <div>
              <div className="text-2xl font-bold text-red-500">
                {jobs?.jobs.reduce((sum, j) => sum + j.failed, 0) || 0}
              </div>
              <div className="text-sm text-slate-500">Failed (24h)</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-full bg-blue-100 dark:bg-blue-900/30">
              <Icons.activity className="h-6 w-6 text-blue-500" />
            </div>
            <div>
              <div className="text-2xl font-bold text-blue-500">
                {jobs?.jobs.reduce((sum, j) => sum + j.total24h, 0) || 0}
              </div>
              <div className="text-sm text-slate-500">Total (24h)</div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

