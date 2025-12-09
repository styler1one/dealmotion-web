/**
 * Date and time formatting utilities
 * 
 * Locale-aware date formatting functions for consistent date display.
 */

// ===========================================
// Relative Time
// ===========================================

/**
 * Get relative time string (e.g., "2 hours ago", "yesterday")
 */
export function getRelativeTime(date: Date | string, locale: string = 'en'): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date
  const now = new Date()
  const diffInSeconds = Math.floor((now.getTime() - dateObj.getTime()) / 1000)
  
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })
  
  // Less than a minute
  if (diffInSeconds < 60) {
    return rtf.format(0, 'second')
  }
  
  // Less than an hour
  if (diffInSeconds < 3600) {
    return rtf.format(-Math.floor(diffInSeconds / 60), 'minute')
  }
  
  // Less than a day
  if (diffInSeconds < 86400) {
    return rtf.format(-Math.floor(diffInSeconds / 3600), 'hour')
  }
  
  // Less than a week
  if (diffInSeconds < 604800) {
    return rtf.format(-Math.floor(diffInSeconds / 86400), 'day')
  }
  
  // Less than a month
  if (diffInSeconds < 2592000) {
    return rtf.format(-Math.floor(diffInSeconds / 604800), 'week')
  }
  
  // Less than a year
  if (diffInSeconds < 31536000) {
    return rtf.format(-Math.floor(diffInSeconds / 2592000), 'month')
  }
  
  // More than a year
  return rtf.format(-Math.floor(diffInSeconds / 31536000), 'year')
}

/**
 * Get short relative time (e.g., "2h", "3d", "1w")
 */
