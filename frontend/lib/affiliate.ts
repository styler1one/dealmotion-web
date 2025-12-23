/**
 * Affiliate Tracking Utilities
 * 
 * Handles referral code detection, cookie storage, and click tracking
 * for the DealMotion Affiliate Program.
 * 
 * Flow:
 * 1. User lands on site with ?ref=AFF_X7K2M9
 * 2. We store affiliate code + generate click_id in localStorage
 * 3. We call backend to track the click
 * 4. On signup, we pass the affiliate code to the backend
 * 
 * Attribution window: 30 days (enforced server-side, but we expire locally too)
 */

import { v4 as uuidv4 } from 'uuid'

const AFFILIATE_STORAGE_KEY = 'dm_affiliate'
const AFFILIATE_EXPIRY_DAYS = 30

interface AffiliateData {
  code: string
  clickId: string
  landingPage: string
  referrer: string | null
  timestamp: number
  expiresAt: number
  validated?: boolean
  affiliateName?: string | null
}

/**
 * Check URL for affiliate referral code and store it.
 * Call this on every page load (in layout or _app).
 */
export function checkAndStoreAffiliateCode(
  searchParams: URLSearchParams,
  currentPath: string
): AffiliateData | null {
  // Check for ref parameter
  const refCode = searchParams.get('ref') || searchParams.get('affiliate')
  
  if (!refCode) {
    return getStoredAffiliateData()
  }
  
  // Validate format (should be AFF_XXXXXX)
  if (!/^AFF_[A-Z0-9]{6,}$/i.test(refCode)) {
    console.warn('Invalid affiliate code format:', refCode)
    return getStoredAffiliateData()
  }
  
  // Check if we already have this exact code stored
  const existing = getStoredAffiliateData()
  if (existing && existing.code === refCode.toUpperCase()) {
    // Same code, no need to re-track
    return existing
  }
  
  // Generate new click ID
  const clickId = uuidv4()
  const now = Date.now()
  const expiresAt = now + (AFFILIATE_EXPIRY_DAYS * 24 * 60 * 60 * 1000)
  
  const affiliateData: AffiliateData = {
    code: refCode.toUpperCase(),
    clickId,
    landingPage: currentPath,
    referrer: typeof document !== 'undefined' ? document.referrer : null,
    timestamp: now,
    expiresAt,
    validated: false,
  }
  
  // Store in localStorage
  try {
    localStorage.setItem(AFFILIATE_STORAGE_KEY, JSON.stringify(affiliateData))
  } catch (e) {
    console.error('Failed to store affiliate data:', e)
  }
  
  return affiliateData
}

/**
 * Get stored affiliate data from localStorage.
 * Returns null if no data or if expired.
 */
export function getStoredAffiliateData(): AffiliateData | null {
  try {
    const stored = localStorage.getItem(AFFILIATE_STORAGE_KEY)
    if (!stored) return null
    
    const data: AffiliateData = JSON.parse(stored)
    
    // Check expiration
    if (data.expiresAt && Date.now() > data.expiresAt) {
      clearAffiliateData()
      return null
    }
    
    return data
  } catch (e) {
    return null
  }
}

/**
 * Get just the affiliate code if available.
 */
export function getAffiliateCode(): string | null {
  const data = getStoredAffiliateData()
  return data?.code || null
}

/**
 * Get the click ID if available.
 */
export function getAffiliateClickId(): string | null {
  const data = getStoredAffiliateData()
  return data?.clickId || null
}

/**
 * Clear stored affiliate data.
 */
export function clearAffiliateData(): void {
  try {
    localStorage.removeItem(AFFILIATE_STORAGE_KEY)
  } catch (e) {
    console.error('Failed to clear affiliate data:', e)
  }
}

/**
 * Update stored data with validation result.
 */
export function updateAffiliateValidation(
  validated: boolean,
  affiliateName: string | null
): void {
  const data = getStoredAffiliateData()
  if (!data) return
  
  data.validated = validated
  data.affiliateName = affiliateName
  
  try {
    localStorage.setItem(AFFILIATE_STORAGE_KEY, JSON.stringify(data))
  } catch (e) {
    console.error('Failed to update affiliate data:', e)
  }
}

/**
 * Track affiliate click via backend API.
 * Should be called after storing affiliate data.
 */
export async function trackAffiliateClick(
  data: AffiliateData,
  utmParams?: {
    utm_source?: string | null
    utm_medium?: string | null
    utm_campaign?: string | null
  }
): Promise<boolean> {
  try {
    const response = await fetch('/api/v1/affiliate/clicks', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        affiliate_code: data.code,
        click_id: data.clickId,
        landing_page: data.landingPage,
        referrer_url: data.referrer,
        utm_source: utmParams?.utm_source || null,
        utm_medium: utmParams?.utm_medium || null,
        utm_campaign: utmParams?.utm_campaign || null,
      }),
    })
    
    const result = await response.json()
    return result.success === true
  } catch (e) {
    console.error('Failed to track affiliate click:', e)
    return false
  }
}

/**
 * Validate affiliate code via backend API.
 * Updates stored data with validation result.
 */
export async function validateAffiliateCode(code: string): Promise<{
  valid: boolean
  affiliateName: string | null
}> {
  try {
    const response = await fetch(`/api/v1/affiliate/validate/${encodeURIComponent(code)}`)
    const result = await response.json()
    
    updateAffiliateValidation(result.valid, result.affiliate_name || null)
    
    return {
      valid: result.valid === true,
      affiliateName: result.affiliate_name || null,
    }
  } catch (e) {
    console.error('Failed to validate affiliate code:', e)
    return { valid: false, affiliateName: null }
  }
}

/**
 * Get affiliate data for signup.
 * Returns the data needed to pass to the backend on user registration.
 */
export function getAffiliateSignupData(): {
  affiliateCode: string | null
  clickId: string | null
} {
  const data = getStoredAffiliateData()
  if (!data) {
    return { affiliateCode: null, clickId: null }
  }
  
  return {
    affiliateCode: data.code,
    clickId: data.clickId,
  }
}

/**
 * Hook-friendly function to get affiliate info for display.
 */
export function getAffiliateDisplayInfo(): {
  hasAffiliate: boolean
  affiliateName: string | null
  code: string | null
} {
  const data = getStoredAffiliateData()
  if (!data || !data.validated) {
    return { hasAffiliate: false, affiliateName: null, code: null }
  }
  
  return {
    hasAffiliate: true,
    affiliateName: data.affiliateName || null,
    code: data.code,
  }
}

