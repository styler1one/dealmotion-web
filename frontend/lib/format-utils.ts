/**
 * Number and string formatting utilities
 * 
 * Locale-aware formatting functions for numbers, currency, percentages, and more.
 */

// ===========================================
// Number Formatting
// ===========================================

/**
 * Format a number with locale-aware separators
 */
export function formatNumber(
  value: number,
  locale: string = 'en',
  options?: Intl.NumberFormatOptions
): string {
  return new Intl.NumberFormat(locale, options).format(value)
}

/**
 * Format as compact number (e.g., 1.2K, 3.4M)
 */
export function formatCompact(
  value: number,
  locale: string = 'en'
): string {
  return new Intl.NumberFormat(locale, {
    notation: 'compact',
    compactDisplay: 'short',
    maximumFractionDigits: 1,
  }).format(value)
}

/**
 * Format as percentage
 */
export function formatPercent(
  value: number,
  locale: string = 'en',
  decimals: number = 0
): string {
  return new Intl.NumberFormat(locale, {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

/**
 * Format bytes to human readable size
 */
export function formatBytes(
  bytes: number,
  decimals: number = 1
): string {
  if (bytes === 0) return '0 B'
  
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`
}

/**
 * Format number with ordinal suffix (1st, 2nd, 3rd, etc.)
 */
export function formatOrdinal(n: number, locale: string = 'en'): string {
  // For English
  if (locale.startsWith('en')) {
    const s = ['th', 'st', 'nd', 'rd']
    const v = n % 100
    return n + (s[(v - 20) % 10] || s[v] || s[0])
  }
  
  // For other locales, just return the number
  return n.toString()
}

// ===========================================
// Currency Formatting
// ===========================================

/**
 * Format as currency
 */
export function formatCurrency(
  value: number,
  currency: string = 'EUR',
  locale: string = 'en'
): string {
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value)
}

/**
 * Format cents to currency (e.g., 1999 cents -> €19.99)
 */
export function formatCentsAsCurrency(
  cents: number,
  currency: string = 'EUR',
  locale: string = 'en'
): string {
  return formatCurrency(cents / 100, currency, locale)
}

/**
 * Format price with interval (e.g., €9.99/month)
 */
export function formatPriceWithInterval(
  amount: number,
  currency: string = 'EUR',
  interval: 'month' | 'year',
  locale: string = 'en'
): string {
  const price = formatCurrency(amount, currency, locale)
  const intervalStr = interval === 'month' ? '/mo' : '/yr'
  return `${price}${intervalStr}`
}

// ===========================================
// String Formatting
// ===========================================

/**
 * Truncate string with ellipsis
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str
  return str.slice(0, maxLength - 3) + '...'
}

/**
 * Truncate in the middle (e.g., for file names)
 */
export function truncateMiddle(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str
  
  const charsToShow = maxLength - 3
  const frontChars = Math.ceil(charsToShow / 2)
  const backChars = Math.floor(charsToShow / 2)
  
  return str.slice(0, frontChars) + '...' + str.slice(-backChars)
}

/**
 * Capitalize first letter
 */
export function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1)
}

/**
 * Convert to title case
 */
export function toTitleCase(str: string): string {
  return str.replace(
    /\w\S*/g,
    (txt) => txt.charAt(0).toUpperCase() + txt.slice(1).toLowerCase()
  )
}

/**
 * Convert camelCase or PascalCase to space-separated words
 */
export function camelToWords(str: string): string {
  return str
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (s) => s.toUpperCase())
    .trim()
}

/**
 * Convert snake_case to space-separated words
 */
export function snakeToWords(str: string): string {
  return str
    .split('_')
    .map(capitalize)
    .join(' ')
}

/**
 * Slugify a string (URL-safe)
 */
export function slugify(str: string): string {
  return str
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

/**
 * Generate initials from name
 */
export function getInitials(name: string, maxLength: number = 2): string {
  return name
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase())
    .slice(0, maxLength)
    .join('')
}

// ===========================================
// Pluralization
// ===========================================

/**
 * Simple pluralization helper
 */
export function pluralize(
  count: number,
  singular: string,
  plural?: string
): string {
  const pluralForm = plural || singular + 's'
  return count === 1 ? singular : pluralForm
}

/**
 * Format count with word (e.g., "5 items", "1 item")
 */
export function formatCount(
  count: number,
  singular: string,
  plural?: string
): string {
  return `${count} ${pluralize(count, singular, plural)}`
}

// ===========================================
// Phone & Email Formatting
// ===========================================

/**
 * Format phone number (basic formatting)
 */
export function formatPhone(phone: string): string {
  // Remove all non-digits
  const digits = phone.replace(/\D/g, '')
  
  // Format based on length
  if (digits.length === 10) {
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`
  }
  if (digits.length === 11 && digits.startsWith('1')) {
    return `+1 (${digits.slice(1, 4)}) ${digits.slice(4, 7)}-${digits.slice(7)}`
  }
  
  // Return original if can't format
  return phone
}

/**
 * Mask email address for privacy
 */
export function maskEmail(email: string): string {
  const [local, domain] = email.split('@')
  if (!domain) return email
  
  const maskedLocal = local.length > 2
    ? local.charAt(0) + '*'.repeat(Math.min(local.length - 2, 5)) + local.charAt(local.length - 1)
    : local
    
  return `${maskedLocal}@${domain}`
}

// ===========================================
// List Formatting
// ===========================================

/**
 * Join array with proper grammar (e.g., "A, B, and C")
 */
export function formatList(
  items: string[],
  locale: string = 'en',
  type: 'conjunction' | 'disjunction' = 'conjunction'
): string {
  return new Intl.ListFormat(locale, {
    style: 'long',
    type,
  }).format(items)
}

/**
 * Format array with limit (e.g., "A, B, and 3 more")
 */
export function formatListWithLimit(
  items: string[],
  limit: number = 3,
  moreText: string = 'more'
): string {
  if (items.length <= limit) {
    return formatList(items)
  }
  
  const shown = items.slice(0, limit)
  const remaining = items.length - limit
  
  return `${shown.join(', ')}, and ${remaining} ${moreText}`
}

