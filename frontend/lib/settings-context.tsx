'use client'

import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react'
import { api } from '@/lib/api'

// ==========================================
// Types
// ==========================================

export interface UserSettings {
  app_language: string
  output_language: string
  email_language: string
}

interface SettingsContextType {
  settings: UserSettings
  updateSettings: (newSettings: Partial<UserSettings>) => Promise<void>
  loading: boolean
  loaded: boolean
}

// ==========================================
// Defaults
// ==========================================

const defaultSettings: UserSettings = {
  app_language: 'en',
  output_language: 'en',
  email_language: 'en',
}

// ==========================================
// Context
// ==========================================

const SettingsContext = createContext<SettingsContextType>({
  settings: defaultSettings,
  updateSettings: async () => {},
  loading: true,
  loaded: false,
})

// ==========================================
// Provider
// ==========================================

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<UserSettings>(defaultSettings)
  const [loading, setLoading] = useState(true)
  const [loaded, setLoaded] = useState(false)
  const hasLoadedRef = useRef(false)

  // Load settings from API - no session check needed, api client handles auth
  const loadSettings = useCallback(async () => {
    try {
      const { data, error } = await api.get<UserSettings>('/api/v1/settings')

      if (!error && data) {
        setSettings({
          app_language: data.app_language || defaultSettings.app_language,
          output_language: data.output_language || defaultSettings.output_language,
          email_language: data.email_language || defaultSettings.email_language,
        })
      }
    } catch (error) {
      console.error('Failed to load settings:', error)
    } finally {
      setLoading(false)
      setLoaded(true)
    }
  }, [])

  // Update settings via API - no session check needed, api client handles auth
  const updateSettings = useCallback(async (newSettings: Partial<UserSettings>) => {
    try {
      const { data, error } = await api.patch<UserSettings>('/api/v1/settings', newSettings)

      if (error) {
        throw new Error(error.message || 'Failed to update settings')
      }

      if (data) {
        setSettings(prev => ({
          ...prev,
          ...data,
        }))
      }
    } catch (error) {
      console.error('Failed to update settings:', error)
      throw error
    }
  }, [])

  // Load settings only once on mount
  useEffect(() => {
    if (hasLoadedRef.current) return
    hasLoadedRef.current = true
    loadSettings()
  }, [loadSettings])

  return (
    <SettingsContext.Provider value={{ settings, updateSettings, loading, loaded }}>
      {children}
    </SettingsContext.Provider>
  )
}

// ==========================================
// Hook
// ==========================================

export function useSettings() {
  const context = useContext(SettingsContext)
  if (!context) {
    throw new Error('useSettings must be used within a SettingsProvider')
  }
  return context
}

