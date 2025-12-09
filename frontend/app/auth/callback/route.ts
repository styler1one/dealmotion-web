import { createRouteHandlerClient } from '@supabase/auth-helpers-nextjs'
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
    const requestUrl = new URL(request.url)
    const code = requestUrl.searchParams.get('code')
    const error = requestUrl.searchParams.get('error')
    const errorDescription = requestUrl.searchParams.get('error_description')

    // Handle OAuth errors (user cancelled, access denied, etc.)
    if (error) {
        console.error('OAuth error:', error, errorDescription)
        
        // Map OAuth errors to user-friendly error codes
        let errorCode = 'oauth_error'
        if (error === 'access_denied') {
            errorCode = 'access_denied'
        } else if (error === 'server_error') {
            errorCode = 'server_error'
        }
        
        return NextResponse.redirect(
            new URL(`/login?error=${errorCode}`, requestUrl.origin)
        )
    }

    if (code) {
        const cookieStore = cookies()
        const supabase = createRouteHandlerClient({ cookies: () => cookieStore })
        
        try {
            const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)
            
            if (exchangeError) {
                console.error('Code exchange error:', exchangeError)
                return NextResponse.redirect(
                    new URL('/login?error=oauth_error', requestUrl.origin)
                )
            }
        } catch (err) {
            console.error('Unexpected error during code exchange:', err)
            return NextResponse.redirect(
                new URL('/login?error=oauth_error', requestUrl.origin)
            )
        }
    }

    // URL to redirect to after sign in process completes
    return NextResponse.redirect(new URL('/dashboard', requestUrl.origin))
}
