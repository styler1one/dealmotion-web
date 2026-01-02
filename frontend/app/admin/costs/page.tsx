'use client'

import { useEffect, useState } from 'react'
import { adminApi } from '@/lib/admin-api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'
import type { 
  CostSummary,
  CostsByService,
  CostsByAction,
  CostTrend,
  CostTrendByService,
  CostsByUser,
  CostProjection,
  ServiceCost,
  ActionCost,
  DailyCost,
  TopUser
} from '@/types/admin'

export default function AdminCostsPage() {
  const [summary, setSummary] = useState<CostSummary | null>(null)
  const [byService, setByService] = useState<CostsByService | null>(null)
  const [byAction, setByAction] = useState<CostsByAction | null>(null)
  const [trend, setTrend] = useState<CostTrend | null>(null)
  const [trendByService, setTrendByService] = useState<CostTrendByService | null>(null)
  const [topUsers, setTopUsers] = useState<CostsByUser | null>(null)
  const [projection, setProjection] = useState<CostProjection | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [days, setDays] = useState(30)
  const [activeTab, setActiveTab] = useState('overview')

  const fetchData = async (isRefresh = false) => {
    try {
      if (isRefresh) setRefreshing(true)
      else setLoading(true)
      
      const [summaryData, serviceData, actionData, trendData, trendServiceData, usersData, projectionData] = await Promise.all([
        adminApi.getCostSummary(days),
        adminApi.getCostsByService(days),
        adminApi.getCostsByAction(days),
        adminApi.getCostTrend(days),
        adminApi.getCostTrendByService(days),
        adminApi.getTopUsersByCost(days, 20),
        adminApi.getCostProjection(),
      ])
      
      setSummary(summaryData)
      setByService(serviceData)
      setByAction(actionData)
      setTrend(trendData)
      setTrendByService(trendServiceData)
      setTopUsers(usersData)
      setProjection(projectionData)
    } catch (err) {
      console.error('Failed to fetch cost data:', err)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [days])

  const formatCurrency = (cents: number) => {
    const euros = cents / 100
    return new Intl.NumberFormat('nl-NL', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: euros >= 100 ? 0 : 2,
      maximumFractionDigits: euros >= 100 ? 0 : 2,
    }).format(euros)
  }

  const getChangeColor = (percent: number) => {
    if (percent > 10) return 'text-red-500'
    if (percent > 0) return 'text-amber-500'
    if (percent < -10) return 'text-emerald-500'
    if (percent < 0) return 'text-emerald-400'
    return 'text-slate-500'
  }

  const getChangeIcon = (percent: number) => {
    if (percent > 0) return <Icons.trendingUp className="h-4 w-4" />
    if (percent < 0) return <Icons.trendingDown className="h-4 w-4" />
    return <Icons.minus className="h-4 w-4" />
  }

  // Calculate max cost for chart scaling
  const maxDailyCost = trend?.data.reduce((max, d) => Math.max(max, d.costCents), 0) || 1

  // Service colors for chart
  const serviceColors: Record<string, string> = {
    anthropic: 'bg-purple-500',
    gemini: 'bg-blue-500',
    deepgram: 'bg-emerald-500',
    pinecone: 'bg-amber-500',
    voyage: 'bg-pink-500',
    exa: 'bg-cyan-500',
    recall: 'bg-indigo-500',
    google: 'bg-red-500',
    brave: 'bg-orange-500',
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-center">
          <Icons.spinner className="h-10 w-10 animate-spin text-teal-500 mx-auto mb-4" />
          <p className="text-slate-500">Loading cost data...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">API Costs</h1>
          <p className="text-slate-500 mt-1">
            Track and analyze API usage costs across all services
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={days.toString()} onValueChange={(v) => setDays(parseInt(v))}>
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="14">Last 14 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
              <SelectItem value="60">Last 60 days</SelectItem>
              <SelectItem value="90">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={() => fetchData(true)} disabled={refreshing} variant="outline">
            <Icons.refresh className={cn("h-4 w-4 mr-2", refreshing && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-slate-900 to-slate-800 text-white">
          <CardContent className="p-6">
            <p className="text-slate-400 text-sm">Total Cost ({days}d)</p>
            <p className="text-3xl font-bold mt-1">
              {summary?.totalCostFormatted || '€0'}
            </p>
            <div className={cn('flex items-center gap-1 mt-2 text-sm', getChangeColor(summary?.changePercent || 0))}>
              {getChangeIcon(summary?.changePercent || 0)}
              <span>{Math.abs(summary?.changePercent || 0).toFixed(1)}% vs previous period</span>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-6">
            <p className="text-slate-500 text-sm">Daily Average</p>
            <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">
              {formatCurrency(trend?.avgDailyCostCents || 0)}
            </p>
            <p className="text-sm text-slate-400 mt-2">
              Based on {days} days
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-6">
            <p className="text-slate-500 text-sm">Month Projection</p>
            <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">
              {formatCurrency(projection?.currentMonthProjectedCents || 0)}
            </p>
            <p className="text-sm text-slate-400 mt-2">
              {projection?.daysRemaining || 0} days remaining
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-6">
            <p className="text-slate-500 text-sm">Month to Date</p>
            <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">
              {formatCurrency(projection?.currentMonthActualCents || 0)}
            </p>
            <p className="text-sm text-slate-400 mt-2">
              {projection?.daysElapsed || 0} days elapsed
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4 lg:w-auto lg:inline-grid">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="services">By Service</TabsTrigger>
          <TabsTrigger value="actions">By Action</TabsTrigger>
          <TabsTrigger value="users">Top Users</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="mt-6 space-y-6">
          {/* Cost Trend Chart */}
          <Card>
            <CardHeader>
              <CardTitle>Daily Cost Trend</CardTitle>
              <CardDescription>
                Total: {summary?.totalCostFormatted} over {days} days
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                {trend && trend.data.length > 0 ? (
                  <div className="flex items-end justify-between h-full gap-1">
                    {trend.data.map((day: DailyCost, i: number) => {
                      const height = (day.costCents / maxDailyCost) * 100
                      return (
                        <div 
                          key={day.date} 
                          className="flex-1 flex flex-col items-center justify-end group"
                        >
                          <div className="relative w-full">
                            {/* Tooltip */}
                            <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 hidden group-hover:block z-10">
                              <div className="bg-slate-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap">
                                <div className="font-medium">{day.date}</div>
                                <div>{formatCurrency(day.costCents)}</div>
                                <div className="text-slate-400">{day.requestCount} requests</div>
                              </div>
                            </div>
                            {/* Bar */}
                            <div 
                              className={cn(
                                'w-full rounded-t transition-all duration-200 hover:opacity-80',
                                'bg-gradient-to-t from-teal-600 to-teal-400'
                              )}
                              style={{ height: `${Math.max(4, height * 2)}px` }}
                            />
                          </div>
                          {/* Date label (show every 5th) */}
                          {i % Math.ceil(trend.data.length / 7) === 0 && (
                            <div className="text-[10px] text-slate-400 mt-1 rotate-45 origin-left">
                              {day.date.slice(5)}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-full text-slate-400">
                    No cost data available
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Service Breakdown Pie */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Cost by Service</CardTitle>
                <CardDescription>Distribution of costs across services</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-8">
                  {/* Simple pie visualization */}
                  <div className="relative w-40 h-40 flex-shrink-0">
                    <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                      {byService?.services.reduce((acc, service, i) => {
                        const startAngle = acc.offset
                        const angle = (service.percentOfTotal / 100) * 360
                        const largeArc = angle > 180 ? 1 : 0
                        const endAngle = startAngle + angle
                        
                        const startX = 50 + 40 * Math.cos((startAngle * Math.PI) / 180)
                        const startY = 50 + 40 * Math.sin((startAngle * Math.PI) / 180)
                        const endX = 50 + 40 * Math.cos((endAngle * Math.PI) / 180)
                        const endY = 50 + 40 * Math.sin((endAngle * Math.PI) / 180)
                        
                        const colors = ['#14b8a6', '#8b5cf6', '#f59e0b', '#ef4444', '#3b82f6', '#ec4899', '#10b981', '#6366f1']
                        
                        acc.paths.push(
                          <path
                            key={service.serviceName}
                            d={`M 50 50 L ${startX} ${startY} A 40 40 0 ${largeArc} 1 ${endX} ${endY} Z`}
                            fill={colors[i % colors.length]}
                            className="hover:opacity-80 transition-opacity"
                          />
                        )
                        acc.offset = endAngle
                        return acc
                      }, { paths: [] as JSX.Element[], offset: 0 }).paths}
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-slate-900 dark:text-white">
                          {byService?.totalCostCents ? formatCurrency(byService.totalCostCents) : '€0'}
                        </div>
                        <div className="text-xs text-slate-500">Total</div>
                      </div>
                    </div>
                  </div>
                  
                  {/* Legend */}
                  <div className="flex-1 space-y-2">
                    {byService?.services.slice(0, 6).map((service: ServiceCost, i: number) => {
                      const colors = ['bg-teal-500', 'bg-purple-500', 'bg-amber-500', 'bg-red-500', 'bg-blue-500', 'bg-pink-500']
                      return (
                        <div key={service.serviceName} className="flex items-center gap-2">
                          <div className={cn('w-3 h-3 rounded-full', colors[i % colors.length])} />
                          <span className="flex-1 text-sm text-slate-600 dark:text-slate-400">
                            {service.displayName}
                          </span>
                          <span className="text-sm font-medium text-slate-900 dark:text-white">
                            {service.percentOfTotal.toFixed(1)}%
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Cost by Action</CardTitle>
                <CardDescription>What operations cost the most</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {byAction?.actions.slice(0, 6).map((action: ActionCost) => (
                    <div key={action.actionName} className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-600 dark:text-slate-400">{action.displayName}</span>
                        <span className="font-medium text-slate-900 dark:text-white">
                          {action.costFormatted}
                        </span>
                      </div>
                      <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-teal-500 rounded-full"
                          style={{ 
                            width: `${(action.costCents / (byAction?.totalCostCents || 1)) * 100}%` 
                          }}
                        />
                      </div>
                      <div className="text-xs text-slate-400">
                        {action.count} calls • avg {formatCurrency(action.avgCostCents)}/call
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Services Tab */}
        <TabsContent value="services" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Cost Breakdown by Service</CardTitle>
              <CardDescription>
                Detailed costs for each external API service
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-sm text-slate-500 border-b dark:border-slate-700">
                      <th className="pb-3 font-medium">Service</th>
                      <th className="pb-3 font-medium text-right">Cost</th>
                      <th className="pb-3 font-medium text-right">% of Total</th>
                      <th className="pb-3 font-medium text-right">Requests</th>
                      <th className="pb-3 font-medium text-right">Tokens</th>
                      <th className="pb-3 font-medium text-right">Minutes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y dark:divide-slate-700">
                    {byService?.services.map((service: ServiceCost) => (
                      <tr key={service.serviceName} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                        <td className="py-4">
                          <div className="flex items-center gap-2">
                            <div className={cn(
                              'w-2 h-2 rounded-full',
                              serviceColors[service.serviceName] || 'bg-slate-400'
                            )} />
                            <span className="font-medium text-slate-900 dark:text-white">
                              {service.displayName}
                            </span>
                          </div>
                        </td>
                        <td className="py-4 text-right font-semibold text-slate-900 dark:text-white">
                          {service.costFormatted}
                        </td>
                        <td className="py-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-16 h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                              <div 
                                className={cn('h-full rounded-full', serviceColors[service.serviceName] || 'bg-slate-400')}
                                style={{ width: `${service.percentOfTotal}%` }}
                              />
                            </div>
                            <span className="text-sm text-slate-600 dark:text-slate-400 w-12">
                              {service.percentOfTotal.toFixed(1)}%
                            </span>
                          </div>
                        </td>
                        <td className="py-4 text-right text-slate-600 dark:text-slate-400">
                          {service.requestCount.toLocaleString()}
                        </td>
                        <td className="py-4 text-right text-slate-600 dark:text-slate-400">
                          {service.tokensUsed ? (service.tokensUsed / 1000).toFixed(1) + 'K' : '—'}
                        </td>
                        <td className="py-4 text-right text-slate-600 dark:text-slate-400">
                          {service.minutesUsed ? service.minutesUsed.toFixed(1) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 dark:border-slate-600">
                      <td className="py-4 font-bold text-slate-900 dark:text-white">Total</td>
                      <td className="py-4 text-right font-bold text-slate-900 dark:text-white">
                        {formatCurrency(byService?.totalCostCents || 0)}
                      </td>
                      <td className="py-4 text-right font-bold text-slate-900 dark:text-white">100%</td>
                      <td className="py-4 text-right font-bold text-slate-600 dark:text-slate-400">
                        {byService?.services.reduce((sum, s) => sum + s.requestCount, 0).toLocaleString()}
                      </td>
                      <td className="py-4"></td>
                      <td className="py-4"></td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Service Trend Chart */}
          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Cost Trend by Service</CardTitle>
              <CardDescription>Daily cost breakdown per service</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {trendByService?.services.slice(0, 5).map((service) => (
                  <div key={service.serviceName}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div className={cn(
                          'w-3 h-3 rounded-full',
                          serviceColors[service.serviceName] || 'bg-slate-400'
                        )} />
                        <span className="font-medium text-slate-900 dark:text-white">
                          {service.displayName}
                        </span>
                      </div>
                      <span className="text-sm text-slate-500">
                        {formatCurrency(service.totalCostCents)}
                      </span>
                    </div>
                    <div className="flex items-end h-12 gap-[2px]">
                      {service.dailyCosts.map((day, i) => {
                        const maxCost = Math.max(...service.dailyCosts.map(d => d.costCents)) || 1
                        const height = (day.costCents / maxCost) * 100
                        return (
                          <div
                            key={i}
                            className={cn(
                              'flex-1 rounded-t transition-all',
                              serviceColors[service.serviceName] || 'bg-slate-400',
                              'opacity-70 hover:opacity-100'
                            )}
                            style={{ height: `${Math.max(2, height)}%` }}
                            title={`${day.date}: ${formatCurrency(day.costCents)}`}
                          />
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Actions Tab */}
        <TabsContent value="actions" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Cost by Action Type</CardTitle>
              <CardDescription>
                How different operations contribute to total costs
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {byAction?.actions.map((action: ActionCost) => (
                  <div key={action.actionName} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="font-medium text-slate-900 dark:text-white">
                          {action.displayName}
                        </span>
                        <p className="text-sm text-slate-500">
                          {action.count.toLocaleString()} calls • 
                          avg {formatCurrency(action.avgCostCents)} per call
                        </p>
                      </div>
                      <div className="text-right">
                        <div className="text-xl font-bold text-slate-900 dark:text-white">
                          {action.costFormatted}
                        </div>
                        <div className="text-sm text-slate-500">
                          {((action.costCents / (byAction?.totalCostCents || 1)) * 100).toFixed(1)}% of total
                        </div>
                      </div>
                    </div>
                    <div className="h-3 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-gradient-to-r from-teal-500 to-teal-400 rounded-full transition-all duration-500"
                        style={{ 
                          width: `${(action.costCents / (byAction?.totalCostCents || 1)) * 100}%` 
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Users Tab */}
        <TabsContent value="users" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Top Users by Cost</CardTitle>
              <CardDescription>
                Users with highest API costs in the selected period • 
                {topUsers?.totalUsers || 0} users total
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-sm text-slate-500 border-b dark:border-slate-700">
                      <th className="pb-3 font-medium">#</th>
                      <th className="pb-3 font-medium">User</th>
                      <th className="pb-3 font-medium">Organization</th>
                      <th className="pb-3 font-medium text-right">Cost</th>
                      <th className="pb-3 font-medium text-right">Requests</th>
                      <th className="pb-3 font-medium text-right">% of Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y dark:divide-slate-700">
                    {topUsers?.users.map((user: TopUser, index: number) => (
                      <tr key={user.userId} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                        <td className="py-4 text-slate-400">
                          {index + 1}
                        </td>
                        <td className="py-4">
                          <div className="font-medium text-slate-900 dark:text-white">
                            {user.email || user.userId.slice(0, 8) + '...'}
                          </div>
                        </td>
                        <td className="py-4 text-slate-600 dark:text-slate-400">
                          {user.organizationName || '—'}
                        </td>
                        <td className="py-4 text-right font-semibold text-slate-900 dark:text-white">
                          {user.costFormatted}
                        </td>
                        <td className="py-4 text-right text-slate-600 dark:text-slate-400">
                          {user.requestCount.toLocaleString()}
                        </td>
                        <td className="py-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-12 h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-teal-500 rounded-full"
                                style={{ 
                                  width: `${(user.costCents / (summary?.totalCostCents || 1)) * 100}%` 
                                }}
                              />
                            </div>
                            <span className="text-sm text-slate-500 w-10">
                              {((user.costCents / (summary?.totalCostCents || 1)) * 100).toFixed(1)}%
                            </span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              
              {(!topUsers || topUsers.users.length === 0) && (
                <div className="text-center py-12 text-slate-500">
                  No user cost data available
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

