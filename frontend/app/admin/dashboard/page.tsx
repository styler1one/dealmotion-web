'use client'

import { useEffect, useState } from 'react'
import { adminApi } from '@/lib/admin-api'
import { StatsCard, AlertBadge } from '@/components/admin/stats-card'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'
import Link from 'next/link'
import type { DashboardMetrics, DashboardTrends, AdminAlert, HealthDistribution, RecentActivityItem } from '@/types/admin'

export default function AdminDashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [trends, setTrends] = useState<DashboardTrends | null>(null)
  const [alerts, setAlerts] = useState<AdminAlert[]>([])
  const [healthDist, setHealthDist] = useState<HealthDistribution | null>(null)
  const [recentActivity, setRecentActivity] = useState<RecentActivityItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const [metricsData, trendsData, alertsData, healthDistData, activityData] = await Promise.all([
          adminApi.getMetrics(),
          adminApi.getTrends(7),
          adminApi.listAlerts({ status: 'active', limit: 5 }),
          adminApi.getHealthDistribution(),
          adminApi.getRecentActivity(10),
        ])
        
        setMetrics(metricsData)
        setTrends(trendsData)
        setAlerts(alertsData.alerts)
        setHealthDist(healthDistData)
        setRecentActivity(activityData.activities)
      } catch (err) {
        console.error('Failed to fetch dashboard data:', err)
        setError('Failed to load dashboard data')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Dashboard</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-6">
                <div className="h-4 w-24 bg-slate-200 dark:bg-slate-700 rounded mb-4" />
                <div className="h-8 w-16 bg-slate-200 dark:bg-slate-700 rounded" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Icons.alertTriangle className="h-12 w-12 text-red-500 mb-4" />
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
          Error Loading Dashboard
        </h2>
        <p className="text-slate-500 dark:text-slate-400 mb-4">{error}</p>
        <Button onClick={() => window.location.reload()}>
          <Icons.refresh className="h-4 w-4 mr-2" />
          Retry
        </Button>
      </div>
    )
  }

  const formatCurrency = (cents: number) => {
    return `€${(cents / 100).toFixed(2)}`
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Dashboard</h1>
        <Button variant="outline" onClick={() => window.location.reload()}>
          <Icons.refresh className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Metrics Grid - 5 cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatsCard
          title="Total Users"
          value={metrics?.totalUsers || 0}
          icon="users"
          iconColor="text-blue-500"
          trend={{
            value: metrics?.usersGrowthWeek || 0,
            label: ' this week',
            isPositive: (metrics?.usersGrowthWeek || 0) >= 0,
          }}
        />
        <StatsCard
          title="Active Users (7d)"
          value={metrics?.activeUsers7d || 0}
          icon="activity"
          iconColor="text-green-500"
          description="With activity in last 7 days"
        />
        <StatsCard
          title="MRR"
          value={formatCurrency(metrics?.mrrCents || 0)}
          icon="creditCard"
          iconColor="text-purple-500"
          trend={{
            value: metrics?.mrrChangePercent || 0,
            label: '% vs last month',
            isPositive: (metrics?.mrrChangePercent || 0) >= 0,
          }}
        />
        <StatsCard
          title="Error Rate (24h)"
          value={`${metrics?.errorRate24h || 0}%`}
          icon="alertCircle"
          iconColor={(metrics?.errorRate24h || 0) > 5 ? 'text-red-500' : 'text-green-500'}
          description={(metrics?.errorRate24h || 0) > 5 ? 'Above threshold' : 'Within limits'}
        />
        <StatsCard
          title="Active Alerts"
          value={metrics?.activeAlerts || 0}
          icon="alertTriangle"
          iconColor={metrics?.activeAlerts ? 'text-yellow-500' : 'text-green-500'}
          description={metrics?.activeAlerts ? 'Requires attention' : 'All clear'}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Usage Trends */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg">Usage Trends (7 Days)</CardTitle>
          </CardHeader>
          <CardContent>
            {trends && trends.trends.length > 0 ? (
              <div className="space-y-4">
                {/* Stacked bar chart representation */}
                <div className="flex items-end gap-1 h-40">
                  {trends.trends.map((day, i) => {
                    const total = day.researches + day.preps + day.followups
                    const maxHeight = 160
                    const maxTotal = Math.max(...trends.trends.map(t => t.researches + t.preps + t.followups), 1)
                    
                    // Calculate heights for stacked bars
                    const researchHeight = maxTotal > 0 ? (day.researches / maxTotal) * maxHeight : 0
                    const prepHeight = maxTotal > 0 ? (day.preps / maxTotal) * maxHeight : 0
                    const followupHeight = maxTotal > 0 ? (day.followups / maxTotal) * maxHeight : 0
                    
                    return (
                      <div key={i} className="flex-1 flex flex-col items-center gap-1">
                        <div 
                          className="w-full flex flex-col-reverse rounded-t overflow-hidden transition-all hover:opacity-80"
                          style={{ height: `${researchHeight + prepHeight + followupHeight}px` }}
                          title={`${day.date}: ${day.researches} researches, ${day.preps} preps, ${day.followups} follow-ups`}
                        >
                          {/* Researches (bottom - blue) */}
                          {day.researches > 0 && (
                            <div 
                              className="w-full bg-blue-500"
                              style={{ height: `${researchHeight}px` }}
                            />
                          )}
                          {/* Preps (middle - green) */}
                          {day.preps > 0 && (
                            <div 
                              className="w-full bg-green-500"
                              style={{ height: `${prepHeight}px` }}
                            />
                          )}
                          {/* Follow-ups (top - orange) */}
                          {day.followups > 0 && (
                            <div 
                              className="w-full bg-orange-500"
                              style={{ height: `${followupHeight}px` }}
                            />
                          )}
                        </div>
                        <span className="text-[10px] text-slate-500">
                          {new Date(day.date).toLocaleDateString('en', { weekday: 'short' })}
                        </span>
                      </div>
                    )
                  })}
                </div>
                
                {/* Legend */}
                <div className="flex items-center gap-4 text-xs text-slate-500">
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded bg-blue-500" />
                    <span>Researches</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded bg-green-500" />
                    <span>Preps</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded bg-orange-500" />
                    <span>Follow-ups</span>
                  </div>
                </div>

                {/* Summary */}
                <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-100 dark:border-slate-800">
                  <div>
                    <div className="text-2xl font-bold text-blue-500">
                      {trends.trends.reduce((sum, d) => sum + d.researches, 0)}
                    </div>
                    <div className="text-xs text-slate-500">Researches</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-green-500">
                      {trends.trends.reduce((sum, d) => sum + d.preps, 0)}
                    </div>
                    <div className="text-xs text-slate-500">Preparations</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-orange-500">
                      {trends.trends.reduce((sum, d) => sum + d.followups, 0)}
                    </div>
                    <div className="text-xs text-slate-500">Follow-ups</div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-40 text-slate-500">
                No data available
              </div>
            )}
          </CardContent>
        </Card>

        {/* Customer Health Distribution - Pie Chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Customer Health</CardTitle>
          </CardHeader>
          <CardContent>
            {healthDist && healthDist.total > 0 ? (
              <div className="space-y-4">
                {/* Pie chart visualization */}
                <div className="relative w-32 h-32 mx-auto">
                  <svg viewBox="0 0 36 36" className="w-full h-full transform -rotate-90">
                    {/* Calculate percentages */}
                    {(() => {
                      const total = healthDist.total || 1
                      const healthyPct = (healthDist.healthy / total) * 100
                      const atRiskPct = (healthDist.atRisk / total) * 100
                      const criticalPct = (healthDist.critical / total) * 100
                      
                      const healthyDash = healthyPct
                      const atRiskDash = atRiskPct
                      const criticalDash = criticalPct
                      
                      const healthyOffset = 0
                      const atRiskOffset = 100 - healthyPct
                      const criticalOffset = 100 - healthyPct - atRiskPct
                      
                      return (
                        <>
                          {/* Healthy - Green */}
                          {healthyPct > 0 && (
                            <circle
                              cx="18" cy="18" r="15.9155"
                              fill="none"
                              stroke="#22c55e"
                              strokeWidth="3.8"
                              strokeDasharray={`${healthyDash} ${100 - healthyDash}`}
                              strokeDashoffset={healthyOffset}
                            />
                          )}
                          {/* At Risk - Yellow */}
                          {atRiskPct > 0 && (
                            <circle
                              cx="18" cy="18" r="15.9155"
                              fill="none"
                              stroke="#eab308"
                              strokeWidth="3.8"
                              strokeDasharray={`${atRiskDash} ${100 - atRiskDash}`}
                              strokeDashoffset={atRiskOffset}
                            />
                          )}
                          {/* Critical - Red */}
                          {criticalPct > 0 && (
                            <circle
                              cx="18" cy="18" r="15.9155"
                              fill="none"
                              stroke="#ef4444"
                              strokeWidth="3.8"
                              strokeDasharray={`${criticalDash} ${100 - criticalDash}`}
                              strokeDashoffset={criticalOffset}
                            />
                          )}
                        </>
                      )
                    })()}
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-2xl font-bold text-slate-900 dark:text-white">
                      {healthDist.total}
                    </span>
                  </div>
                </div>
                
                {/* Legend */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-green-500" />
                      <span className="text-slate-600 dark:text-slate-400">Healthy (80-100)</span>
                    </div>
                    <span className="font-medium text-slate-900 dark:text-white">{healthDist.healthy}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-yellow-500" />
                      <span className="text-slate-600 dark:text-slate-400">At Risk (50-79)</span>
                    </div>
                    <span className="font-medium text-slate-900 dark:text-white">{healthDist.atRisk}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-red-500" />
                      <span className="text-slate-600 dark:text-slate-400">Critical (0-49)</span>
                    </div>
                    <span className="font-medium text-slate-900 dark:text-white">{healthDist.critical}</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-slate-500">
                <Icons.users className="h-8 w-8 mb-2" />
                <span className="text-sm">No users yet</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Active Alerts */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg">Active Alerts</CardTitle>
            <Link href="/admin/alerts">
              <Button variant="ghost" size="sm">
                View All
                <Icons.chevronRight className="h-4 w-4 ml-1" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {alerts.length > 0 ? (
              <div className="space-y-3">
                {alerts.map((alert) => (
                  <Link 
                    key={alert.id} 
                    href={`/admin/alerts?id=${alert.id}`}
                    className="block"
                  >
                    <div className={cn(
                      'flex items-start gap-3 p-3 rounded-lg border transition-colors hover:bg-slate-50 dark:hover:bg-slate-800',
                      alert.severity === 'critical' ? 'border-red-200 dark:border-red-900' :
                      alert.severity === 'error' ? 'border-orange-200 dark:border-orange-900' :
                      alert.severity === 'warning' ? 'border-yellow-200 dark:border-yellow-900' :
                      'border-blue-200 dark:border-blue-900'
                    )}>
                      <div className={cn(
                        'p-1.5 rounded-full',
                        alert.severity === 'critical' ? 'bg-red-100 dark:bg-red-900/30' :
                        alert.severity === 'error' ? 'bg-orange-100 dark:bg-orange-900/30' :
                        alert.severity === 'warning' ? 'bg-yellow-100 dark:bg-yellow-900/30' :
                        'bg-blue-100 dark:bg-blue-900/30'
                      )}>
                        <Icons.alertTriangle className={cn(
                          'h-4 w-4',
                          alert.severity === 'critical' ? 'text-red-500' :
                          alert.severity === 'error' ? 'text-orange-500' :
                          alert.severity === 'warning' ? 'text-yellow-500' :
                          'text-blue-500'
                        )} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm text-slate-900 dark:text-white truncate">
                          {alert.title}
                        </div>
                        <div className="text-xs text-slate-500 truncate">
                          {alert.targetName || alert.alertType}
                        </div>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-slate-500">
                <Icons.checkCircle className="h-8 w-8 text-green-500 mb-2" />
                <span className="text-sm">All clear!</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity Feed */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-lg">Recent Activity</CardTitle>
        </CardHeader>
        <CardContent>
          {recentActivity.length > 0 ? (
            <div className="space-y-3">
              {recentActivity.map((activity) => (
                <div 
                  key={activity.id}
                  className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50"
                >
                  <div className={cn(
                    'p-2 rounded-full',
                    activity.type === 'research' ? 'bg-blue-100 dark:bg-blue-900/30' :
                    activity.type === 'preparation' ? 'bg-green-100 dark:bg-green-900/30' :
                    'bg-orange-100 dark:bg-orange-900/30'
                  )}>
                    {activity.type === 'research' ? (
                      <Icons.search className="h-4 w-4 text-blue-500" />
                    ) : activity.type === 'preparation' ? (
                      <Icons.fileText className="h-4 w-4 text-green-500" />
                    ) : (
                      <Icons.mail className="h-4 w-4 text-orange-500" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm text-slate-900 dark:text-white truncate">
                        {activity.userName}
                      </span>
                      <span className={cn(
                        'text-xs px-1.5 py-0.5 rounded',
                        activity.status === 'completed' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                        activity.status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                        'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300'
                      )}>
                        {activity.status}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 truncate">
                      {activity.type === 'research' ? 'Researched' :
                       activity.type === 'preparation' ? 'Prepared for' :
                       'Follow-up for'} <strong>{activity.title}</strong>
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      {new Date(activity.createdAt).toLocaleString('en', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </div>
                  </div>
                  <Link href={`/admin/users/${activity.userId}`}>
                    <Button variant="ghost" size="sm" className="text-xs">
                      View User
                    </Button>
                  </Link>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-slate-500">
              <Icons.inbox className="h-8 w-8 mb-2" />
              <span className="text-sm">No recent activity</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Link href="/admin/users">
              <Button variant="outline" className="w-full h-auto py-4 flex flex-col gap-2">
                <Icons.users className="h-5 w-5 text-blue-500" />
                <span>View Users</span>
              </Button>
            </Link>
            <Link href="/admin/alerts">
              <Button variant="outline" className="w-full h-auto py-4 flex flex-col gap-2">
                <Icons.alertTriangle className="h-5 w-5 text-yellow-500" />
                <span>Manage Alerts</span>
                {metrics?.activeAlerts ? (
                  <AlertBadge count={metrics.activeAlerts} />
                ) : null}
              </Button>
            </Link>
            <Link href="/admin/health">
              <Button variant="outline" className="w-full h-auto py-4 flex flex-col gap-2">
                <Icons.activity className="h-5 w-5 text-green-500" />
                <span>System Health</span>
              </Button>
            </Link>
            <Link href="/admin/billing">
              <Button variant="outline" className="w-full h-auto py-4 flex flex-col gap-2">
                <Icons.creditCard className="h-5 w-5 text-purple-500" />
                <span>Billing Overview</span>
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

