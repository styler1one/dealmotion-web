/**
 * Clipboard utilities
 * 
 * Functions for copying content to clipboard with feedback.
 */

// ===========================================
// Types
// ===========================================

interface CopyOptions {
  /** Success message for toast */
  successMessage?: string
  /** Error message for toast */
  errorMessage?: string
  /** Show toast notification */
  showToast?: boolean
  /** Toast function (if not using global) */
  toast?: (options: { title: string; description?: string; variant?: 'default' | 'destructive' }) => void
}

interface CopyResult {
  success: boolean
  error?: Error
}

// ===========================================
// Core Copy Function
// ===========================================

/**
 * Copy text to clipboard
 * 
 * Uses modern Clipboard API with fallback for older browsers.
 */
export async function copyToClipboard(text: string): Promise<CopyResult> {
  try {
    // Modern Clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text)
      return { success: true }
    }

    // Fallback for older browsers
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    textarea.style.top = '-9999px'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()

    const successful = document.execCommand('copy')
    document.body.removeChild(textarea)

    if (!successful) {
      throw new Error('execCommand copy failed')
    }

    return { success: true }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error : new Error('Copy failed'),
    }
  }
}

/**
 * Copy text with toast feedback
 * 
 * @example
 * ```tsx
 * import { useToast } from '@/components/ui/use-toast'
 * 
 * const { toast } = useToast()
 * 
 * const handleCopy = () => {
 *   copyWithToast(text, { toast, successMessage: 'Email copied!' })
 * }
 * ```
 */
export async function copyWithToast(
  text: string,
  options: CopyOptions = {}
): Promise<boolean> {
  const {
    successMessage = 'Copied to clipboard',
    errorMessage = 'Failed to copy',
    showToast = true,
    toast,
  } = options

  const result = await copyToClipboard(text)

  if (showToast && toast) {
    if (result.success) {
      toast({
        title: successMessage,
      })
    } else {
      toast({
        title: errorMessage,
        description: result.error?.message,
        variant: 'destructive',
      })
    }
  }

  return result.success
}

// ===========================================
// Specialized Copy Functions
// ===========================================

/**
 * Copy rich text (HTML) to clipboard
 * 
 * Copies both HTML and plain text versions for compatibility.
 */
export async function copyRichText(html: string, plainText?: string): Promise<CopyResult> {
  try {
    const text = plainText || html.replace(/<[^>]*>/g, '')

    if (navigator.clipboard && typeof ClipboardItem !== 'undefined') {
      const htmlBlob = new Blob([html], { type: 'text/html' })
      const textBlob = new Blob([text], { type: 'text/plain' })
      
      const clipboardItem = new ClipboardItem({
        'text/html': htmlBlob,
        'text/plain': textBlob,
      })
      
      await navigator.clipboard.write([clipboardItem])
      return { success: true }
    }

    // Fallback to plain text
    return copyToClipboard(text)
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error : new Error('Copy failed'),
    }
  }
}

/**
 * Copy URL with optional formatting
 */
export async function copyUrl(
  url?: string,
  options?: CopyOptions
): Promise<boolean> {
  const urlToCopy = url || (typeof window !== 'undefined' ? window.location.href : '')
  return copyWithToast(urlToCopy, {
    successMessage: 'Link copied!',
    ...options,
  })
}

/**
 * Copy email address
 */
export async function copyEmail(
  email: string,
  options?: CopyOptions
): Promise<boolean> {
  return copyWithToast(email, {
    successMessage: 'Email copied!',
    ...options,
  })
}

/**
 * Copy formatted code
 */
export async function copyCode(
  code: string,
  options?: CopyOptions
): Promise<boolean> {
  return copyWithToast(code, {
    successMessage: 'Code copied!',
    ...options,
  })
}

// ===========================================
// React Hook
// ===========================================

import { useState, useCallback } from 'react'

interface UseCopyOptions extends CopyOptions {
  /** Reset copied state after this many ms (default: 2000) */
  resetDelay?: number
}

/**
 * React hook for copy to clipboard functionality
 * 
 * @example
 * ```tsx
 * const { copy, copied, copying } = useCopy()
 * 
 * <Button onClick={() => copy(text)}>
 *   {copied ? 'Copied!' : 'Copy'}
 * </Button>
 * ```
 */
export function useCopy(options: UseCopyOptions = {}) {
  const { resetDelay = 2000, ...copyOptions } = options
  
  const [copied, setCopied] = useState(false)
  const [copying, setCopying] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const copy = useCallback(async (text: string) => {
    setCopying(true)
    setError(null)

    const result = await copyToClipboard(text)

    setCopying(false)

    if (result.success) {
      setCopied(true)
      
      // Show toast if configured
      if (copyOptions.showToast && copyOptions.toast) {
        copyOptions.toast({
          title: copyOptions.successMessage || 'Copied to clipboard',
        })
      }

      // Reset after delay
      setTimeout(() => {
        setCopied(false)
      }, resetDelay)
    } else {
      setError(result.error || new Error('Copy failed'))
      
      if (copyOptions.showToast && copyOptions.toast) {
        copyOptions.toast({
          title: copyOptions.errorMessage || 'Failed to copy',
          variant: 'destructive',
        })
      }
    }

    return result.success
  }, [copyOptions, resetDelay])

  const reset = useCallback(() => {
    setCopied(false)
    setError(null)
  }, [])

  return {
    copy,
    copied,
    copying,
    error,
    reset,
  }
}

// ===========================================
// Copy Button Component Helper
// ===========================================

/**
 * Get copy button state props
 * 
 * @example
 * ```tsx
 * const copyState = useCopy()
 * const buttonProps = getCopyButtonProps(copyState)
 * 
 * <Button {...buttonProps.button} onClick={() => copyState.copy(text)}>
 *   <buttonProps.Icon className="h-4 w-4 mr-2" />
 *   {buttonProps.label}
 * </Button>
 * ```
 */
export function getCopyButtonProps(state: ReturnType<typeof useCopy>) {
  const { copied, copying, error } = state
  
  return {
    label: copying ? 'Copying...' : copied ? 'Copied!' : 'Copy',
    icon: copied ? 'check' : 'copy',
    disabled: copying,
    button: {
      disabled: copying,
      'aria-label': copied ? 'Copied to clipboard' : 'Copy to clipboard',
    },
  }
}

