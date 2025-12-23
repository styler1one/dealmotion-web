'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { 
    Copy, 
    Check, 
    Users, 
    TrendingUp, 
    Wallet, 
    ExternalLink,
    Clock,
    ArrowUpRight,
    CreditCard,
    AlertCircle,
    Gift,
    ChevronRight,
    RefreshCw
} from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

interface AffiliateStats {
    total_clicks: number
    total_signups: number
    total_conversions: number
    conversion_rate: number
    total_earned_cents: number
    total_paid_cents: number
    current_balance_cents: number
    pending_commissions_cents: number
}

interface AffiliateData {
    id: string
    affiliate_code: string
    referral_url: string
    status: string
    stripe_connect_status: string
    stripe_payouts_enabled: boolean
}

interface Referral {
    id: string
    referred_email: string
    signup_at: string
    converted: boolean
    first_payment_at: string | null
    lifetime_revenue_cents: number
    lifetime_commission_cents: number
    status: string
}

interface Commission {
    id: string
    payment_type: string
    payment_amount_cents: number
    commission_amount_cents: number
    status: string
    payment_at: string
}

interface Payout {
    id: string
    amount_cents: number
    commission_count: number
    status: string
    created_at: string
    completed_at: string | null
}

interface DashboardData {
    affiliate: AffiliateData
    stats: AffiliateStats
    recent_referrals: Referral[]
    recent_commissions: Commission[]
    recent_payouts: Payout[]
}

