'use client'

import { useEffect, useState, useCallback } from 'react'
import { adminApi } from '@/lib/admin-api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'
import type { AuditLogEntry, AuditLogResponse } from '@/types/admin'

export default function AdminAuditPage() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  
  // Filters
  const [actionFilter, setActionFilter] = useState('')
  const [targetTypeFilter, setTargetTypeFilter] = useState('')
  const [search, setSearch] = useState('')
  const [actions, setActions] = useState<string[]>([])

  const fetchEntries = useCallback(async (loadMore = false) => {
    try {
      if (loadMore) {
        setLoadingMore(true)
      } else {
        setLoading(true)
        setCursor(null)
      }
      
      const data = await adminApi.getAuditLog({
        action: actionFilter || undefined,
        targetType: targetTypeFilter || undefined,
        search: search || undefined,
        limit: 50,
        cursor: loadMore ? cursor || undefined : undefined,
      })
      
      if (loadMore) {
        setEntries(prev => [...prev, ...data.entries])
      } else {
        setEntries(data.entries)
      }
      
      setTotal(data.total)
      setHasMore(data.hasMore)
      if (data.nextCursor) {
        setCursor(data.nextCursor)
      }
    } catch (err) {
      console.error('Failed to fetch audit log:', err)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [actionFilter, targetTypeFilter, search, cursor])

  useEffect(() => {
    fetchEntries()
  }, [actionFilter, targetTypeFilter]) // Note: not including search to avoid fetch on every keystroke

  useEffect(() => {
    const fetchActions = async () => {
      try {
        const data = await adminApi.getActionTypes()
        setActions(data.actions)
      } catch (err) {
        console.error('Failed to fetch action types:', err)
      }
    }
    fetchActions()
  }, [])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    fetchEntries()
  }

  const handleExport = async () => {
    try {
      const blob = await adminApi.exportAuditLog({
        action: actionFilter || undefined,
        targetType: targetTypeFilter || undefined,
        limit: 10000,
      })
      
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `audit_log_${new Date().toISOString().split('T')[0]}.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Failed to export:', err)
    }
  }

  const getActionBadge = (action: string) => {
    const parts = action.split('.')
    const type = parts[0]
    const colors: Record<string, string> = {
      user: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
      alert: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
      note: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
      admin: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    }
    
    return (
      <span className={cn(
        'px-2 py-0.5 rounded-full text-xs font-medium',
        colors[type] || 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400'
      )}>
        {action}
      </span>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Audit Log</h1>
          <p className="text-sm text-slate-500">{total} total entries</p>
        </div>
        <Button onClick={handleExport}>
          <Icons.download className="h-4 w-4 mr-2" />
          Export CSV
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <form onSubmit={handleSearch} className="flex flex-wrap gap-4">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Icons.search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  placeholder="Search by target identifier..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="h-10 px-3 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
            >
              <option value="">All Actions</option>
              {actions.map((action) => (
                <option key={action} value={action}>{action}</option>
              ))}
            </select>
            <select
              value={targetTypeFilter}
              onChange={(e) => setTargetTypeFilter(e.target.value)}
              className="h-10 px-3 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
            >
              <option value="">All Targets</option>
              <option value="user">User</option>
              <option value="organization">Organization</option>
              <option value="alert">Alert</option>
            </select>
            <Button type="submit">
              <Icons.search className="h-4 w-4 mr-2" />
              Search
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Audit Log Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Icons.spinner className="h-6 w-6 animate-spin text-teal-500" />
            </div>
          ) : entries.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-slate-500">
              <Icons.fileText className="h-12 w-12 opacity-50 mb-4" />
              <span>No audit entries found</span>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-50 dark:bg-slate-800/50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                        Timestamp
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                        Admin
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                        Action
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                        Target
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                        Details
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                        IP
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {entries.map((entry) => (
                      <tr key={entry.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                        <td className="px-4 py-3 text-sm text-slate-500">
                          {new Date(entry.createdAt).toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {entry.adminEmail}
                        </td>
                        <td className="px-4 py-3">
                          {getActionBadge(entry.action)}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {entry.targetIdentifier ? (
                            <div>
                              <div className="font-medium">{entry.targetIdentifier}</div>
                              <div className="text-xs text-slate-500 capitalize">{entry.targetType}</div>
                            </div>
                          ) : (
                            <span className="text-slate-400">-</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-500 max-w-[200px] truncate">
                          {entry.details ? JSON.stringify(entry.details) : '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-500">
                          {entry.ipAddress || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Load More */}
              {hasMore && (
                <div className="p-4 text-center border-t border-slate-100 dark:border-slate-800">
                  <Button
                    variant="outline"
                    onClick={() => fetchEntries(true)}
                    disabled={loadingMore}
                  >
                    {loadingMore ? (
                      <Icons.spinner className="h-4 w-4 animate-spin mr-2" />
                    ) : null}
                    Load More
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

