'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { adminApi } from '@/lib/admin-api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

interface AffiliateDetail {
  affiliate: {
    id: string
    user_id: string
    organization_id: string
    affiliate_code: string
    status: string
    stripe_connect_account_id: string | null
    stripe_connect_status: string
    stripe_payouts_enabled: boolean
    commission_rate_subscription: number
    commission_rate_credits: number
    total_clicks: number
    total_signups: number
    total_conversions: number
    total_earned_cents: number
    total_paid_cents: number
    current_balance_cents: number
    created_at: string
    activated_at: string | null
  }
  user: {
    id: string
    email: string
    full_name: string | null
    created_at: string
  }
  organization: {
    id: string
    name: string
    created_at: string
  }
  recent_referrals: Array<{
    id: string
    referred_user_id: string
    signup_at: string
    converted: boolean
    converted_at: string | null
  }>
  recent_commissions: Array<{
    id: string
    payment_amount_cents: number
    commission_amount_cents: number
    status: string
    payment_at: string
  }>
  recent_payouts: Array<{
    id: string
    amount_cents: number
    status: string
    created_at: string
  }>
  stats: {
    total_clicks: number
    total_signups: number
    total_conversions: number
    conversion_rate: number
    total_earned_cents: number
    total_paid_cents: number
    current_balance_cents: number
    pending_commissions_cents: number
  }
}

