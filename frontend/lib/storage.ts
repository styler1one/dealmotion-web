/**
 * Type-safe localStorage utilities
 * 
 * Provides a type-safe wrapper around localStorage with JSON serialization,
 * expiration support, and SSR-safe operations.
 */

// ===========================================
// Types
// ===========================================

interface StorageItem<T> {
  value: T
  expiresAt?: number
}

interface StorageOptions {
  /** Time to live in milliseconds */
  ttl?: number
}

// ===========================================
// Core Storage Functions
// ===========================================

/**
 * Check if we're in a browser environment
 */
function isBrowser(): boolean {
  return typeof window !== 'undefined'
}

/**
 * Get item from localStorage with type safety
 * 
 * @example
 * ```ts
 * const user = getStorageItem<User>('user')
 * const settings = getStorageItem<Settings>('settings', { theme: 'light' })
 * ```
 */
export function getStorageItem<T>(key: string, defaultValue?: T): T | undefined {
  if (!isBrowser()) {
    return defaultValue
  }

  try {
    const item = localStorage.getItem(key)
    
    if (!item) {
      return defaultValue
    }

    const parsed: StorageItem<T> = JSON.parse(item)
    
    // Check expiration
    if (parsed.expiresAt && Date.now() > parsed.expiresAt) {
      localStorage.removeItem(key)
      return defaultValue
    }

    return parsed.value
  } catch {
    // If parsing fails, try to return raw value or default
    return defaultValue
  }
}

/**
 * Set item in localStorage with type safety
 * 
 * @example
 * ```ts
 * setStorageItem('user', { name: 'John' })
 * setStorageItem('cache', data, { ttl: 60000 }) // Expires in 1 minute
 * ```
 */
export function setStorageItem<T>(
  key: string,
  value: T,
  options?: StorageOptions
): boolean {
  if (!isBrowser()) {
    return false
  }

  try {
    const item: StorageItem<T> = {
      value,
      ...(options?.ttl && { expiresAt: Date.now() + options.ttl }),
    }
    
    localStorage.setItem(key, JSON.stringify(item))
    return true
  } catch {
    // Handle quota exceeded or other errors
    return false
  }
}

/**
 * Remove item from localStorage
 */
export function removeStorageItem(key: string): boolean {
  if (!isBrowser()) {
    return false
  }

  try {
    localStorage.removeItem(key)
    return true
  } catch {
    return false
  }
}

/**
 * Clear all items from localStorage
 */
export function clearStorage(): boolean {
  if (!isBrowser()) {
    return false
  }

  try {
    localStorage.clear()
    return true
  } catch {
    return false
  }
}

/**
 * Check if key exists in localStorage
 */
export function hasStorageItem(key: string): boolean {
  if (!isBrowser()) {
    return false
  }

  return localStorage.getItem(key) !== null
}

/**
 * Get all keys in localStorage
 */
export function getStorageKeys(): string[] {
  if (!isBrowser()) {
    return []
  }

  return Object.keys(localStorage)
}

// ===========================================
// Session Storage (same API)
// ===========================================

/**
 * Get item from sessionStorage with type safety
 */
export function getSessionItem<T>(key: string, defaultValue?: T): T | undefined {
  if (!isBrowser()) {
    return defaultValue
  }

  try {
    const item = sessionStorage.getItem(key)
    
    if (!item) {
      return defaultValue
    }

    return JSON.parse(item)
  } catch {
    return defaultValue
  }
}

/**
 * Set item in sessionStorage with type safety
 */
export function setSessionItem<T>(key: string, value: T): boolean {
  if (!isBrowser()) {
    return false
  }

  try {
    sessionStorage.setItem(key, JSON.stringify(value))
    return true
  } catch {
    return false
  }
}

/**
 * Remove item from sessionStorage
 */
export function removeSessionItem(key: string): boolean {
  if (!isBrowser()) {
    return false
  }

  try {
    sessionStorage.removeItem(key)
    return true
  } catch {
    return false
  }
}

// ===========================================
// Typed Storage Keys
// ===========================================

/**
 * Pre-defined storage keys for the application
 * 
 * Using this ensures consistent key names and type safety.
 */
