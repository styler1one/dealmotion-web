'use client'

import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { Loader2, CheckCircle, XCircle } from 'lucide-react'
import { api } from '@/lib/api'

type CallbackStatus = 'loading' | 'success' | 'error'

export default function MicrosoftCalendarCallbackPage() {
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<CallbackStatus>('loading')
  const [message, setMessage] = useState('Processing authorization...')
  const [email, setEmail] = useState<string | null>(null)

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code')
      const state = searchParams.get('state')
      const error = searchParams.get('error')
      const errorDescription = searchParams.get('error_description')

      // Check for OAuth error
      if (error) {
        setStatus('error')
        setMessage(error === 'access_denied' 
          ? 'Authorization was cancelled' 
          : errorDescription || `Authorization failed: ${error}`)
        notifyOpener({ type: 'microsoft_calendar_error', error })
        return
      }

      // Validate required parameters
      if (!code || !state) {
        setStatus('error')
        setMessage('Missing authorization parameters')
        notifyOpener({ type: 'microsoft_calendar_error', error: 'Missing parameters' })
        return
      }

      // Verify state matches (optional security check)
      const storedState = sessionStorage.getItem('microsoft_calendar_state')
      if (storedState && state !== storedState) {
        setStatus('error')
        setMessage('Invalid state parameter')
        notifyOpener({ type: 'microsoft_calendar_error', error: 'State mismatch' })
        return
      }

      try {
        // Exchange code for tokens via backend
        const { data, error: apiError } = await api.post<{ 
          success: boolean
          email?: string
          provider: string 
        }>('/api/v1/calendar/callback/microsoft', { code, state })

        if (apiError || !data?.success) {
          throw new Error(apiError?.message || 'Failed to connect Microsoft Calendar')
        }

        setStatus('success')
        setEmail(data.email || null)
        setMessage('Microsoft 365 Calendar connected successfully!')
        
        // Clear stored state
        sessionStorage.removeItem('microsoft_calendar_state')
        
        // Notify opener window
        notifyOpener({ 
          type: 'microsoft_calendar_connected', 
          email: data.email 
        })

        // Close popup after short delay
        setTimeout(() => {
          window.close()
        }, 2000)

      } catch (err) {
        console.error('Microsoft Calendar callback error:', err)
        setStatus('error')
        setMessage(err instanceof Error ? err.message : 'Failed to connect calendar')
        notifyOpener({ 
          type: 'microsoft_calendar_error', 
          error: err instanceof Error ? err.message : 'Unknown error' 
        })
      }
    }

    handleCallback()
  }, [searchParams])

  const notifyOpener = (data: Record<string, unknown>) => {
    if (window.opener && !window.opener.closed) {
      window.opener.postMessage(data, window.location.origin)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900">
      <div className="text-center p-8 max-w-md">
        {status === 'loading' && (
          <>
            <Loader2 className="h-12 w-12 animate-spin text-blue-600 mx-auto mb-4" />
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
              Connecting Microsoft 365
            </h1>
            <p className="text-slate-500 dark:text-slate-400">{message}</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="h-10 w-10 text-green-600 dark:text-green-400" />
            </div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
              Connected!
            </h1>
            <p className="text-slate-500 dark:text-slate-400 mb-2">{message}</p>
            {email && (
              <p className="text-sm text-slate-400 dark:text-slate-500">
                Connected as {email}
              </p>
            )}
            <p className="text-sm text-slate-400 dark:text-slate-500 mt-4">
              This window will close automatically...
            </p>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mx-auto mb-4">
              <XCircle className="h-10 w-10 text-red-600 dark:text-red-400" />
            </div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
              Connection Failed
            </h1>
            <p className="text-slate-500 dark:text-slate-400 mb-4">{message}</p>
            <button
              onClick={() => window.close()}
              className="px-4 py-2 bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-300 dark:hover:bg-slate-600 transition-colors"
            >
              Close Window
            </button>
          </>
        )}
      </div>
    </div>
  )
}

