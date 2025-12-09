'use client'

import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { useTranslations } from 'next-intl'

export function OAuthButtons() {
    const supabase = createClientComponentClient()
    const [loadingGoogle, setLoadingGoogle] = useState(false)
    const [loadingMicrosoft, setLoadingMicrosoft] = useState(false)
    const t = useTranslations('auth')

    const handleGoogleLogin = async () => {
        setLoadingGoogle(true)
        try {
            const { error } = await supabase.auth.signInWithOAuth({
                provider: 'google',
                options: {
                    redirectTo: `${window.location.origin}/auth/callback`,
                    queryParams: {
                        access_type: 'offline',
                        prompt: 'consent',
                    },
                },
            })
            if (error) throw error
        } catch (error) {
            console.error('Google OAuth error:', error)
            setLoadingGoogle(false)
        }
    }

    const handleMicrosoftLogin = async () => {
        setLoadingMicrosoft(true)
        try {
            const { error } = await supabase.auth.signInWithOAuth({
                provider: 'azure',
                options: {
                    redirectTo: `${window.location.origin}/auth/callback`,
                    scopes: 'email profile openid',
                },
            })
            if (error) throw error
        } catch (error) {
            console.error('Microsoft OAuth error:', error)
            setLoadingMicrosoft(false)
        }
    }

    const isLoading = loadingGoogle || loadingMicrosoft

    return (
        <div className="grid gap-3">
            <Button
                variant="outline"
                onClick={handleGoogleLogin}
                disabled={isLoading}
                className="w-full h-11 font-medium"
            >
                {loadingGoogle ? (
                    <Icons.spinner className="mr-2 h-5 w-5 animate-spin" />
                ) : (
                    <Icons.google className="mr-2 h-5 w-5" />
                )}
                {t('continueWithGoogle')}
            </Button>

            <Button
                variant="outline"
                onClick={handleMicrosoftLogin}
                disabled={isLoading}
                className="w-full h-11 font-medium"
            >
                {loadingMicrosoft ? (
                    <Icons.spinner className="mr-2 h-5 w-5 animate-spin" />
                ) : (
                    <Icons.microsoft className="mr-2 h-5 w-5" />
                )}
                {t('continueWithMicrosoft')}
            </Button>
        </div>
    )
}

