'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { useEffect, useState } from 'react'
import { AuthForm } from '@/components/auth/auth-form'
import { Icons } from '@/components/icons'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useTranslations } from 'next-intl'
import { Logo } from '@/components/dealmotion-logo'
import { 
    getStoredAffiliateData,
    validateAffiliateCode,
    getAffiliateDisplayInfo
} from '@/lib/affiliate'
import { UserCheck } from 'lucide-react'

export default function SignupPage() {
    const searchParams = useSearchParams()
    const error = searchParams.get('error')
    const t = useTranslations('authForm')
    const tAuth = useTranslations('auth.signup')
    const tAffiliate = useTranslations('affiliate')
    
    // Affiliate state
    const [affiliateInfo, setAffiliateInfo] = useState<{
        hasAffiliate: boolean
        affiliateName: string | null
        code: string | null
    }>({ hasAffiliate: false, affiliateName: null, code: null })
    
    // Check for affiliate info to display banner (tracking is handled globally by AffiliateTracker)
    useEffect(() => {
        const initAffiliate = async () => {
            // Get stored affiliate data (set by global AffiliateTracker)
            const affiliateData = getStoredAffiliateData()
            
            if (affiliateData) {
                // Validate the code to get affiliate name for display
                if (!affiliateData.validated) {
                    const validation = await validateAffiliateCode(affiliateData.code)
                    if (validation.valid) {
                        setAffiliateInfo({
                            hasAffiliate: true,
                            affiliateName: validation.affiliateName,
                            code: affiliateData.code,
                        })
                    }
                } else {
                    // Already validated, use display info
                    const stored = getAffiliateDisplayInfo()
                    setAffiliateInfo(stored)
                }
            }
        }
        
        initAffiliate()
    }, [searchParams])

    // Error messages for OAuth errors
    const errorMessages: Record<string, string> = {
        oauth_error: t('errors.oauthError'),
        access_denied: t('errors.accessDenied'),
        server_error: t('errors.serverError'),
    }

    const errorMessage = error ? errorMessages[error] || t('errors.genericSignUp') : null

    return (
        <div className="min-h-screen flex flex-col bg-gradient-to-br from-slate-50 to-blue-50 dark:from-slate-900 dark:to-slate-950">
            {/* Header */}
            <header className="p-4">
                <Link href="/" className="w-fit">
                    <Logo />
                </Link>
            </header>

            {/* Main Content */}
            <main className="flex-1 flex items-center justify-center p-4">
                <div className="w-full max-w-[400px] space-y-6">
                    {/* Card */}
                    <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl border dark:border-slate-800 p-8">
                        <div className="flex flex-col space-y-2 text-center mb-6">
                            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                                {tAuth('title')}
                            </h1>
                            <p className="text-sm text-muted-foreground">
                                {tAuth('subtitle')}
                            </p>
                        </div>

                        {/* Affiliate Referral Banner */}
                        {affiliateInfo.hasAffiliate && (
                            <div className="mb-6 flex items-center gap-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 p-3 border border-blue-200 dark:border-blue-800">
                                <div className="flex-shrink-0">
                                    <UserCheck className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                                </div>
                                <div className="text-sm">
                                    <p className="font-medium text-blue-900 dark:text-blue-100">
                                        {affiliateInfo.affiliateName 
                                            ? tAffiliate('referredBy', { name: affiliateInfo.affiliateName })
                                            : tAffiliate('referredByPartner')
                                        }
                                    </p>
                                </div>
                            </div>
                        )}

                        {/* OAuth Error Alert */}
                        {errorMessage && (
                            <Alert variant="destructive" className="mb-6">
                                <Icons.alertCircle className="h-4 w-4" />
                                <AlertDescription>{errorMessage}</AlertDescription>
                            </Alert>
                        )}

                        <AuthForm view="signup" />

                        {/* Terms */}
                        <p className="mt-6 text-center text-xs text-muted-foreground">
                            {t('termsPrefix')}{' '}
                            <Link href="/terms" className="underline hover:text-foreground">
                                {t('termsOfService')}
                            </Link>{' '}
                            {t('and')}{' '}
                            <Link href="/privacy" className="underline hover:text-foreground">
                                {t('privacyPolicy')}
                            </Link>
                        </p>
                    </div>

                    {/* Footer Link */}
                    <p className="text-center text-sm text-muted-foreground">
                        {tAuth('hasAccount')}{' '}
                        <Link
                            href="/login"
                            className="font-medium text-blue-600 hover:text-blue-500 underline underline-offset-4"
                        >
                            {tAuth('logIn')}
                        </Link>
                    </p>
                </div>
            </main>

            {/* Footer */}
            <footer className="p-4 text-center text-sm text-muted-foreground">
                <p>© {new Date().getFullYear()} DealMotion. All rights reserved.</p>
            </footer>
        </div>
    )
}
