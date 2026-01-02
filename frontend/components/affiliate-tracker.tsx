'use client'

/**
 * Global Affiliate Tracker Component
 * 
 * This component runs on every page to track affiliate clicks.
 * It checks for ?ref= parameter and records the click to the backend.
 * Should be placed in the root layout to ensure all landing pages are tracked.
 */

import { useEffect, useRef } from 'react'
import { useSearchParams, usePathname } from 'next/navigation'
import { 
    checkAndStoreAffiliateCode, 
    trackAffiliateClick,
    getStoredAffiliateData 
} from '@/lib/affiliate'

export function AffiliateTracker() {
    const searchParams = useSearchParams()
    const pathname = usePathname()
    const hasTracked = useRef(false)
    
    useEffect(() => {
        // Only run once per page load with ref parameter
        const refCode = searchParams.get('ref') || searchParams.get('affiliate')
        
        // Skip if no ref code or already tracked this session
        if (!refCode || hasTracked.current) {
            return
        }
        
        const trackClick = async () => {
            try {
                const params = new URLSearchParams(searchParams.toString())
                
                // Check and store affiliate data
                const affiliateData = checkAndStoreAffiliateCode(params, pathname)
                
                // If we have new affiliate data (not previously validated), track the click
                if (affiliateData && !affiliateData.validated) {
                    hasTracked.current = true
                    
                    const success = await trackAffiliateClick(affiliateData, {
                        utm_source: params.get('utm_source'),
                        utm_medium: params.get('utm_medium'),
                        utm_campaign: params.get('utm_campaign'),
                    })
                    
                    if (success) {
                        console.log('[Affiliate] Click tracked successfully for:', affiliateData.code)
                    } else {
                        console.warn('[Affiliate] Click tracking returned false for:', affiliateData.code)
                    }
                } else if (affiliateData?.validated) {
                    // Already validated from a previous visit
                    hasTracked.current = true
                    console.log('[Affiliate] Using existing affiliate data:', affiliateData.code)
                }
            } catch (error) {
                console.error('[Affiliate] Error tracking click:', error)
            }
        }
        
        trackClick()
    }, [searchParams, pathname])
    
    // This component doesn't render anything
    return null
}

