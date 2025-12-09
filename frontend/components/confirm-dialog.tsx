'use client'

import { ReactNode, useState, createContext, useContext, useCallback } from 'react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'

// ===========================================
// Types
// ===========================================

type DialogVariant = 'default' | 'danger' | 'warning'

interface ConfirmDialogOptions {
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: DialogVariant
  icon?: keyof typeof Icons
  /** Called when confirmed */
  onConfirm?: () => void | Promise<void>
  /** Called when cancelled */
  onCancel?: () => void
}

interface DialogState extends ConfirmDialogOptions {
  isOpen: boolean
  isLoading: boolean
}

interface ConfirmDialogContextType {
  /** Open a confirmation dialog */
  confirm: (options: ConfirmDialogOptions) => Promise<boolean>
  /** Close the current dialog */
  close: () => void
}

// ===========================================
// Context
// ===========================================

const ConfirmDialogContext = createContext<ConfirmDialogContextType | null>(null)

/**
 * Hook to access the confirm dialog
 * 
 * @example
 * ```tsx
 * const { confirm } = useConfirmDialog()
 * 
 * const handleDelete = async () => {
 *   const confirmed = await confirm({
 *     title: 'Delete item?',
 *     description: 'This action cannot be undone.',
 *     variant: 'danger',
 *   })
 *   if (confirmed) {
 *     await deleteItem()
 *   }
 * }
 * ```
 */
export function useConfirmDialog() {
  const context = useContext(ConfirmDialogContext)
  if (!context) {
    throw new Error('useConfirmDialog must be used within a ConfirmDialogProvider')
  }
  return context
}

// ===========================================
// Provider
// ===========================================

interface ConfirmDialogProviderProps {
  children: ReactNode
}

/**
 * Provider for the confirm dialog system
 * 
 * Add this to your app layout to enable confirmation dialogs.
 */
export function ConfirmDialogProvider({ children }: ConfirmDialogProviderProps) {
  const [dialog, setDialog] = useState<DialogState>({
    isOpen: false,
    isLoading: false,
    title: '',
  })
  
  const [resolvePromise, setResolvePromise] = useState<((value: boolean) => void) | null>(null)

  const confirm = useCallback((options: ConfirmDialogOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      setResolvePromise(() => resolve)
      setDialog({
        ...options,
        isOpen: true,
        isLoading: false,
      })
    })
  }, [])

  const close = useCallback(() => {
    setDialog(prev => ({ ...prev, isOpen: false }))
    if (resolvePromise) {
      resolvePromise(false)
      setResolvePromise(null)
    }
  }, [resolvePromise])

  const handleConfirm = useCallback(async () => {
    setDialog(prev => ({ ...prev, isLoading: true }))
    
    try {
      if (dialog.onConfirm) {
        await dialog.onConfirm()
      }
      setDialog(prev => ({ ...prev, isOpen: false, isLoading: false }))
      if (resolvePromise) {
        resolvePromise(true)
        setResolvePromise(null)
      }
    } catch (error) {
      setDialog(prev => ({ ...prev, isLoading: false }))
      throw error
    }
  }, [dialog.onConfirm, resolvePromise])

  const handleCancel = useCallback(() => {
    dialog.onCancel?.()
    close()
  }, [dialog.onCancel, close])

  return (
    <ConfirmDialogContext.Provider value={{ confirm, close }}>
      {children}
      <ConfirmDialogModal
        {...dialog}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    </ConfirmDialogContext.Provider>
  )
}

// ===========================================
// Modal Component
// ===========================================

interface ConfirmDialogModalProps extends DialogState {
  onConfirm: () => void
  onCancel: () => void
}

function ConfirmDialogModal({
  isOpen,
  isLoading,
  title,
  description,
  confirmLabel,
  cancelLabel,
  variant = 'default',
  icon,
  onConfirm,
  onCancel,
}: ConfirmDialogModalProps) {
  const t = useTranslations('common')
  
  // Use translations as defaults if not provided
  const finalConfirmLabel = confirmLabel || t('confirm')
  const finalCancelLabel = cancelLabel || t('cancel')
  const processingLabel = t('processing')
  
  if (!isOpen) return null

  const variantConfig = {
    default: {
      icon: icon || 'helpCircle',
      iconBg: 'bg-blue-100 dark:bg-blue-900/30',
      iconColor: 'text-blue-600 dark:text-blue-400',
      buttonClass: 'bg-blue-600 hover:bg-blue-700',
    },
    danger: {
      icon: icon || 'alertTriangle',
      iconBg: 'bg-red-100 dark:bg-red-900/30',
      iconColor: 'text-red-600 dark:text-red-400',
      buttonClass: 'bg-red-600 hover:bg-red-700',
    },
    warning: {
      icon: icon || 'alertCircle',
      iconBg: 'bg-amber-100 dark:bg-amber-900/30',
      iconColor: 'text-amber-600 dark:text-amber-400',
      buttonClass: 'bg-amber-600 hover:bg-amber-700',
    },
  }

  const config = variantConfig[variant]
  const IconComponent = Icons[config.icon as keyof typeof Icons]

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 z-50 animate-in fade-in duration-200"
        onClick={onCancel}
      />
      
      {/* Dialog */}
      <div className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md animate-in zoom-in-95 fade-in duration-200">
        <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl border border-slate-200 dark:border-slate-800 p-6">
          {/* Icon */}
          <div className={cn(
            'mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-4',
            config.iconBg
          )}>
            <IconComponent className={cn('h-6 w-6', config.iconColor)} />
          </div>
          
          {/* Content */}
          <div className="text-center mb-6">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
              {title}
            </h2>
            {description && (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {description}
              </p>
            )}
          </div>
          
          {/* Actions */}
          <div className="flex gap-3">
            <Button
              variant="outline"
              className="flex-1"
              onClick={onCancel}
              disabled={isLoading}
            >
              {finalCancelLabel}
            </Button>
            <Button
              className={cn('flex-1', config.buttonClass)}
              onClick={onConfirm}
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Icons.spinner className="h-4 w-4 mr-2 animate-spin" />
                  {processingLabel}
                </>
              ) : (
                finalConfirmLabel
              )}
            </Button>
          </div>
        </div>
      </div>
    </>
  )
}

// ===========================================
// Standalone Component (for simpler use cases)
// ===========================================

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: DialogVariant
  icon?: keyof typeof Icons
  isLoading?: boolean
  onConfirm: () => void | Promise<void>
}

/**
 * Standalone confirm dialog component
 * 
 * @example
 * ```tsx
 * const [open, setOpen] = useState(false)
 * 
 * <ConfirmDialog
 *   open={open}
 *   onOpenChange={setOpen}
 *   title="Delete item?"
 *   description="This cannot be undone."
 *   variant="danger"
 *   onConfirm={handleDelete}
 * />
 * ```
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'default',
  icon,
  isLoading = false,
  onConfirm,
}: ConfirmDialogProps) {
  const [loading, setLoading] = useState(false)

  const handleConfirm = async () => {
    setLoading(true)
    try {
      await onConfirm()
      onOpenChange(false)
    } finally {
      setLoading(false)
    }
  }

  return (
    <ConfirmDialogModal
      isOpen={open}
      isLoading={isLoading || loading}
      title={title}
      description={description}
      confirmLabel={confirmLabel}
      cancelLabel={cancelLabel}
      variant={variant}
      icon={icon}
      onConfirm={handleConfirm}
      onCancel={() => onOpenChange(false)}
    />
  )
}

