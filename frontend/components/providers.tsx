'use client'

import { ReactNode, Suspense } from 'react'
import { ThemeProvider } from '@/components/theme-provider'
import { SettingsProvider } from '@/lib/settings-context'
import { BillingProvider } from '@/lib/billing-context'
import { ErrorBoundary } from '@/components/error-boundary'
import { ConfirmDialogProvider } from '@/components/confirm-dialog'
import { InsufficientCreditsProvider } from '@/components/insufficient-credits-modal'
import { Toaster } from '@/components/ui/toaster'
import { PostHogProvider } from '@/lib/posthog'
import { AffiliateTracker } from '@/components/affiliate-tracker'
import { LunaProvider, LunaWidget } from '@/components/luna'

interface ProvidersProps {
  children: ReactNode
}

/**
 * Client-side providers wrapper
 * 
 * Combines all client-side providers and context in a single component
 * to keep the layout file clean and simplify provider management.
 * 
 * Provider order (outer to inner):
 * 1. PostHogProvider - Analytics (wrapped in Suspense for useSearchParams)
 * 2. ThemeProvider - Theme management
 * 3. ErrorBoundary - Error catching
 * 4. SettingsProvider - User settings
 * 5. BillingProvider - Subscription/billing
 * 6. LunaProvider - Luna AI Assistant (SPEC-046)
 * 7. ConfirmDialogProvider - Confirmation dialogs
 */
export function Providers({ children }: ProvidersProps) {
  return (
    <Suspense fallback={null}>
      <PostHogProvider>
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem
          disableTransitionOnChange
        >
          <ErrorBoundary>
            <SettingsProvider>
              <BillingProvider>
                <LunaProvider>
                  <ConfirmDialogProvider>
                    <InsufficientCreditsProvider>
                      <AffiliateTracker />
                      {children}
                      <LunaWidget />
                      <Toaster />
                    </InsufficientCreditsProvider>
                  </ConfirmDialogProvider>
                </LunaProvider>
              </BillingProvider>
            </SettingsProvider>
          </ErrorBoundary>
        </ThemeProvider>
      </PostHogProvider>
    </Suspense>
  )
}

