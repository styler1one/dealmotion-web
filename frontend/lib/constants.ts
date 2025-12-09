/**
 * Application-wide constants
 * 
 * This file centralizes all constants used throughout the frontend application.
 */

// ===========================================
// API Configuration
// ===========================================

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * API Endpoints - centralized for consistency and maintainability
 */
export const API_ENDPOINTS = {
  // Authentication & Users
  auth: {
    user: '/api/v1/users/me',
    profile: '/api/v1/users/profile',
  },
  
  // Research
  research: {
    start: '/api/v1/research/start',
    briefs: '/api/v1/research/briefs',
    brief: (id: string) => `/api/v1/research/${id}`,
    status: (id: string) => `/api/v1/research/${id}/status`,
    contacts: (researchId: string) => `/api/v1/research/${researchId}/contacts`,
  },
  
  // Preparation
  preparation: {
    start: '/api/v1/prep/start',
    briefs: '/api/v1/prep/briefs',
    brief: (id: string) => `/api/v1/prep/${id}`,
    status: (id: string) => `/api/v1/prep/${id}/status`,
  },
  
  // Follow-up
  followup: {
    upload: '/api/v1/followup/upload',
    uploadTranscript: '/api/v1/followup/upload-transcript',
    list: '/api/v1/followup/list',
    detail: (id: string) => `/api/v1/followup/${id}`,
    status: (id: string) => `/api/v1/followup/${id}/status`,
    regenerateEmail: (id: string) => `/api/v1/followup/${id}/regenerate-email`,
  },
  
  // Profiles
  profile: {
    sales: '/api/v1/profile/sales',
    company: '/api/v1/profile/company',
    salesInterview: {
      start: '/api/v1/profile/sales/interview/start',
      answer: '/api/v1/profile/sales/interview/answer',
      skip: '/api/v1/profile/sales/interview/skip',
    },
    companyInterview: {
      start: '/api/v1/profile/company/interview/start',
      answer: '/api/v1/profile/company/interview/answer',
      skip: '/api/v1/profile/company/interview/skip',
    },
  },
  
  // Knowledge Base
  knowledgeBase: {
    files: '/api/v1/knowledge-base/files',
    upload: '/api/v1/knowledge-base/upload',
    file: (id: string) => `/api/v1/knowledge-base/files/${id}`,
    download: (id: string) => `/api/v1/knowledge-base/files/${id}/download`,
  },
  
  // Prospects
  prospects: {
    list: '/api/v1/prospects',
    create: '/api/v1/prospects',
    detail: (id: string) => `/api/v1/prospects/${id}`,
    search: '/api/v1/prospects/search',
    contacts: (prospectId: string) => `/api/v1/prospects/${prospectId}/contacts`,
  },
  
  // Contacts
  contacts: {
    detail: (id: string) => `/api/v1/contacts/${id}`,
    lookup: '/api/v1/contacts/lookup',
  },
  
  // Settings
  settings: {
    get: '/api/v1/settings',
    update: '/api/v1/settings',
  },
  
  // Billing
  billing: {
    subscription: '/api/v1/billing/subscription',
    plans: '/api/v1/billing/plans',
    checkout: '/api/v1/billing/checkout',
    portal: '/api/v1/billing/portal',
    usage: '/api/v1/billing/usage',
    cancel: '/api/v1/billing/cancel',
    reactivate: '/api/v1/billing/reactivate',
    checkLimit: '/api/v1/billing/check-limit',
  },
  
  // Company Lookup
  companyLookup: {
    search: '/api/v1/research/company-lookup',
  },
} as const

// ===========================================
// Application Configuration
// ===========================================

/**
 * Supported locales for internationalization
 */
export const SUPPORTED_LOCALES = ['nl', 'en', 'de', 'fr', 'es', 'hi', 'ar'] as const
export type SupportedLocale = typeof SUPPORTED_LOCALES[number]

export const DEFAULT_LOCALE: SupportedLocale = 'en'

export const RTL_LOCALES: SupportedLocale[] = ['ar']

/**
 * Locale display names and flags
 */
export const LOCALE_CONFIG: Record<SupportedLocale, { name: string; flag: string; nativeName: string }> = {
  nl: { name: 'Dutch', flag: '🇳🇱', nativeName: 'Nederlands' },
  en: { name: 'English', flag: '🇬🇧', nativeName: 'English' },
  de: { name: 'German', flag: '🇩🇪', nativeName: 'Deutsch' },
  fr: { name: 'French', flag: '🇫🇷', nativeName: 'Français' },
  es: { name: 'Spanish', flag: '🇪🇸', nativeName: 'Español' },
  hi: { name: 'Hindi', flag: '🇮🇳', nativeName: 'हिन्दी' },
  ar: { name: 'Arabic', flag: '🇸🇦', nativeName: 'العربية' },
}

// ===========================================
// Feature Limits (for display purposes)
// ===========================================

export const PLAN_LIMITS = {
  free: {
    research: 5,
    preparation: 5,
    followup: 5,
    knowledgeBase: 3,
    transcriptionMinutes: 15,
  },
  solo: {
    research: -1, // unlimited
    preparation: -1,
    followup: -1,
    knowledgeBase: 25,
    transcriptionMinutes: 300,
  },
  teams: {
    research: -1,
    preparation: -1,
    followup: -1,
    knowledgeBase: -1, // unlimited
    transcriptionMinutes: -1, // unlimited
  },
} as const

// ===========================================
// UI Constants
// ===========================================

/**
 * Meeting types for preparation
 */
export const MEETING_TYPES = [
  'discovery',
  'demo',
  'closing',
  'follow_up',
  'other',
] as const
export type MeetingType = typeof MEETING_TYPES[number]

/**
 * Status values used across the application
 */
export const STATUS = {
  pending: 'pending',
  processing: 'processing',
  completed: 'completed',
  failed: 'failed',
} as const
export type Status = typeof STATUS[keyof typeof STATUS]

/**
 * File upload configuration
 */
export const FILE_UPLOAD = {
  maxSize: 10 * 1024 * 1024, // 10MB
  allowedTypes: {
    documents: ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'],
    audio: ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/webm', 'audio/ogg', 'audio/m4a', 'audio/x-m4a'],
  },
  allowedExtensions: {
    documents: ['.pdf', '.docx', '.txt'],
    audio: ['.mp3', '.wav', '.webm', '.ogg', '.m4a'],
  },
} as const

// ===========================================
// External URLs
// ===========================================

export const EXTERNAL_URLS = {
  support: 'mailto:support@dealmotion.ai',
  docs: 'https://docs.dealmotion.ai',
  privacy: '/privacy',
  terms: '/terms',
} as const

