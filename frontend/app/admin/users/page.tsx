'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { adminApi } from '@/lib/admin-api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'
import type { AdminUserListItem } from '@/types/admin'

export default function AdminUsersPage() {
  const router = useRouter()
  const [users, setUsers] = useState<AdminUserListItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [planFilter, setPlanFilter] = useState<string>('')
  const [healthFilter, setHealthFilter] = useState<string>('')
  const [sortBy, setSortBy] = useState<string>('created_at')
  const [sortOrder, setSortOrder] = useState<string>('desc')
  const [offset, setOffset] = useState(0)
  const [hoveredUserId, setHoveredUserId] = useState<string | null>(null)
  const limit = 25

  const fetchUsers = useCallback(async () => {
    try {
      setLoading(true)
      const data = await adminApi.listUsers({
        search: search || undefined,
        plan: planFilter || undefined,
        healthStatus: healthFilter || undefined,
        sortBy,
        sortOrder,
        offset,
        limit,
      })
      setUsers(data.users)
      setTotal(data.total)
    } catch (err) {
      console.error('Failed to fetch users:', err)
    } finally {
      setLoading(false)
    }
  }, [search, planFilter, healthFilter, sortBy, sortOrder, offset])

  useEffect(() => {
    fetchUsers()
  }, [fetchUsers])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setOffset(0)
    fetchUsers()
  }

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('desc')
    }
    setOffset(0)
  }

  const getHealthBadge = (status: string, score: number) => {
    const colors = {
      healthy: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
      at_risk: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
      critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    }
    return (
      <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', colors[status as keyof typeof colors])}>
        {score}
      </span>
    )
  }

  const getPlanBadge = (plan: string, planName?: string) => {
    const colors: Record<string, string> = {
      free: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
      pro_monthly: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
      pro_yearly: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
      pro_plus_monthly: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
      pro_plus_yearly: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
      enterprise: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
      // Legacy plans
      pro_solo: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
      unlimited_solo: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
    }
    const labels: Record<string, string> = {
      free: 'Free',
      pro_monthly: 'Pro',
      pro_yearly: 'Pro',
      pro_plus_monthly: 'Pro+',
      pro_plus_yearly: 'Pro+',
      enterprise: 'Enterprise',
      pro_solo: 'Pro Solo',
      unlimited_solo: 'Unlimited',
    }
    return (
      <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', colors[plan] || colors.free)}>
        {planName || labels[plan] || plan.replace('_', ' ')}
      </span>
    )
  }

  const getSuspendedBadge = () => (
    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
      Suspended
    </span>
  )

  const getSortIcon = (field: string) => {
    if (sortBy !== field) return <Icons.arrowUpDown className="h-3 w-3 opacity-30" />
    return sortOrder === 'asc' 
      ? <Icons.arrowUp className="h-3 w-3" /> 
      : <Icons.arrowDown className="h-3 w-3" />
  }

  const getInitials = (name?: string, email?: string) => {
    if (name) {
      return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    }
    return email?.slice(0, 2).toUpperCase() || '?'
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Users</h1>
        <span className="text-sm text-slate-500">{total} total users</span>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <form onSubmit={handleSearch} className="flex flex-wrap gap-4">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Icons.search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  placeholder="Search by email, name, or organization..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            <select
              value={planFilter}
              onChange={(e) => { setPlanFilter(e.target.value); setOffset(0) }}
              className="h-10 px-3 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
            >
              <option value="">All Plans</option>
              <option value="free">Free</option>
              <option value="pro_monthly">Pro (Monthly)</option>
              <option value="pro_yearly">Pro (Yearly)</option>
              <option value="pro_plus_monthly">Pro+ (Monthly)</option>
              <option value="pro_plus_yearly">Pro+ (Yearly)</option>
              <option value="enterprise">Enterprise</option>
            </select>
            <select
              value={healthFilter}
              onChange={(e) => { setHealthFilter(e.target.value); setOffset(0) }}
              className="h-10 px-3 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
            >
              <option value="">All Health</option>
              <option value="healthy">Healthy</option>
              <option value="at_risk">At Risk</option>
              <option value="critical">Critical</option>
            </select>
            <select
              value={`${sortBy}:${sortOrder}`}
              onChange={(e) => { 
                const [field, order] = e.target.value.split(':')
                setSortBy(field)
                setSortOrder(order)
                setOffset(0)
              }}
              className="h-10 px-3 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
            >
              <option value="created_at:desc">Newest First</option>
              <option value="created_at:asc">Oldest First</option>
              <option value="last_active:desc">Recently Active</option>
              <option value="last_active:asc">Least Active</option>
              <option value="email:asc">Email A-Z</option>
              <option value="email:desc">Email Z-A</option>
            </select>
            <Button type="submit">
              <Icons.search className="h-4 w-4 mr-2" />
              Search
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Users Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Icons.spinner className="h-6 w-6 animate-spin text-teal-500" />
            </div>
          ) : users.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-slate-500">
              <Icons.users className="h-12 w-12 mb-4 opacity-50" />
              <span>No users found</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 dark:bg-slate-800/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      <button onClick={() => handleSort('email')} className="flex items-center gap-1 hover:text-slate-700">
                        User {getSortIcon('email')}
                      </button>
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Organization
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Plan
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Credits
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Health
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      <button onClick={() => handleSort('last_active')} className="flex items-center gap-1 hover:text-slate-700">
                        Last Active {getSortIcon('last_active')}
                      </button>
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {users.map((user) => (
                    <tr 
                      key={user.id}
                      className="hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer transition-colors"
                      onClick={() => router.push(`/admin/users/${user.id}`)}
                      onMouseEnter={() => setHoveredUserId(user.id)}
                      onMouseLeave={() => setHoveredUserId(null)}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          {/* Avatar */}
                          <div className={cn(
                            'w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium',
                            user.isSuspended ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                            user.plan?.includes('pro_plus') ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' :
                            user.plan?.includes('pro') && user.plan !== 'free' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                            user.plan === 'enterprise' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' :
                            'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                          )}>
                            {getInitials(user.fullName, user.email)}
                          </div>
                          <div>
                            <div className="font-medium text-slate-900 dark:text-white">
                              {user.fullName || 'No name'}
                            </div>
                            <div className="text-sm text-slate-500">{user.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-500">
                        {user.organizationName || '-'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          {getPlanBadge(user.plan, user.planName)}
                          {user.isSuspended && getSuspendedBadge()}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {(() => {
                          const usage = user.creditUsage
                          if (!usage) return '-'
                          return (
                            <>
                              <span className={cn(
                                usage.limit === -1 ? 'text-slate-500' :
                                usage.used >= usage.limit ? 'text-red-500 font-medium' :
                                'text-slate-500'
                              )}>
                                {usage.used}
                                {usage.limit !== -1 && `/${usage.limit}`}
                                {usage.limit === -1 && ' (∞)'}
                              </span>
                              {usage.packBalance > 0 && (
                                <span className="ml-1 text-xs text-purple-500">
                                  +{usage.packBalance}
                                </span>
                              )}
                            </>
                          )
                        })()}
                      </td>
                      <td className="px-4 py-3">
                        {getHealthBadge(user.healthStatus, user.healthScore)}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-500">
                        {user.lastActive 
                          ? new Date(user.lastActive).toLocaleDateString()
                          : 'Never'
                        }
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className={cn(
                          'flex items-center justify-end gap-1 transition-opacity',
                          hoveredUserId === user.id ? 'opacity-100' : 'opacity-0'
                        )}>
                          {/* Quick Actions */}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation()
                              window.open(`mailto:${user.email}`, '_blank')
                            }}
                            title="Email user"
                          >
                            <Icons.mail className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation()
                              router.push(`/admin/users/${user.id}`)
                            }}
                            title="View details"
                          >
                            <Icons.eye className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {total > limit && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 dark:border-slate-800">
              <span className="text-sm text-slate-500">
                Showing {offset + 1} to {Math.min(offset + limit, total)} of {total}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset + limit >= total}
                  onClick={() => setOffset(offset + limit)}
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
