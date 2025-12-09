'use client'

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { useCoach } from './CoachProvider'
import { X, Lightbulb, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/**
 * Types of inline tips that can be shown
 */
export type InlineTipType = 
  | 'research_form'
  | 'contacts_empty'
  | 'contacts_few'
  | 'prep_form'
  | 'prep_no_contacts'
  | 'followup_form'
  | 'deal_form'
  | 'export_available'

/**
 * Configuration for inline tips
 */
interface InlineTipConfig {
  id: string
  type: InlineTipType
  icon?: string
  title: string
  description: string
  actionLabel?: string
  actionRoute?: string
  dismissable?: boolean
  showOnce?: boolean
}

/**
 * Pre-configured inline tips - icons and settings only
 * Labels and descriptions come from translations
 */
const INLINE_TIPS_CONFIG: Record<InlineTipType, { icon: string; dismissable: boolean; showOnce?: boolean; hasAction?: boolean }> = {
  research_form: { icon: '🔍', dismissable: true },
  contacts_empty: { icon: '👤', dismissable: true, hasAction: true },
  contacts_few: { icon: '👥', dismissable: true },
  prep_form: { icon: '📋', dismissable: true },
  prep_no_contacts: { icon: '⚠️', dismissable: true, hasAction: true },
  followup_form: { icon: '🎙️', dismissable: true },
  deal_form: { icon: '💼', dismissable: true },
  export_available: { icon: '📤', dismissable: true, showOnce: true },
}

/**
 * Get inline tip configuration with translated strings
 */
function getInlineTipConfig(
  type: InlineTipType,
  t: ReturnType<typeof useTranslations>
): Omit<InlineTipConfig, 'id' | 'type'> {
  const config = INLINE_TIPS_CONFIG[type]
  const translationKey = type.replace(/_/g, '') // research_form -> researchForm style handled in translations
  
  // Map type to translation key (snake_case to camelCase for translation keys)
  const keyMap: Record<InlineTipType, string> = {
    research_form: 'researchForm',
    contacts_empty: 'contactsEmpty',
    contacts_few: 'contactsFew',
    prep_form: 'prepForm',
    prep_no_contacts: 'prepNoContacts',
    followup_form: 'followupForm',
    deal_form: 'dealForm',
    export_available: 'exportAvailable',
  }
  
  const key = keyMap[type]
  
  return {
    icon: config.icon,
    title: t(`inlineTips.${key}.title`),
    description: t(`inlineTips.${key}.description`),
    actionLabel: config.hasAction ? t(`inlineTips.${key}.action`) : undefined,
    dismissable: config.dismissable,
    showOnce: config.showOnce,
  }
}

interface CoachInlineTipProps {
  type: InlineTipType
  className?: string
  onAction?: () => void
  /** Override the default config */
  config?: Partial<InlineTipConfig>
  /** Custom ID for dismissal tracking */
  tipId?: string
}

/**
 * Inline tip component that shows contextual coaching hints.
 * 
 * @example
 * ```tsx
 * <CoachInlineTip 
 *   type="contacts_empty" 
 *   onAction={() => router.push('/contacts/new')} 
 * />
 * ```
 */
export function CoachInlineTip({
  type,
  className,
  onAction,
  config: overrideConfig,
  tipId,
}: CoachInlineTipProps) {
  const t = useTranslations('coach')
  const { settings, dismissTipId, isDismissed } = useCoach()
  const [visible, setVisible] = useState(true)
  
  const baseConfig = getInlineTipConfig(type, t)
  const config: InlineTipConfig = {
    ...baseConfig,
    ...overrideConfig,
    id: tipId || `inline-${type}`,
    type,
  }
  
  // Check if this tip should be shown
  const shouldShow = settings?.show_inline_tips !== false && visible
  
  // Check if already dismissed
  useEffect(() => {
    if (isDismissed(config.id)) {
      setVisible(false)
    }
  }, [config.id, isDismissed])
  
  if (!shouldShow) {
    return null
  }
  
  const handleDismiss = () => {
    setVisible(false)
    if (config.showOnce || config.dismissable) {
      dismissTipId(config.id)
    }
  }
  
  const handleAction = () => {
    onAction?.()
  }
  
  return (
    <div 
      className={cn(
        'flex items-start gap-3 p-4 rounded-lg',
        'bg-gradient-to-r from-primary/5 to-primary/10',
        'border border-primary/20',
        'animate-in fade-in slide-in-from-top-2 duration-300',
        className
      )}
    >
      {/* Icon */}
      <div className="text-2xl flex-shrink-0 mt-0.5">
        {config.icon || <Lightbulb className="h-5 w-5 text-primary" />}
      </div>
      
      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h4 className="text-sm font-medium text-foreground">
              {config.title}
            </h4>
            <p className="text-sm text-muted-foreground mt-0.5">
              {config.description}
            </p>
          </div>
          
          {/* Dismiss button */}
          {config.dismissable && (
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 flex-shrink-0 hover:bg-primary/10"
              onClick={handleDismiss}
            >
              <X className="h-4 w-4" />
              <span className="sr-only">Dismiss tip</span>
            </Button>
          )}
        </div>
        
        {/* Action button */}
        {config.actionLabel && (
          <Button
            variant="link"
            size="sm"
            className="h-auto p-0 mt-2 text-primary"
            onClick={handleAction}
          >
            {config.actionLabel}
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        )}
      </div>
    </div>
  )
}

/**
 * Compact version of the inline tip for smaller spaces
 */
export function CoachInlineTipCompact({
  type,
  className,
  tipId,
}: Pick<CoachInlineTipProps, 'type' | 'className' | 'tipId'>) {
  const t = useTranslations('coach')
  const { settings, isDismissed } = useCoach()
  const [visible, setVisible] = useState(true)
  
  const config = getInlineTipConfig(type, t)
  const id = tipId || `inline-${type}`
  
  useEffect(() => {
    if (isDismissed(id)) {
      setVisible(false)
    }
  }, [id, isDismissed])
  
  if (!settings?.show_inline_tips || !visible) {
    return null
  }
  
  return (
    <div 
      className={cn(
        'flex items-center gap-2 py-1.5 px-3 rounded-md',
        'bg-primary/5 text-sm text-muted-foreground',
        'animate-in fade-in duration-200',
        className
      )}
    >
      <span>{config.icon}</span>
      <span>{config.title}</span>
    </div>
  )
}