export const StorageKeys = {
  // User preferences
  THEME: 'theme',
  LOCALE: 'locale',
  SIDEBAR_COLLAPSED: 'sidebar_collapsed',
  
  // Form drafts (auto-saved)
  RESEARCH_DRAFT: 'research_draft',
  PREPARATION_DRAFT: 'preparation_draft',
  
  // Cache
  COMPANY_SEARCH_CACHE: 'company_search_cache',
  USER_SETTINGS_CACHE: 'user_settings_cache',
  
  // Session
  LAST_VISITED_PAGE: 'last_visited_page',
  ONBOARDING_STEP: 'onboarding_step',
} as const

// ===========================================
// Helper Functions
// ===========================================

/**
 * Save form draft to localStorage
 * 
 * @example
 * ```ts
 * // Auto-save form data
 * useEffect(() => {
 *   saveDraft('research', formData)
 * }, [formData])
 * 
 * // Restore on mount
 * useEffect(() => {
 *   const draft = getDraft('research')
 *   if (draft) setFormData(draft)
 * }, [])
 * ```
 */
export function saveDraft<T>(formId: string, data: T): boolean {
  return setStorageItem(`draft_${formId}`, data, { ttl: 24 * 60 * 60 * 1000 }) // 24 hours
}

/**
 * Get form draft from localStorage
 */
export function getDraft<T>(formId: string): T | undefined {
  return getStorageItem<T>(`draft_${formId}`)
}

/**
 * Clear form draft
 */
export function clearDraft(formId: string): boolean {
  return removeStorageItem(`draft_${formId}`)
}

/**
 * Cache data with automatic expiration
 * 
 * @example
 * ```ts
 * const cachedData = getCache<Company[]>('companies')
 * if (!cachedData) {
 *   const data = await fetchCompanies()
 *   setCache('companies', data, 5 * 60 * 1000) // Cache for 5 minutes
 * }
 * ```
 */
export function setCache<T>(key: string, data: T, ttlMs: number = 300000): boolean {
  return setStorageItem(`cache_${key}`, data, { ttl: ttlMs })
}

/**
 * Get cached data
 */
export function getCache<T>(key: string): T | undefined {
  return getStorageItem<T>(`cache_${key}`)
}

/**
 * Clear cached data
 */
export function clearCache(key: string): boolean {
  return removeStorageItem(`cache_${key}`)
}

/**
 * Clear all cached data
 */
export function clearAllCache(): void {
  if (!isBrowser()) return
  
  const keys = getStorageKeys()
  keys.forEach(key => {
    if (key.startsWith('cache_')) {
      localStorage.removeItem(key)
    }
  })
}

// ===========================================
// React Hook
// ===========================================

import { useState, useEffect, useCallback } from 'react'

/**
 * React hook for synced localStorage state
 * 
 * @example
 * ```tsx
 * const [theme, setTheme] = useLocalStorage<'light' | 'dark'>('theme', 'light')
 * 
 * // Updates localStorage and state together
 * setTheme('dark')
 * ```
 */
export function useLocalStorage<T>(
  key: string,
  initialValue: T
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
  // State to store our value
  const [storedValue, setStoredValue] = useState<T>(() => {
    return getStorageItem<T>(key, initialValue) ?? initialValue
  })

  // Return a wrapped version of useState's setter function that
  // persists the new value to localStorage
  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      setStoredValue(prev => {
        const valueToStore = value instanceof Function ? value(prev) : value
        setStorageItem(key, valueToStore)
        return valueToStore
      })
    },
    [key]
  )

  // Remove the item
  const removeValue = useCallback(() => {
    removeStorageItem(key)
    setStoredValue(initialValue)
  }, [key, initialValue])

  // Listen for changes from other tabs
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === key && e.newValue) {
        try {
          const parsed: StorageItem<T> = JSON.parse(e.newValue)
          setStoredValue(parsed.value)
        } catch {
          // Ignore parse errors
        }
      }
    }

    window.addEventListener('storage', handleStorageChange)
    return () => window.removeEventListener('storage', handleStorageChange)
  }, [key])

  return [storedValue, setValue, removeValue]
}