export default function AffiliateDashboardPage() {
    const t = useTranslations('affiliate')
    const router = useRouter()
    const [loading, setLoading] = useState(true)
    const [applying, setApplying] = useState(false)
    const [isAffiliate, setIsAffiliate] = useState(false)
    const [dashboardData, setDashboardData] = useState<DashboardData | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [copied, setCopied] = useState(false)
    const [connectLoading, setConnectLoading] = useState(false)

    // Check affiliate status on load
    useEffect(() => {
        checkAffiliateStatus()
    }, [])

    const checkAffiliateStatus = async () => {
        try {
            setLoading(true)
            const response = await api.get<{ is_affiliate: boolean; affiliate?: AffiliateData }>('/api/v1/affiliate/status')
            
            if (response.data?.is_affiliate) {
                setIsAffiliate(true)
                // Load dashboard data
                await loadDashboard()
            } else {
                setIsAffiliate(false)
            }
        } catch (err) {
            console.error('Error checking affiliate status:', err)
            setError(t('errorLoading'))
        } finally {
            setLoading(false)
        }
    }

    const loadDashboard = async () => {
        try {
            const response = await api.get<DashboardData>('/api/v1/affiliate/dashboard')
            if (response.data) {
                setDashboardData(response.data)
            }
        } catch (err) {
            console.error('Error loading dashboard:', err)
            setError(t('errorLoading'))
        }
    }

    const handleApply = async () => {
        try {
            setApplying(true)
            setError(null)
            
            const response = await api.post<{ is_affiliate: boolean; affiliate?: AffiliateData }>('/api/v1/affiliate/apply', {
                application_notes: null // Could add a form for this
            })
            
            if (response.data?.is_affiliate) {
                setIsAffiliate(true)
                await loadDashboard()
            }
        } catch (err: any) {
            console.error('Error applying:', err)
            setError(err?.message || t('errorApplying'))
        } finally {
            setApplying(false)
        }
    }

    const copyReferralLink = async () => {
        if (!dashboardData?.affiliate?.referral_url) return
        
        try {
            await navigator.clipboard.writeText(dashboardData.affiliate.referral_url)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        } catch (err) {
            console.error('Failed to copy:', err)
        }
    }

    const handleConnectSetup = async () => {
        try {
            setConnectLoading(true)
            const returnUrl = `${window.location.origin}/dashboard/affiliate?connect=success`
            const refreshUrl = `${window.location.origin}/dashboard/affiliate?connect=refresh`
            
            const response = await api.post<{ url: string }>('/api/v1/affiliate/connect/onboarding', {
                return_url: returnUrl,
                refresh_url: refreshUrl
            })
            
            if (response.data?.url) {
                window.location.href = response.data.url
            }
        } catch (err: any) {
            console.error('Error setting up Connect:', err)
            setError(err?.message || t('errorConnect'))
        } finally {
            setConnectLoading(false)
        }
    }

    const formatCurrency = (cents: number) => {
        return new Intl.NumberFormat('nl-NL', {
            style: 'currency',
            currency: 'EUR'
        }).format(cents / 100)
    }

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString('nl-NL', {
            day: 'numeric',
            month: 'short',
            year: 'numeric'
        })
    }

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'active':
            case 'paid':
            case 'succeeded':
            case 'approved':
                return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
            case 'pending':
            case 'processing':
                return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
            case 'reversed':
            case 'failed':
            case 'churned':
                return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
            default:
                return 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400'
        }
    }

    // Loading state
    if (loading) {
        return (
            <div className="container mx-auto py-8 space-y-6">
                <Skeleton className="h-10 w-64" />
                <div className="grid gap-4 md:grid-cols-4">
                    {[1, 2, 3, 4].map(i => (
                        <Skeleton key={i} className="h-32" />
                    ))}
                </div>
                <Skeleton className="h-96" />
            </div>
        )
    }

    // Not an affiliate - show apply page
    if (!isAffiliate) {
        return (
            <div className="container mx-auto py-8 max-w-3xl">
                <Card>
                    <CardHeader className="text-center">
                        <div className="mx-auto mb-4 rounded-full bg-blue-100 dark:bg-blue-900/30 p-4 w-fit">
                            <Gift className="h-8 w-8 text-blue-600 dark:text-blue-400" />
                        </div>
                        <CardTitle className="text-2xl">{t('joinProgram.title')}</CardTitle>
                        <CardDescription className="text-base">
                            {t('joinProgram.subtitle')}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        {/* Benefits */}
                        <div className="grid gap-4 md:grid-cols-2">
                            <div className="flex gap-3 p-4 rounded-lg border">
                                <div className="flex-shrink-0">
                                    <TrendingUp className="h-5 w-5 text-blue-600" />
                                </div>
                                <div>
                                    <h4 className="font-medium">{t('joinProgram.benefit1Title')}</h4>
                                    <p className="text-sm text-muted-foreground">{t('joinProgram.benefit1Desc')}</p>
                                </div>
                            </div>
                            <div className="flex gap-3 p-4 rounded-lg border">
                                <div className="flex-shrink-0">
                                    <Wallet className="h-5 w-5 text-green-600" />
                                </div>
                                <div>
                                    <h4 className="font-medium">{t('joinProgram.benefit2Title')}</h4>
                                    <p className="text-sm text-muted-foreground">{t('joinProgram.benefit2Desc')}</p>
                                </div>
                            </div>
                            <div className="flex gap-3 p-4 rounded-lg border">
                                <div className="flex-shrink-0">
                                    <Users className="h-5 w-5 text-purple-600" />
                                </div>
                                <div>
                                    <h4 className="font-medium">{t('joinProgram.benefit3Title')}</h4>
                                    <p className="text-sm text-muted-foreground">{t('joinProgram.benefit3Desc')}</p>
                                </div>
                            </div>
                            <div className="flex gap-3 p-4 rounded-lg border">
                                <div className="flex-shrink-0">
                                    <Clock className="h-5 w-5 text-orange-600" />
                                </div>
                                <div>
                                    <h4 className="font-medium">{t('joinProgram.benefit4Title')}</h4>
                                    <p className="text-sm text-muted-foreground">{t('joinProgram.benefit4Desc')}</p>
                                </div>
                            </div>
                        </div>

                        {error && (
                            <Alert variant="destructive">
                                <AlertCircle className="h-4 w-4" />
                                <AlertDescription>{error}</AlertDescription>
                            </Alert>
                        )}

                        <div className="flex justify-center">
                            <Button 
                                size="lg" 
                                onClick={handleApply}
                                disabled={applying}
                            >
                                {applying && <RefreshCw className="mr-2 h-4 w-4 animate-spin" />}
                                {t('joinProgram.applyButton')}
                                <ChevronRight className="ml-2 h-4 w-4" />
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>
        )
    }

    // Affiliate dashboard
    const stats = dashboardData?.stats
    const affiliate = dashboardData?.affiliate

    return (
        <div className="container mx-auto py-8 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold">{t('dashboard.title')}</h1>
                    <p className="text-muted-foreground">{t('dashboard.subtitle')}</p>
                </div>
                <Badge className={cn(getStatusColor(affiliate?.status || 'pending'))}>
                    {affiliate?.status}
                </Badge>
            </div>

            {error && (
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>{error}</AlertDescription>
                </Alert>
            )}

            {/* Referral Link Card */}
            <Card>
                <CardHeader>
                    <CardTitle>{t('dashboard.referralLink')}</CardTitle>
                    <CardDescription>{t('dashboard.referralLinkDesc')}</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex gap-2">
                        <code className="flex-1 px-3 py-2 bg-muted rounded-md text-sm font-mono truncate">
                            {affiliate?.referral_url}
                        </code>
                        <Button variant="outline" onClick={copyReferralLink}>
                            {copied ? (
                                <Check className="h-4 w-4 text-green-600" />
                            ) : (
                                <Copy className="h-4 w-4" />
                            )}
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* Stats Grid */}
            <div className="grid gap-4 md:grid-cols-4">
                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription>{t('dashboard.stats.clicks')}</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{stats?.total_clicks || 0}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription>{t('dashboard.stats.signups')}</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-baseline gap-2">
                            <span className="text-2xl font-bold">{stats?.total_signups || 0}</span>
                            <span className="text-sm text-muted-foreground">
                                ({stats?.conversion_rate?.toFixed(1) || 0}%)
                            </span>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription>{t('dashboard.stats.conversions')}</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{stats?.total_conversions || 0}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription>{t('dashboard.stats.totalEarned')}</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-green-600">
                            {formatCurrency(stats?.total_earned_cents || 0)}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Balance & Payout Section */}
            <div className="grid gap-4 md:grid-cols-2">
                {/* Balance Card */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Wallet className="h-5 w-5" />
                            {t('dashboard.balance.title')}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex items-baseline justify-between">
                            <span className="text-sm text-muted-foreground">{t('dashboard.balance.available')}</span>
                            <span className="text-2xl font-bold text-green-600">
                                {formatCurrency(stats?.current_balance_cents || 0)}
                            </span>
                        </div>
                        <div className="flex items-baseline justify-between">
                            <span className="text-sm text-muted-foreground">{t('dashboard.balance.pending')}</span>
                            <span className="text-lg text-muted-foreground">
                                {formatCurrency(stats?.pending_commissions_cents || 0)}
                            </span>
                        </div>
                        <div className="flex items-baseline justify-between">
                            <span className="text-sm text-muted-foreground">{t('dashboard.balance.paid')}</span>
                            <span className="text-lg">
                                {formatCurrency(stats?.total_paid_cents || 0)}
                            </span>
                        </div>
                    </CardContent>
                </Card>

                {/* Stripe Connect Card */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <CreditCard className="h-5 w-5" />
                            {t('dashboard.payout.title')}
                        </CardTitle>
                        <CardDescription>{t('dashboard.payout.desc')}</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {affiliate?.stripe_payouts_enabled ? (
                            <div className="flex items-center gap-2 text-green-600">
                                <Check className="h-5 w-5" />
                                <span>{t('dashboard.payout.enabled')}</span>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                <p className="text-sm text-muted-foreground">
                                    {t('dashboard.payout.setupRequired')}
                                </p>
                                <Button 
                                    onClick={handleConnectSetup}
                                    disabled={connectLoading}
                                >
                                    {connectLoading && <RefreshCw className="mr-2 h-4 w-4 animate-spin" />}
                                    {t('dashboard.payout.setupButton')}
                                    <ExternalLink className="ml-2 h-4 w-4" />
                                </Button>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Activity Tabs */}
            <Tabs defaultValue="referrals" className="w-full">
                <TabsList>
                    <TabsTrigger value="referrals">{t('dashboard.tabs.referrals')}</TabsTrigger>
                    <TabsTrigger value="commissions">{t('dashboard.tabs.commissions')}</TabsTrigger>
                    <TabsTrigger value="payouts">{t('dashboard.tabs.payouts')}</TabsTrigger>
                </TabsList>

                <TabsContent value="referrals" className="mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>{t('dashboard.referrals.title')}</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {dashboardData?.recent_referrals && dashboardData.recent_referrals.length > 0 ? (
                                <div className="space-y-3">
                                    {dashboardData.recent_referrals.map((referral) => (
                                        <div 
                                            key={referral.id} 
                                            className="flex items-center justify-between py-3 border-b last:border-0"
                                        >
                                            <div>
                                                <p className="font-medium">{referral.referred_email}</p>
                                                <p className="text-sm text-muted-foreground">
                                                    {formatDate(referral.signup_at)}
                                                </p>
                                            </div>
                                            <div className="text-right">
                                                <Badge className={cn(getStatusColor(referral.status))}>
                                                    {referral.converted ? t('dashboard.referrals.converted') : t('dashboard.referrals.pending')}
                                                </Badge>
                                                {referral.lifetime_commission_cents > 0 && (
                                                    <p className="text-sm text-green-600 mt-1">
                                                        {formatCurrency(referral.lifetime_commission_cents)}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-center text-muted-foreground py-8">
                                    {t('dashboard.referrals.empty')}
                                </p>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="commissions" className="mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>{t('dashboard.commissions.title')}</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {dashboardData?.recent_commissions && dashboardData.recent_commissions.length > 0 ? (
                                <div className="space-y-3">
                                    {dashboardData.recent_commissions.map((commission) => (
                                        <div 
                                            key={commission.id} 
                                            className="flex items-center justify-between py-3 border-b last:border-0"
                                        >
                                            <div>
                                                <p className="font-medium">
                                                    {commission.payment_type === 'subscription' 
                                                        ? t('dashboard.commissions.subscription')
                                                        : t('dashboard.commissions.creditPack')
                                                    }
                                                </p>
                                                <p className="text-sm text-muted-foreground">
                                                    {formatDate(commission.payment_at)}
                                                </p>
                                            </div>
                                            <div className="text-right">
                                                <p className="font-medium text-green-600">
                                                    +{formatCurrency(commission.commission_amount_cents)}
                                                </p>
                                                <Badge className={cn("text-xs", getStatusColor(commission.status))}>
                                                    {commission.status}
                                                </Badge>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-center text-muted-foreground py-8">
                                    {t('dashboard.commissions.empty')}
                                </p>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="payouts" className="mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>{t('dashboard.payouts.title')}</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {dashboardData?.recent_payouts && dashboardData.recent_payouts.length > 0 ? (
                                <div className="space-y-3">
                                    {dashboardData.recent_payouts.map((payout) => (
                                        <div 
                                            key={payout.id} 
                                            className="flex items-center justify-between py-3 border-b last:border-0"
                                        >
                                            <div>
                                                <p className="font-medium">
                                                    {formatCurrency(payout.amount_cents)}
                                                </p>
                                                <p className="text-sm text-muted-foreground">
                                                    {payout.commission_count} {t('dashboard.payouts.commissions')}
                                                </p>
                                            </div>
                                            <div className="text-right">
                                                <Badge className={cn(getStatusColor(payout.status))}>
                                                    {payout.status}
                                                </Badge>
                                                <p className="text-sm text-muted-foreground mt-1">
                                                    {payout.completed_at 
                                                        ? formatDate(payout.completed_at)
                                                        : formatDate(payout.created_at)
                                                    }
                                                </p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-center text-muted-foreground py-8">
                                    {t('dashboard.payouts.empty')}
                                </p>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    )
}

