/**
 * Error handling utilities
 * 
 * Provides consistent error handling across the application.
 */

import { logger } from './logger'

/**
 * Extract a user-friendly message from an unknown error
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message
  }
  if (typeof error === 'string') {
    return error
  }
  if (error && typeof error === 'object' && 'message' in error) {
    return String((error as { message: unknown }).message)
  }
  return 'An unexpected error occurred'
}

/**
 * Check if error is an API error with a specific code
 */
export function isApiError(error: unknown, code?: string): boolean {
  if (!error || typeof error !== 'object') return false
  const apiError = error as { code?: string }
  if (code) {
    return apiError.code === code
  }
  return 'code' in apiError
}

/**
 * Check if error is a network error
 */
export function isNetworkError(error: unknown): boolean {
  if (error instanceof Error) {
    return error.message.includes('network') || 
           error.message.includes('fetch') ||
           error.message.includes('Failed to fetch')
  }
  return false
}

/**
 * Handle an error with logging and optional callback
 */
export function handleError(
  error: unknown,
  options: {
    context?: string
    fallbackMessage?: string
    onError?: (message: string) => void
    silent?: boolean
  } = {}
): string {
  const { context, fallbackMessage, onError, silent = false } = options
  const message = getErrorMessage(error) || fallbackMessage || 'An error occurred'
  
  if (!silent) {
    logger.error(context || 'Error', error, { context })
  }
  
  if (onError) {
    onError(message)
  }
  
  return message
}

/**
 * Wrap an async function with error handling
 */
export function withErrorHandling<T extends (...args: unknown[]) => Promise<unknown>>(
  fn: T,
  options: {
    context?: string
    fallbackMessage?: string
    onError?: (message: string) => void
  } = {}
): T {
  return (async (...args: Parameters<T>) => {
    try {
      return await fn(...args)
    } catch (error) {
      handleError(error, options)
      return null
    }
  }) as T
}

