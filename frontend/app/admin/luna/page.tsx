'use client'

/**
 * Luna Admin Page
 * SPEC-046-Luna-Unified-AI-Assistant
 * 
 * Admin dashboard for Luna shadow mode monitoring, comparison with Autopilot,
 * feature flags management, and message inspection.
 */

import { useEffect, useState, useCallback } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Icons } from '@/components/icons'
import { api } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'
import { formatDistanceToNow } from 'date-fns'
import { nl } from 'date-fns/locale'

// Types
interface LunaShadowStats {
  totalMessagesCreated: number
  messagesByStatus: Record<string, number>
  messagesByType: Record<string, number>
  uniqueUsersReached: number
  shadowModeEnabled: boolean
  lunaEnabled: boolean
  widgetEnabled: boolean
  periodDays: number
}

interface LunaComparisonStats {
  lunaMessagesCreated: number
  autopilotProposalsCreated: number
  lunaAcceptanceRate: number
  autopilotAcceptanceRate: number
  lunaActiveUsers: number
  autopilotActiveUsers: number
  periodDays: number
}

interface LunaMessage {
  id: string
  userId: string
  userEmail?: string
  messageType: string
  status: string
  priority: number
  title: string
  createdAt: string
  viewedAt?: string
  actedAt?: string
}

