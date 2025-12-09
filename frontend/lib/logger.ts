/**
 * Centralized logging utility
 * 
 * Provides consistent logging across the application with:
 * - Development: Console output
 * - Production: Silent (logs sent to Sentry via error-boundary)
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error'

interface LogContext {
  /** Component or function name */
  source?: string
  /** User ID for context */
  userId?: string
  /** Additional metadata */
  [key: string]: unknown
}

const isDev = process.env.NODE_ENV === 'development'

/**
 * Format log message with optional context
 */
function formatMessage(message: string, context?: LogContext): string {
  if (!context?.source) return message
  return `[${context.source}] ${message}`
}

/**
 * Logger utility - only outputs in development
 */
export const logger = {
  debug: (message: string, context?: LogContext) => {
    if (isDev) {
      console.debug(formatMessage(message, context), context)
    }
  },

  info: (message: string, context?: LogContext) => {
    if (isDev) {
      console.info(formatMessage(message, context), context)
    }
  },

  warn: (message: string, context?: LogContext) => {
    if (isDev) {
      console.warn(formatMessage(message, context), context)
    }
  },

  error: (message: string, error?: unknown, context?: LogContext) => {
    if (isDev) {
      console.error(formatMessage(message, context), error, context)
    }
    // In production, errors are captured by ErrorBoundary/Sentry
  },
}

export default logger

