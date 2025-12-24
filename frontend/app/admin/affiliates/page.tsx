'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { adminApi, AffiliateListItem, AffiliateProgramStats } from '@/lib/admin-api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'

export default function AdminAffiliatesPage() {
  const router = useRouter()
  const [affiliates, setAffiliates] = useState<AffiliateListItem[]>([])
  const [stats, setStats] = useState<AffiliateProgramStats | null>(null)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [page, setPage] = useState(1)
  const pageSize = 20

  const fetchAffiliates = useCallback(async () => {
    try {
      setLoading(true)
      const data = await adminApi.listAffiliates({
        page,
        pageSize,
        status: statusFilter || undefined,
        search: search || undefined,
      })
      setAffiliates(data.affiliates)
      setTotal(data.total)
    } catch (err) {
      console.error('Failed to fetch affiliates:', err)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, statusFilter, search])

  const fetchStats = useCallback(async () => {
    try {
      const data = await adminApi.getAffiliateStats()
      setStats(data)
    } catch (err) {
      console.error('Failed to fetch affiliate stats:', err)
    }
  }, [])

  useEffect(() => {
    fetchAffiliates()
    fetchStats()
  }, [fetchAffiliates, fetchStats])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchAffiliates()
  }

  const formatCurrency = (cents: number) => {
    return new Intl.NumberFormat('nl-NL', {
      style: 'currency',
      currency: 'EUR'
    }).format(cents / 100)
  }

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
      pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
      paused: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
      suspended: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
      rejected: 'bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-400',
    }
    return (
      <Badge className={cn('text-xs', colors[status] || colors.pending)}>
        {status}
      </Badge>
    )
  }

  const getConnectBadge = (status: string, enabled: boolean) => {
    if (enabled) {
      return <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 text-xs">Ready</Badge>
    }
    if (status === 'not_connected') {
      return <Badge className="bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 text-xs">Not Set Up</Badge>
    }
    return <Badge className="bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400 text-xs">{status}</Badge>
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Affiliate Program</h1>
          <p className="text-sm text-slate-500">Manage affiliates, commissions, and payouts</p>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total Affiliates</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_affiliates}</div>
              <p className="text-xs text-muted-foreground">
                {stats.active_affiliates} active, {stats.pending_affiliates} pending
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total Referrals</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_referrals}</div>
              <p className="text-xs text-muted-foreground">
                {stats.total_conversions} converted
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Revenue Generated</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{formatCurrency(stats.total_revenue_cents)}</div>
              <p className="text-xs text-muted-foreground">
                {formatCurrency(stats.total_commissions_cents)} in commissions
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Payouts</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatCurrency(stats.total_paid_cents)}</div>
              <p className="text-xs text-muted-foreground">
                {formatCurrency(stats.pending_payouts_cents)} pending
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <form onSubmit={handleSearch} className="flex flex-wrap gap-4">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Icons.search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  placeholder="Search by email, name, or affiliate code..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
              className="h-10 px-3 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
            >
              <option value="">All Statuses</option>
              <option value="active">Active</option>
              <option value="pending">Pending</option>
              <option value="paused">Paused</option>
              <option value="suspended">Suspended</option>
              <option value="rejected">Rejected</option>
            </select>
            <Button type="submit">
              <Icons.search className="h-4 w-4 mr-2" />
              Search
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Affiliates Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Icons.spinner className="h-6 w-6 animate-spin text-teal-500" />
            </div>
          ) : affiliates.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-slate-500">
              <Icons.gift className="h-12 w-12 mb-4 opacity-50" />
              <span>No affiliates found</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 dark:bg-slate-800/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Affiliate
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Code
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Stripe Connect
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Clicks
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Signups
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Conversions
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Earned
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Balance
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {affiliates.map((affiliate) => (
                    <tr 
                      key={affiliate.id}
                      className="hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer transition-colors"
                      onClick={() => router.push(`/admin/affiliates/${affiliate.id}`)}
                    >
                      <td className="px-4 py-3">
                        <div>
                          <div className="font-medium text-slate-900 dark:text-white">
                            {affiliate.user_name || affiliate.user_email?.split('@')[0] || 'Unknown'}
                          </div>
                          <div className="text-sm text-slate-500">{affiliate.user_email}</div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <code className="text-sm font-mono bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                          {affiliate.affiliate_code}
                        </code>
                      </td>
                      <td className="px-4 py-3">
                        {getStatusBadge(affiliate.status)}
                      </td>
                      <td className="px-4 py-3">
                        {getConnectBadge(affiliate.stripe_connect_status, affiliate.stripe_payouts_enabled)}
                      </td>
                      <td className="px-4 py-3 text-right text-sm">
                        {affiliate.total_clicks}
                      </td>
                      <td className="px-4 py-3 text-right text-sm">
                        {affiliate.total_signups}
                      </td>
                      <td className="px-4 py-3 text-right text-sm">
                        {affiliate.total_conversions}
                      </td>
                      <td className="px-4 py-3 text-right text-sm font-medium text-green-600">
                        {formatCurrency(affiliate.total_earned_cents)}
                      </td>
                      <td className="px-4 py-3 text-right text-sm font-medium">
                        {formatCurrency(affiliate.current_balance_cents)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {total > pageSize && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 dark:border-slate-800">
              <span className="text-sm text-slate-500">
                Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, total)} of {total}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page * pageSize >= total}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

