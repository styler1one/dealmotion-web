'use client'

import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Icons } from '@/components/icons'
import { OAuthButtons } from './oauth-buttons'
import { useTranslations } from 'next-intl'
import { CheckCircle2, Mail } from 'lucide-react'
import { getAffiliateSignupData, clearAffiliateData } from '@/lib/affiliate'

interface AuthFormProps {
    view: 'login' | 'signup'
}

export function AuthForm({ view }: AuthFormProps) {
    const router = useRouter()
    const supabase = createClientComponentClient()
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [signupSuccess, setSignupSuccess] = useState(false)
    const t = useTranslations('authForm')

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setLoading(true)
        setError(null)

        try {
            if (view === 'signup') {
                // Get affiliate data if present
                const affiliateData = getAffiliateSignupData()
                
                const { data, error } = await supabase.auth.signUp({
                    email,
                    password,
                    options: {
                        emailRedirectTo: `${location.origin}/auth/callback`,
                        data: {
                            // Pass affiliate info in user metadata
                            // Will be processed by handle_new_user trigger or backend
                            affiliate_code: affiliateData.affiliateCode,
                            affiliate_click_id: affiliateData.clickId,
                        },
                    },
                })
                if (error) throw error
                
                // Check if email confirmation is required
                // If user.identities is empty or user is not confirmed, show check email message
                if (data.user && !data.user.confirmed_at && data.user.identities?.length === 0) {
                    // User already exists
                    setError(t('userAlreadyExists'))
                } else if (data.user && !data.session) {
                    // Email confirmation required - show success message
                    setSignupSuccess(true)
                    // Clear affiliate data after successful signup
                    clearAffiliateData()
                } else {
                    // Email confirmation disabled - user is logged in
                    // Clear affiliate data after successful signup
                    clearAffiliateData()
                    router.refresh()
                    router.push('/dashboard')
                }
            } else {
                const { error } = await supabase.auth.signInWithPassword({
                    email,
                    password,
                })
                if (error) throw error
                router.refresh()
                router.push('/dashboard')
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred')
        } finally {
            setLoading(false)
        }
    }

    // Show success message after signup
    if (signupSuccess) {
        return (
            <div className="grid gap-6">
                <div className="flex flex-col items-center justify-center py-8 text-center">
                    <div className="mb-4 rounded-full bg-green-100 p-3 dark:bg-green-900/30">
                        <Mail className="h-8 w-8 text-green-600 dark:text-green-400" />
                    </div>
                    <h3 className="mb-2 text-xl font-semibold">{t('checkYourEmail')}</h3>
                    <p className="mb-4 text-muted-foreground">
                        {t('confirmationEmailSent', { email })}
                    </p>
                    <Button 
                        variant="outline" 
                        onClick={() => router.push('/login')}
                        className="mt-2"
                    >
                        {t('backToLogin')}
                    </Button>
                </div>
            </div>
        )
    }

    return (
        <div className="grid gap-6">
            {/* OAuth Buttons - Most prominent */}
            <OAuthButtons />

            {/* Divider */}
            <div className="relative">
                <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-background px-2 text-muted-foreground">
                        {t('orContinueWith')}
                    </span>
                </div>
            </div>

            {/* Email/Password Form */}
            <form onSubmit={handleSubmit}>
                <div className="grid gap-4">
                    <div className="grid gap-2">
                        <Label htmlFor="email">{t('email')}</Label>
                        <Input
                            id="email"
                            placeholder={t('emailPlaceholder')}
                            type="email"
                            autoCapitalize="none"
                            autoComplete="email"
                            autoCorrect="off"
                            disabled={loading}
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                        />
                    </div>
                    <div className="grid gap-2">
                        <Label htmlFor="password">{t('password')}</Label>
                        <Input
                            id="password"
                            type="password"
                            autoCapitalize="none"
                            autoComplete="current-password"
                            disabled={loading}
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </div>
                    {error && (
                        <Alert variant="destructive">
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}
                    <Button disabled={loading}>
                        {loading && (
                            <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
                        )}
                        {view === 'login' ? t('signInEmail') : t('signUpEmail')}
                    </Button>
                </div>
            </form>
        </div>
    )
}
