'use client'

import { useEffect, useState } from 'react'
import { adminApi } from '@/lib/admin-api'
import { StatsCard } from '@/components/admin/stats-card'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'
import type { BillingOverview, TransactionItem, FailedPaymentItem } from '@/types/admin'

export default function AdminBillingPage() {
  const [overview, setOverview] = useState<BillingOverview | null>(null)
  const [transactions, setTransactions] = useState<TransactionItem[]>([])
  const [failedPayments, setFailedPayments] = useState<FailedPaymentItem[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    try {
      setLoading(true)
      const [overviewData, transactionsData, failedData] = await Promise.all([
        adminApi.getBillingOverview(),
        adminApi.getTransactions({ limit: 20 }),
        adminApi.getFailedPayments(),
      ])
      setOverview(overviewData)
      setTransactions(transactionsData.transactions)
      setFailedPayments(failedData.failedPayments)
    } catch (err) {
      console.error('Failed to fetch billing data:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

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
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Billing Overview</h1>
        <Button onClick={fetchData}>
          <Icons.refresh className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="MRR"
          value={overview?.mrrFormatted || '€0.00'}
          icon="creditCard"
          iconColor="text-purple-500"
          description="Monthly Recurring Revenue"
        />
        <StatsCard
          title="ARR"
          value={overview?.arrFormatted || '€0.00'}
          icon="trendingUp"
          iconColor="text-green-500"
          description="Annual Recurring Revenue"
        />
        <StatsCard
          title="Paid Users"
          value={overview?.paidUsers || 0}
          icon="users"
          iconColor="text-blue-500"
          description={`${overview?.freeUsers || 0} free users`}
        />
        <StatsCard
          title="Churn Rate"
          value={`${overview?.churnRate30d || 0}%`}
          icon="userMinus"
          iconColor={(overview?.churnRate30d || 0) > 5 ? 'text-red-500' : 'text-green-500'}
          description="Last 30 days"
        />
      </div>

      {/* Plan Distribution */}
      {overview && Object.keys(overview.planDistribution).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Plan Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              {Object.entries(overview.planDistribution).map(([plan, count]) => {
                const total = Object.values(overview.planDistribution).reduce((a, b) => a + b, 0)
                const percentage = Math.round((count / total) * 100)
                const colors: Record<string, string> = {
                  free: 'bg-slate-500',
                  pro_solo: 'bg-blue-500',
                  unlimited_solo: 'bg-purple-500',
                  enterprise: 'bg-amber-500',
                }
                const labels: Record<string, string> = {
                  free: 'Free',
                  pro_solo: 'Pro Solo',
                  unlimited_solo: 'Unlimited',
                  enterprise: 'Enterprise',
                }
                
                return (
                  <div key={plan} className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium capitalize">
                        {labels[plan] || plan}
                      </span>
                      <span className="text-sm text-slate-500">{count}</span>
                    </div>
                    <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                      <div 
                        className={cn('h-full rounded-full', colors[plan] || 'bg-teal-500')}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                    <div className="text-xs text-slate-500 mt-1">{percentage}%</div>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Failed Payments */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Failed Payments
              {failedPayments.length > 0 && (
                <span className="px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-xs font-medium">
                  {failedPayments.length}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {failedPayments.length > 0 ? (
              <div className="space-y-3">
                {failedPayments.map((payment) => (
                  <div 
                    key={payment.id}
                    className="flex items-center justify-between p-3 bg-red-50 dark:bg-red-900/10 rounded-lg border border-red-200 dark:border-red-800"
                  >
                    <div>
                      <div className="font-medium text-sm">{payment.customerEmail}</div>
                      <div className="text-xs text-slate-500">
                        {payment.organizationName || 'Unknown org'} • {payment.attemptCount} attempts
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-medium text-red-600">{payment.amountFormatted}</div>
                      {payment.nextAttempt && (
                        <div className="text-xs text-slate-500">
                          Retry: {new Date(payment.nextAttempt).toLocaleDateString()}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-slate-500">
                <Icons.checkCircle className="h-8 w-8 text-green-500 mb-2" />
                <span className="text-sm">No failed payments</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Transactions */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Transactions</CardTitle>
          </CardHeader>
          <CardContent>
            {transactions.length > 0 ? (
              <div className="space-y-3">
                {transactions.slice(0, 10).map((tx) => (
                  <div 
                    key={tx.id}
                    className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800 rounded-lg"
                  >
                    <div>
                      <div className="font-medium text-sm">
                        {tx.organizationName || 'Unknown'}
                      </div>
                      <div className="text-xs text-slate-500 capitalize">
                        {tx.type} • {tx.status}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={cn(
                        'font-medium',
                        tx.type === 'refund' ? 'text-red-500' : 'text-green-500'
                      )}>
                        {tx.type === 'refund' ? '-' : '+'}{tx.amountFormatted}
                      </div>
                      <div className="text-xs text-slate-500">
                        {new Date(tx.createdAt).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-slate-500">
                <Icons.creditCard className="h-8 w-8 opacity-50 mb-2" />
                <span className="text-sm">No transactions yet</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