export function getShortRelativeTime(date: Date | string): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date
  const now = new Date()
  const diffInSeconds = Math.floor((now.getTime() - dateObj.getTime()) / 1000)
  
  if (diffInSeconds < 60) return 'now'
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m`
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h`
  if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}d`
  if (diffInSeconds < 2592000) return `${Math.floor(diffInSeconds / 604800)}w`
  if (diffInSeconds < 31536000) return `${Math.floor(diffInSeconds / 2592000)}mo`
  return `${Math.floor(diffInSeconds / 31536000)}y`
}

// ===========================================
// Date Formatting
// ===========================================

type DateFormatStyle = 'short' | 'medium' | 'long' | 'full'

/**
 * Format date according to locale
 */
export function formatDate(
  date: Date | string,
  locale: string = 'en',
  style: DateFormatStyle = 'medium'
): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date
  
  const styleOptions: Record<DateFormatStyle, Intl.DateTimeFormatOptions> = {
    short: { month: 'numeric', day: 'numeric', year: '2-digit' },
    medium: { month: 'short', day: 'numeric', year: 'numeric' },
    long: { month: 'long', day: 'numeric', year: 'numeric' },
    full: { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' },
  }
  
  return new Intl.DateTimeFormat(locale, styleOptions[style]).format(dateObj)
}

/**
 * Format time according to locale
 */
export function formatTime(
  date: Date | string,
  locale: string = 'en',
  includeSeconds: boolean = false
): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date
  
  const options: Intl.DateTimeFormatOptions = {
    hour: 'numeric',
    minute: '2-digit',
    ...(includeSeconds && { second: '2-digit' }),
  }
  
  return new Intl.DateTimeFormat(locale, options).format(dateObj)
}

/**
 * Format date and time together
 */
export function formatDateTime(
  date: Date | string,
  locale: string = 'en',
  dateStyle: DateFormatStyle = 'medium'
): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date
  return `${formatDate(dateObj, locale, dateStyle)} ${formatTime(dateObj, locale)}`
}

// ===========================================
// Date Ranges
// ===========================================

/**
 * Format date range (e.g., "Jan 1 - Jan 15, 2024")
 */
export function formatDateRange(
  start: Date | string,
  end: Date | string,
  locale: string = 'en'
): string {
  const startDate = typeof start === 'string' ? new Date(start) : start
  const endDate = typeof end === 'string' ? new Date(end) : end
  
  const sameYear = startDate.getFullYear() === endDate.getFullYear()
  const sameMonth = sameYear && startDate.getMonth() === endDate.getMonth()
  
  if (sameMonth) {
    // Same month: "Jan 1 - 15, 2024"
    const month = new Intl.DateTimeFormat(locale, { month: 'short' }).format(startDate)
    const year = startDate.getFullYear()
    return `${month} ${startDate.getDate()} - ${endDate.getDate()}, ${year}`
  }
  
  if (sameYear) {
    // Same year: "Jan 1 - Feb 15, 2024"
    const startStr = new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric' }).format(startDate)
    const endStr = new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric' }).format(endDate)
    return `${startStr} - ${endStr}, ${startDate.getFullYear()}`
  }
  
  // Different years: "Jan 1, 2023 - Feb 15, 2024"
  return `${formatDate(startDate, locale, 'medium')} - ${formatDate(endDate, locale, 'medium')}`
}

// ===========================================
// Duration Formatting
// ===========================================

/**
 * Format duration in seconds to human readable format
 */
export function formatDuration(seconds: number, locale: string = 'en'): string {
  if (seconds < 60) {
    return `${seconds}s`
  }
  
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  
  if (minutes < 60) {
    return remainingSeconds > 0
      ? `${minutes}m ${remainingSeconds}s`
      : `${minutes}m`
  }
  
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  
  if (hours < 24) {
    return remainingMinutes > 0
      ? `${hours}h ${remainingMinutes}m`
      : `${hours}h`
  }
  
  const days = Math.floor(hours / 24)
  const remainingHours = hours % 24
  
  return remainingHours > 0
    ? `${days}d ${remainingHours}h`
    : `${days}d`
}

/**
 * Format minutes to hours and minutes (e.g., "2h 30m")
 */
export function formatMinutes(minutes: number): string {
  if (minutes < 60) {
    return `${minutes}m`
  }
  
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  
  return remainingMinutes > 0
    ? `${hours}h ${remainingMinutes}m`
    : `${hours}h`
}

// ===========================================
// Date Helpers
// ===========================================

/**
 * Check if date is today
 */
export function isToday(date: Date | string): boolean {
  const dateObj = typeof date === 'string' ? new Date(date) : date
  const today = new Date()
  return (
    dateObj.getDate() === today.getDate() &&
    dateObj.getMonth() === today.getMonth() &&
    dateObj.getFullYear() === today.getFullYear()
  )
}

/**
 * Check if date is yesterday
 */
export function isYesterday(date: Date | string): boolean {
  const dateObj = typeof date === 'string' ? new Date(date) : date
  const yesterday = new Date()
  yesterday.setDate(yesterday.getDate() - 1)
  return (
    dateObj.getDate() === yesterday.getDate() &&
    dateObj.getMonth() === yesterday.getMonth() &&
    dateObj.getFullYear() === yesterday.getFullYear()
  )
}

/**
 * Check if date is within the last N days
 */
export function isWithinDays(date: Date | string, days: number): boolean {
  const dateObj = typeof date === 'string' ? new Date(date) : date
  const threshold = new Date()
  threshold.setDate(threshold.getDate() - days)
  return dateObj >= threshold
}

/**
 * Get start of day (midnight)
 */
export function startOfDay(date: Date | string): Date {
  const dateObj = typeof date === 'string' ? new Date(date) : new Date(date)
  dateObj.setHours(0, 0, 0, 0)
  return dateObj
}

/**
 * Get end of day (23:59:59.999)
 */
export function endOfDay(date: Date | string): Date {
  const dateObj = typeof date === 'string' ? new Date(date) : new Date(date)
  dateObj.setHours(23, 59, 59, 999)
  return dateObj
}

/**
 * Get start of month
 */
export function startOfMonth(date: Date | string): Date {
  const dateObj = typeof date === 'string' ? new Date(date) : new Date(date)
  dateObj.setDate(1)
  dateObj.setHours(0, 0, 0, 0)
  return dateObj
}

/**
 * Get end of month
 */
export function endOfMonth(date: Date | string): Date {
  const dateObj = typeof date === 'string' ? new Date(date) : new Date(date)
  dateObj.setMonth(dateObj.getMonth() + 1, 0)
  dateObj.setHours(23, 59, 59, 999)
  return dateObj
}

/**
 * Add days to a date
 */
export function addDays(date: Date | string, days: number): Date {
  const dateObj = typeof date === 'string' ? new Date(date) : new Date(date)
  dateObj.setDate(dateObj.getDate() + days)
  return dateObj
}

/**
 * Subtract days from a date
 */
export function subtractDays(date: Date | string, days: number): Date {
  return addDays(date, -days)
}

// ===========================================
// Smart Date Display
// ===========================================

/**
 * Smart date display that shows relative time for recent dates
 * and absolute date for older dates
 */
export function smartDate(
  date: Date | string,
  locale: string = 'en',
  options?: {
    /** Show relative time for dates within this many days (default: 7) */
    relativeDays?: number
    /** Include time for today/yesterday */
    includeTime?: boolean
  }
): string {
  const { relativeDays = 7, includeTime = true } = options || {}
  const dateObj = typeof date === 'string' ? new Date(date) : date
  
  if (isToday(dateObj)) {
    return includeTime
      ? `Today at ${formatTime(dateObj, locale)}`
      : 'Today'
  }
  
  if (isYesterday(dateObj)) {
    return includeTime
      ? `Yesterday at ${formatTime(dateObj, locale)}`
      : 'Yesterday'
  }
  
  if (isWithinDays(dateObj, relativeDays)) {
    return getRelativeTime(dateObj, locale)
  }
  
  return formatDate(dateObj, locale, 'medium')
}

