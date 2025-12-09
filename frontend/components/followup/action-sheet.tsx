'use client'

/**
 * ActionSheet - Renders ActionPanel in a side sheet (Portal)
 * 
 * This component wraps the ActionPanel in a Radix Sheet that renders
 * via Portal - completely outside the main React tree. This isolation
 * prevents blocking issues when navigating while actions are generating.
 * 
 * Uses URL search params (?action=customer_report) for state management,
 * making action views shareable and enabling proper back button behavior.
 */

import { useCallback, useEffect, useState } from 'react'
import { useRouter, useSearchParams, usePathname } from 'next/navigation'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { ActionPanel } from './action-panel'
import type { FollowupAction, ActionType } from '@/types/followup-actions'
import { getActionTypeInfo } from '@/types/followup-actions'

interface ActionSheetProps {
  /** All available actions for this followup */
  actions: FollowupAction[]
  /** Company name for exports */
  companyName: string
  /** Callback when action content is updated */
  onUpdate: (actionId: string, content: string) => Promise<void>
  /** Callback when action is deleted */
  onDelete: (actionId: string) => Promise<void>
  /** Callback when action should be regenerated */
  onRegenerate: (actionId: string) => void
  /** Currently generating action type (for UI feedback) */
  generatingType: ActionType | null
}

export function ActionSheet({
  actions,
  companyName,
  onUpdate,
  onDelete,
  onRegenerate,
  generatingType,
}: ActionSheetProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  
  // Get selected action from URL param
  const actionParam = searchParams.get('action')
  
  // Find the action to display
  const selectedAction = actionParam 
    ? actions.find(a => a.action_type === actionParam) 
    : null
  
  // Local state for tracking if sheet should be open
  // This allows smooth closing animation before URL update
  const [isOpen, setIsOpen] = useState(false)
  
  // Sync open state with URL param
  useEffect(() => {
    setIsOpen(!!actionParam && !!selectedAction)
  }, [actionParam, selectedAction])
  
  // Handle sheet close - update URL to remove action param
  const handleClose = useCallback(() => {
    // First trigger close animation
    setIsOpen(false)
    
    // Then update URL after animation completes
    setTimeout(() => {
      const params = new URLSearchParams(searchParams.toString())
      params.delete('action')
      const newUrl = params.toString() ? `${pathname}?${params}` : pathname
      router.push(newUrl, { scroll: false })
    }, 300) // Match sheet close animation duration
  }, [router, pathname, searchParams])
  
  // Handle open change from Radix (e.g., clicking overlay, pressing Escape)
  const handleOpenChange = useCallback((open: boolean) => {
    if (!open) {
      handleClose()
    }
  }, [handleClose])
  
  // Get action info for the title
  const actionInfo = selectedAction ? getActionTypeInfo(selectedAction.action_type) : null
  
  return (
    <Sheet open={isOpen} onOpenChange={handleOpenChange}>
      <SheetContent 
        side="right" 
        className="w-full sm:max-w-2xl lg:max-w-3xl p-0 overflow-hidden flex flex-col"
      >
        {selectedAction && actionInfo && (
          <>
            {/* Accessible title for screen readers */}
            <SheetHeader className="sr-only">
              <SheetTitle>{actionInfo.label}</SheetTitle>
              <SheetDescription>
                View and manage {actionInfo.label} for {companyName}
              </SheetDescription>
            </SheetHeader>
            
            {/* The actual ActionPanel - now in a Portal! */}
            <div className="flex-1 overflow-y-auto">
              <ActionPanel
                action={selectedAction}
                companyName={companyName}
                onUpdate={onUpdate}
                onDelete={async (actionId) => {
                  await onDelete(actionId)
                  handleClose()
                }}
                onRegenerate={onRegenerate}
                onClose={handleClose}
              />
            </div>
          </>
        )}
        
        {/* Loading state when action is generating */}
        {actionParam && !selectedAction && generatingType === actionParam && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-600 mx-auto mb-4" />
              <p className="text-slate-600 dark:text-slate-400">Generating...</p>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

/**
 * Hook to open an action in the sheet
 * Updates URL param to trigger sheet opening
 */
export function useActionSheet() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  
  const openAction = useCallback((actionType: ActionType | string) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set('action', actionType)
    router.push(`${pathname}?${params}`, { scroll: false })
  }, [router, pathname, searchParams])
  
  const closeAction = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString())
    params.delete('action')
    const newUrl = params.toString() ? `${pathname}?${params}` : pathname
    router.push(newUrl, { scroll: false })
  }, [router, pathname, searchParams])
  
  return { openAction, closeAction }
}