export default function AffiliateDetailPage() {
  const router = useRouter()
  const params = useParams()
  const affiliateId = params.id as string

  const [data, setData] = useState<AffiliateDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [showStatusDialog, setShowStatusDialog] = useState(false)
  const [pendingStatus, setPendingStatus] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      const response = await adminApi.getAffiliateDetail(affiliateId)
      setData(response)
    } catch (err: any) {
      console.error('Failed to fetch affiliate:', err)
      setError(err?.message || 'Failed to load affiliate')
    } finally {
      setLoading(false)
    }
  }, [affiliateId])

  useEffect(() => {
    if (affiliateId) {
      fetchData()
    }
  }, [affiliateId, fetchData])

  const formatCurrency = (cents: number) => {
    return new Intl.NumberFormat('nl-NL', {
      style: 'currency',
      currency: 'EUR'
    }).format(cents / 100)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('nl-NL', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
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
      <Badge className={cn('text-sm', colors[status] || colors.pending)}>
        {status}
      </Badge>
    )
  }

  const handleStatusChange = async (newStatus: string) => {
    setPendingStatus(newStatus)
    setShowStatusDialog(true)
  }

  const confirmStatusChange = async () => {
    if (!pendingStatus) return
    
    try {
      setActionLoading(true)
      await adminApi.updateAffiliateStatus(affiliateId, pendingStatus)
      await fetchData()
    } catch (err: any) {
      console.error('Failed to update status:', err)
      setError(err?.message || 'Failed to update status')
    } finally {
      setActionLoading(false)
      setShowStatusDialog(false)
      setPendingStatus(null)
    }
  }

  const handleTriggerPayout = async () => {
    try {
      setActionLoading(true)
      await adminApi.triggerAffiliatePayout(affiliateId)
      await fetchData()
    } catch (err: any) {
      console.error('Failed to trigger payout:', err)
      setError(err?.message || 'Failed to trigger payout')
    } finally {
      setActionLoading(false)
    }
  }

  const handleSyncConnect = async () => {
    try {
      setActionLoading(true)
      await adminApi.syncAffiliateConnect(affiliateId)
      await fetchData()
    } catch (err: any) {
      console.error('Failed to sync Connect:', err)
      setError(err?.message || 'Failed to sync Connect status')
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Icons.spinner className="h-8 w-8 animate-spin text-teal-500" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <Icons.alertTriangle className="h-12 w-12 text-red-500" />
        <p className="text-slate-600">{error || 'Affiliate not found'}</p>
        <Button variant="outline" onClick={() => router.push('/admin/affiliates')}>
          Back to Affiliates
        </Button>
      </div>
    )
  }

  const { affiliate, user, organization, recent_referrals, recent_commissions, recent_payouts, stats } = data
  const displayName = user.full_name || user.email?.split('@')[0] || 'Unknown'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <Button 
            variant="ghost" 
            size="icon"
            onClick={() => router.push('/admin/affiliates')}
          >
            <Icons.arrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                {displayName}
              </h1>
              {getStatusBadge(affiliate.status)}
            </div>
            <p className="text-sm text-slate-500">{user.email}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleSyncConnect}
            disabled={actionLoading}
          >
            {actionLoading ? (
              <Icons.spinner className="h-4 w-4 animate-spin" />
            ) : (
              <Icons.refresh className="h-4 w-4 mr-2" />
            )}
            Sync Connect
          </Button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-sm text-slate-500 mb-1">Total Clicks</div>
            <div className="text-2xl font-bold">{stats.total_clicks}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-sm text-slate-500 mb-1">Signups</div>
            <div className="text-2xl font-bold">{stats.total_signups}</div>
            <div className="text-xs text-slate-400">{stats.conversion_rate}% to conversion</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-sm text-slate-500 mb-1">Total Earned</div>
            <div className="text-2xl font-bold text-green-600">{formatCurrency(stats.total_earned_cents)}</div>
            <div className="text-xs text-slate-400">{formatCurrency(stats.pending_commissions_cents)} pending</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-sm text-slate-500 mb-1">Current Balance</div>
            <div className="text-2xl font-bold">{formatCurrency(stats.current_balance_cents)}</div>
            <div className="text-xs text-slate-400">{formatCurrency(stats.total_paid_cents)} paid out</div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Affiliate Info */}
        <Card>
          <CardHeader>
            <CardTitle>Affiliate Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-slate-500">Affiliate Code</div>
                <code className="font-mono bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded text-sm">
                  {affiliate.affiliate_code}
                </code>
              </div>
              <div>
                <div className="text-slate-500">Referral URL</div>
                <code className="font-mono bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded text-xs break-all">
                  dealmotion.ai?ref={affiliate.affiliate_code}
                </code>
              </div>
              <div>
                <div className="text-slate-500">Commission (Subscription)</div>
                <div className="font-medium">{(affiliate.commission_rate_subscription * 100).toFixed(0)}%</div>
              </div>
              <div>
                <div className="text-slate-500">Commission (Credits)</div>
                <div className="font-medium">{(affiliate.commission_rate_credits * 100).toFixed(0)}%</div>
              </div>
              <div>
                <div className="text-slate-500">Created</div>
                <div>{formatDate(affiliate.created_at)}</div>
              </div>
              <div>
                <div className="text-slate-500">Activated</div>
                <div>{affiliate.activated_at ? formatDate(affiliate.activated_at) : 'Not yet'}</div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Stripe Connect */}
        <Card>
          <CardHeader>
            <CardTitle>Stripe Connect</CardTitle>
            <CardDescription>Payout configuration</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-slate-500">Status</div>
                <Badge className={cn(
                  'mt-1',
                  affiliate.stripe_payouts_enabled 
                    ? 'bg-green-100 text-green-700' 
                    : 'bg-yellow-100 text-yellow-700'
                )}>
                  {affiliate.stripe_connect_status}
                </Badge>
              </div>
              <div>
                <div className="text-slate-500">Payouts Enabled</div>
                <div className="font-medium">{affiliate.stripe_payouts_enabled ? 'Yes' : 'No'}</div>
              </div>
              <div className="col-span-2">
                <div className="text-slate-500">Connect Account ID</div>
                <code className="font-mono text-xs">
                  {affiliate.stripe_connect_account_id || 'Not connected'}
                </code>
              </div>
            </div>
            {affiliate.stripe_payouts_enabled && stats.current_balance_cents > 0 && (
              <Button 
                onClick={handleTriggerPayout}
                disabled={actionLoading}
                className="w-full mt-4"
              >
                {actionLoading ? (
                  <Icons.spinner className="h-4 w-4 animate-spin mr-2" />
                ) : null}
                Trigger Payout ({formatCurrency(stats.current_balance_cents)})
              </Button>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Status Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Status Management</CardTitle>
          <CardDescription>Change affiliate status</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            <Button
              variant={affiliate.status === 'active' ? 'default' : 'outline'}
              size="sm"
              onClick={() => handleStatusChange('active')}
              disabled={affiliate.status === 'active' || actionLoading}
            >
              Activate
            </Button>
            <Button
              variant={affiliate.status === 'paused' ? 'default' : 'outline'}
              size="sm"
              onClick={() => handleStatusChange('paused')}
              disabled={affiliate.status === 'paused' || actionLoading}
            >
              Pause
            </Button>
            <Button
              variant={affiliate.status === 'suspended' ? 'destructive' : 'outline'}
              size="sm"
              onClick={() => handleStatusChange('suspended')}
              disabled={affiliate.status === 'suspended' || actionLoading}
            >
              Suspend
            </Button>
            <Button
              variant={affiliate.status === 'rejected' ? 'destructive' : 'outline'}
              size="sm"
              onClick={() => handleStatusChange('rejected')}
              disabled={affiliate.status === 'rejected' || actionLoading}
            >
              Reject
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Recent Activity */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recent Referrals */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Referrals</CardTitle>
          </CardHeader>
          <CardContent>
            {recent_referrals.length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-4">No referrals yet</p>
            ) : (
              <div className="space-y-3">
                {recent_referrals.map((r) => (
                  <div key={r.id} className="flex items-center justify-between text-sm">
                    <div>
                      <div className="font-mono text-xs text-slate-600">
                        {r.referred_user_id.substring(0, 8)}...
                      </div>
                      <div className="text-xs text-slate-400">
                        {formatDate(r.signup_at)}
                      </div>
                    </div>
                    <Badge className={cn(
                      'text-xs',
                      r.converted 
                        ? 'bg-green-100 text-green-700' 
                        : 'bg-slate-100 text-slate-600'
                    )}>
                      {r.converted ? 'Converted' : 'Pending'}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Commissions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Commissions</CardTitle>
          </CardHeader>
          <CardContent>
            {recent_commissions.length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-4">No commissions yet</p>
            ) : (
              <div className="space-y-3">
                {recent_commissions.map((c) => (
                  <div key={c.id} className="flex items-center justify-between text-sm">
                    <div>
                      <div className="font-medium text-green-600">
                        {formatCurrency(c.commission_amount_cents)}
                      </div>
                      <div className="text-xs text-slate-400">
                        from {formatCurrency(c.payment_amount_cents)}
                      </div>
                    </div>
                    <Badge className={cn(
                      'text-xs',
                      c.status === 'approved' ? 'bg-green-100 text-green-700' :
                      c.status === 'pending' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-slate-100 text-slate-600'
                    )}>
                      {c.status}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Payouts */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Payouts</CardTitle>
          </CardHeader>
          <CardContent>
            {recent_payouts.length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-4">No payouts yet</p>
            ) : (
              <div className="space-y-3">
                {recent_payouts.map((p) => (
                  <div key={p.id} className="flex items-center justify-between text-sm">
                    <div>
                      <div className="font-medium">
                        {formatCurrency(p.amount_cents)}
                      </div>
                      <div className="text-xs text-slate-400">
                        {formatDate(p.created_at)}
                      </div>
                    </div>
                    <Badge className={cn(
                      'text-xs',
                      p.status === 'succeeded' ? 'bg-green-100 text-green-700' :
                      p.status === 'pending' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-slate-100 text-slate-600'
                    )}>
                      {p.status}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Status Change Dialog */}
      <AlertDialog open={showStatusDialog} onOpenChange={setShowStatusDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Change Affiliate Status</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to change the status to "{pendingStatus}"?
              {pendingStatus === 'suspended' && (
                <span className="block mt-2 text-red-600">
                  This will prevent the affiliate from earning new commissions.
                </span>
              )}
              {pendingStatus === 'rejected' && (
                <span className="block mt-2 text-red-600">
                  This will permanently reject the affiliate application.
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmStatusChange}
              className={cn(
                pendingStatus === 'suspended' || pendingStatus === 'rejected'
                  ? 'bg-red-600 hover:bg-red-700'
                  : ''
              )}
            >
              Confirm
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