export default function LunaAdminPage() {
  const { toast } = useToast()
  
  // State
  const [stats, setStats] = useState<LunaShadowStats | null>(null)
  const [comparison, setComparison] = useState<LunaComparisonStats | null>(null)
  const [messages, setMessages] = useState<LunaMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [periodDays, setPeriodDays] = useState(7)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [updatingFlag, setUpdatingFlag] = useState<string | null>(null)
  
  // Fetch all data
  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const statusParam = statusFilter && statusFilter !== 'all' ? `&status=${statusFilter}` : ''
      const typeParam = typeFilter && typeFilter !== 'all' ? `&message_type=${typeFilter}` : ''
      
      const [statsRes, comparisonRes, messagesRes] = await Promise.all([
        api.get<LunaShadowStats>(`/api/v1/admin/luna/stats?days=${periodDays}`),
        api.get<LunaComparisonStats>(`/api/v1/admin/luna/comparison?days=${periodDays}`),
        api.get<{ messages: LunaMessage[] }>(`/api/v1/admin/luna/messages?limit=50${statusParam}${typeParam}`),
      ])
      
      if (!statsRes.error && statsRes.data) setStats(statsRes.data)
      if (!comparisonRes.error && comparisonRes.data) setComparison(comparisonRes.data)
      if (!messagesRes.error && messagesRes.data) setMessages(messagesRes.data.messages || [])
    } catch (error) {
      console.error('Failed to fetch Luna data:', error)
      toast({ title: 'Failed to fetch data', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [periodDays, statusFilter, typeFilter, toast])
  
  useEffect(() => {
    fetchData()
  }, [fetchData])
  
  // Toggle feature flag
  const toggleFlag = async (flagName: string, enabled: boolean) => {
    setUpdatingFlag(flagName)
    try {
      const { error } = await api.post(`/api/v1/admin/luna/flags/${flagName}?enabled=${enabled}`)
      if (error) throw error
      
      toast({ title: `${flagName} ${enabled ? 'enabled' : 'disabled'}` })
      fetchData()
    } catch (error) {
      toast({ title: 'Failed to update flag', variant: 'destructive' })
    } finally {
      setUpdatingFlag(null)
    }
  }
  
  // Status badge color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-500/20 text-green-400'
      case 'pending': return 'bg-blue-500/20 text-blue-400'
      case 'executing': return 'bg-yellow-500/20 text-yellow-400'
      case 'dismissed': return 'bg-slate-500/20 text-slate-400'
      case 'snoozed': return 'bg-purple-500/20 text-purple-400'
      case 'expired': return 'bg-red-500/20 text-red-400'
      case 'failed': return 'bg-red-500/20 text-red-400'
      default: return 'bg-slate-500/20 text-slate-400'
    }
  }
  
  if (loading && !stats) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center h-64">
          <Icons.spinner className="h-8 w-8 animate-spin text-amber-500" />
        </div>
      </div>
    )
  }
  
  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Icons.sparkles className="h-6 w-6 text-amber-400" />
            Luna AI Dashboard
          </h1>
          <p className="text-slate-400 mt-1">
            Shadow mode monitoring & feature flags
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={String(periodDays)} onValueChange={(v) => setPeriodDays(parseInt(v))}>
            <SelectTrigger className="w-32 bg-slate-800 border-slate-700 text-white">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">Last 24h</SelectItem>
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="14">Last 14 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={fetchData} disabled={loading}>
            <Icons.refresh className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>
      
      {/* Feature Flags */}
      <Card className="bg-slate-800/50 border-slate-700 p-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Icons.settings className="h-5 w-5 text-slate-400" />
          Feature Flags
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="flex items-center justify-between p-4 bg-slate-900/50 rounded-lg">
            <div>
              <Label className="text-white font-medium">Luna Enabled</Label>
              <p className="text-xs text-slate-400">Master switch for UI</p>
            </div>
            <Switch
              checked={stats?.lunaEnabled ?? false}
              onCheckedChange={(v) => toggleFlag('luna_enabled', v)}
              disabled={updatingFlag === 'luna_enabled'}
            />
          </div>
          <div className="flex items-center justify-between p-4 bg-slate-900/50 rounded-lg">
            <div>
              <Label className="text-white font-medium">Shadow Mode</Label>
              <p className="text-xs text-slate-400">Detection only, no UI</p>
            </div>
            <Switch
              checked={stats?.shadowModeEnabled ?? false}
              onCheckedChange={(v) => toggleFlag('luna_shadow_mode', v)}
              disabled={updatingFlag === 'luna_shadow_mode'}
            />
          </div>
          <div className="flex items-center justify-between p-4 bg-slate-900/50 rounded-lg">
            <div>
              <Label className="text-white font-medium">Widget Enabled</Label>
              <p className="text-xs text-slate-400">Floating widget</p>
            </div>
            <Switch
              checked={stats?.widgetEnabled ?? false}
              onCheckedChange={(v) => toggleFlag('luna_widget_enabled', v)}
              disabled={updatingFlag === 'luna_widget_enabled'}
            />
          </div>
          <div className="flex items-center justify-between p-4 bg-slate-900/50 rounded-lg">
            <div>
              <Label className="text-white font-medium">P1 Features</Label>
              <p className="text-xs text-slate-400">Deal analysis, coaching</p>
            </div>
            <Switch
              checked={false}
              onCheckedChange={(v) => toggleFlag('luna_p1_features', v)}
              disabled={updatingFlag === 'luna_p1_features'}
            />
          </div>
        </div>
      </Card>
      
      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-slate-800/50 border-slate-700 p-6">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-amber-500/20">
              <Icons.mail className="h-5 w-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{stats?.totalMessagesCreated ?? 0}</p>
              <p className="text-sm text-slate-400">Messages Created</p>
            </div>
          </div>
        </Card>
        <Card className="bg-slate-800/50 border-slate-700 p-6">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-blue-500/20">
              <Icons.users className="h-5 w-5 text-blue-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{stats?.uniqueUsersReached ?? 0}</p>
              <p className="text-sm text-slate-400">Users Reached</p>
            </div>
          </div>
        </Card>
        <Card className="bg-slate-800/50 border-slate-700 p-6">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-green-500/20">
              <Icons.check className="h-5 w-5 text-green-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">
                {comparison ? (comparison.lunaAcceptanceRate * 100).toFixed(1) : 0}%
              </p>
              <p className="text-sm text-slate-400">Acceptance Rate</p>
            </div>
          </div>
        </Card>
        <Card className="bg-slate-800/50 border-slate-700 p-6">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-purple-500/20">
              <Icons.zap className="h-5 w-5 text-purple-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{comparison?.lunaActiveUsers ?? 0}</p>
              <p className="text-sm text-slate-400">Active Users</p>
            </div>
          </div>
        </Card>
      </div>
      
      {/* Comparison with Autopilot */}
      {comparison && (
        <Card className="bg-slate-800/50 border-slate-700 p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Icons.barChart className="h-5 w-5 text-slate-400" />
            Luna vs Autopilot Comparison
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-slate-400">Messages Created</h3>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-amber-400">Luna</span>
                    <span className="text-white">{comparison.lunaMessagesCreated}</span>
                  </div>
                  <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-amber-500"
                      style={{ width: `${Math.min(100, (comparison.lunaMessagesCreated / Math.max(1, comparison.autopilotProposalsCreated)) * 100)}%` }}
                    />
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-blue-400">Autopilot</span>
                    <span className="text-white">{comparison.autopilotProposalsCreated}</span>
                  </div>
                  <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500"
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>
              </div>
            </div>
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-slate-400">Acceptance Rate</h3>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-amber-400">Luna</span>
                    <span className="text-white">{(comparison.lunaAcceptanceRate * 100).toFixed(1)}%</span>
                  </div>
                  <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div className="h-full bg-amber-500" style={{ width: `${comparison.lunaAcceptanceRate * 100}%` }} />
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-blue-400">Autopilot</span>
                    <span className="text-white">{(comparison.autopilotAcceptanceRate * 100).toFixed(1)}%</span>
                  </div>
                  <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500" style={{ width: `${comparison.autopilotAcceptanceRate * 100}%` }} />
                  </div>
                </div>
              </div>
            </div>
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-slate-400">Active Users</h3>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-amber-400">Luna</span>
                    <span className="text-white">{comparison.lunaActiveUsers}</span>
                  </div>
                  <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-amber-500"
                      style={{ width: `${Math.min(100, (comparison.lunaActiveUsers / Math.max(1, comparison.autopilotActiveUsers)) * 100)}%` }}
                    />
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-blue-400">Autopilot</span>
                    <span className="text-white">{comparison.autopilotActiveUsers}</span>
                  </div>
                  <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500" style={{ width: '100%' }} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Card>
      )}
      
      {/* Messages by Status & Type */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="bg-slate-800/50 border-slate-700 p-6">
            <h2 className="text-lg font-semibold text-white mb-4">Messages by Status</h2>
            <div className="space-y-2">
              {Object.entries(stats.messagesByStatus).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <Badge className={getStatusColor(status)}>{status}</Badge>
                  <span className="text-white font-medium">{count}</span>
                </div>
              ))}
              {Object.keys(stats.messagesByStatus).length === 0 && (
                <p className="text-slate-400 text-sm">No messages yet</p>
              )}
            </div>
          </Card>
          <Card className="bg-slate-800/50 border-slate-700 p-6">
            <h2 className="text-lg font-semibold text-white mb-4">Messages by Type</h2>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {Object.entries(stats.messagesByType)
                .sort((a, b) => b[1] - a[1])
                .map(([type, count]) => (
                  <div key={type} className="flex items-center justify-between">
                    <span className="text-slate-300 text-sm truncate">{type}</span>
                    <span className="text-white font-medium">{count}</span>
                  </div>
                ))}
              {Object.keys(stats.messagesByType).length === 0 && (
                <p className="text-slate-400 text-sm">No messages yet</p>
              )}
            </div>
          </Card>
        </div>
      )}
      
      {/* Recent Messages Table */}
      <Card className="bg-slate-800/50 border-slate-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Recent Messages</h2>
          <div className="flex gap-2">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-32 bg-slate-900 border-slate-700 text-white">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All status</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="dismissed">Dismissed</SelectItem>
                <SelectItem value="snoozed">Snoozed</SelectItem>
                <SelectItem value="expired">Expired</SelectItem>
              </SelectContent>
            </Select>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-40 bg-slate-900 border-slate-700 text-white">
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All types</SelectItem>
                <SelectItem value="review_research">Review Research</SelectItem>
                <SelectItem value="prep_ready">Prep Ready</SelectItem>
                <SelectItem value="review_meeting_summary">Meeting Summary</SelectItem>
                <SelectItem value="prepare_outreach">Prepare Outreach</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="border-slate-700">
                <TableHead className="text-slate-400">User</TableHead>
                <TableHead className="text-slate-400">Type</TableHead>
                <TableHead className="text-slate-400">Title</TableHead>
                <TableHead className="text-slate-400">Status</TableHead>
                <TableHead className="text-slate-400">Priority</TableHead>
                <TableHead className="text-slate-400">Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {messages.map((msg) => (
                <TableRow key={msg.id} className="border-slate-700">
                  <TableCell className="text-slate-300">
                    {msg.userEmail || msg.userId.slice(0, 8)}
                  </TableCell>
                  <TableCell className="text-slate-300 font-mono text-xs">
                    {msg.messageType}
                  </TableCell>
                  <TableCell className="text-white max-w-[200px] truncate">
                    {msg.title}
                  </TableCell>
                  <TableCell>
                    <Badge className={getStatusColor(msg.status)}>{msg.status}</Badge>
                  </TableCell>
                  <TableCell className="text-slate-300">{msg.priority}</TableCell>
                  <TableCell className="text-slate-400 text-sm">
                    {formatDistanceToNow(new Date(msg.createdAt), { addSuffix: true, locale: nl })}
                  </TableCell>
                </TableRow>
              ))}
              {messages.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-slate-400 py-8">
                    No messages found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </Card>
    </div>
  )
}
