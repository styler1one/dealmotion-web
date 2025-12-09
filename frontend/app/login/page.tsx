'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { AuthForm } from '@/components/auth/auth-form'
import { Icons } from '@/components/icons'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useTranslations } from 'next-intl'
import { Logo } from '@/components/dealmotion-logo'

export default function LoginPage() {
    const searchParams = useSearchParams()
    const error = searchParams.get('error')
    const t = useTranslations('authForm')
    const tAuth = useTranslations('auth.login')

    // Error messages for OAuth errors
    const errorMessages: Record<string, string> = {
        oauth_error: t('errors.oauthError'),
        access_denied: t('errors.accessDenied'),
        server_error: t('errors.serverError'),
    }

    const errorMessage = error ? errorMessages[error] || t('errors.genericSignIn') : null

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

                        {/* OAuth Error Alert */}
                        {errorMessage && (
                            <Alert variant="destructive" className="mb-6">
                                <Icons.alertCircle className="h-4 w-4" />
                                <AlertDescription>{errorMessage}</AlertDescription>
                            </Alert>
                        )}

                        <AuthForm view="login" />
                    </div>

                    {/* Footer Link */}
                    <p className="text-center text-sm text-muted-foreground">
                        {tAuth('noAccount')}{' '}
                        <Link
                            href="/signup"
                            className="font-medium text-blue-600 hover:text-blue-500 underline underline-offset-4"
                        >
                            {tAuth('signUp')}
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
