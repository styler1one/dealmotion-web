'use client'

import { useState, createContext, useContext, useCallback, ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { AlertTriangle, Coins, CreditCard, X, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

// Credit action info for display
const ACTION_INFO: Record<string, { name: string; credits: number; icon: string }> = {
  research_flow: { name: 'Research', credits: 3, icon: '🔍' },
  prospect_discovery: { name: 'Prospect Discovery', credits: 5, icon: '🎯' },
  preparation: { name: 'Meeting Prep', credits: 2, icon: '📋' },
  followup: { name: 'Follow-up Summary', credits: 2, icon: '📝' },
  followup_start: { name: 'Follow-up (Audio)', credits: 3, icon: '🎙️' },
  followup_action: { name: 'Follow-up Action', credits: 2, icon: '✨' },
  transcription_minute: { name: 'Transcriptie (per min)', credits: 0.15, icon: '🎤' },
}

interface InsufficientCreditsModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  action?: string
  requiredCredits?: number
  availableCredits?: number
}

export function InsufficientCreditsModal({
  open,
  onOpenChange,
  action,
  requiredCredits,
  availableCredits = 0,
}: InsufficientCreditsModalProps) {
  const router = useRouter()
  const actionInfo = action ? ACTION_INFO[action] : null
  const displayCredits = requiredCredits || actionInfo?.credits || 0

  const handleUpgrade = () => {
    onOpenChange(false)
    router.push('/pricing')
  }

  const handleManageSubscription = () => {
    onOpenChange(false)
    router.push('/dashboard/settings')
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
            <AlertTriangle className="h-6 w-6 text-red-600 dark:text-red-400" />
          </div>
          <DialogTitle className="text-xl text-center">
            Onvoldoende Credits
          </DialogTitle>
          <DialogDescription className="text-center">
            Je hebt niet genoeg credits voor deze actie
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Action Info */}
          {actionInfo && (
            <div className="flex items-center justify-between p-4 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{actionInfo.icon}</span>
                <div>
                  <p className="font-medium text-slate-900 dark:text-white">
                    {actionInfo.name}
                  </p>
                  <p className="text-sm text-slate-500">
                    Vereist {displayCredits} credits
                  </p>
                </div>
              </div>
              <div className="text-right">
                <div className="flex items-center gap-1 text-red-600 dark:text-red-400">
                  <Coins className="h-4 w-4" />
                  <span className="font-semibold">{displayCredits}</span>
                </div>
              </div>
            </div>
          )}

          {/* Balance Info */}
          <div className="flex items-center justify-between p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
            <span className="text-sm text-amber-700 dark:text-amber-300">
              Jouw beschikbare credits:
            </span>
            <span className="font-semibold text-amber-700 dark:text-amber-300">
              {availableCredits.toFixed(1)}
            </span>
          </div>

          {/* Shortage */}
          <div className="text-center text-sm text-slate-500">
            Tekort: <span className="font-semibold text-red-600">{(displayCredits - availableCredits).toFixed(1)}</span> credits
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-2">
          <Button
            onClick={handleUpgrade}
            className="w-full gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
          >
            <Sparkles className="h-4 w-4" />
            Upgrade of Koop Credits
          </Button>
          <Button
            variant="outline"
            onClick={handleManageSubscription}
            className="w-full gap-2"
          >
            <CreditCard className="h-4 w-4" />
            Beheer Abonnement
          </Button>
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            className="w-full"
          >
            Later
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// =============================================================================
// Context Provider for global usage
// =============================================================================

interface InsufficientCreditsState {
  showModal: boolean
  action?: string
  requiredCredits?: number
  availableCredits?: number
}

interface InsufficientCreditsContextType {
  showInsufficientCredits: (options: {
    action?: string
    requiredCredits?: number
    availableCredits?: number
  }) => void
  hideInsufficientCredits: () => void
}

const InsufficientCreditsContext = createContext<InsufficientCreditsContextType | null>(null)

export function InsufficientCreditsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<InsufficientCreditsState>({ showModal: false })

  const showInsufficientCredits = useCallback((options: {
    action?: string
    requiredCredits?: number
    availableCredits?: number
  }) => {
    setState({
      showModal: true,
      ...options,
    })
  }, [])

  const hideInsufficientCredits = useCallback(() => {
    setState({ showModal: false })
  }, [])

  return (
    <InsufficientCreditsContext.Provider value={{ showInsufficientCredits, hideInsufficientCredits }}>
      {children}
      <InsufficientCreditsModal
        open={state.showModal}
        onOpenChange={(open) => !open && hideInsufficientCredits()}
        action={state.action}
        requiredCredits={state.requiredCredits}
        availableCredits={state.availableCredits}
      />
    </InsufficientCreditsContext.Provider>
  )
}

export function useInsufficientCredits() {
  const context = useContext(InsufficientCreditsContext)
  if (!context) {
    throw new Error('useInsufficientCredits must be used within InsufficientCreditsProvider')
  }
  return context
}

