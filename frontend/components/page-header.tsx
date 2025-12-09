'use client'

import { ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'

interface PageHeaderProps {
  /** Page title */
  title: string
  /** Optional subtitle/description */
  subtitle?: string
  /** Optional icon to display before title */
  icon?: keyof typeof Icons
  /** Icon color class (e.g., 'text-blue-600') */
  iconColor?: string
  /** Show back button */
  showBack?: boolean
  /** Custom back URL (defaults to browser back) */
  backUrl?: string
  /** Back button label */
  backLabel?: string
  /** Actions to display on the right side */
  actions?: ReactNode
  /** Additional content below the header */
  children?: ReactNode
  /** Additional CSS classes */
  className?: string
  /** Badge content (e.g., status) */
  badge?: ReactNode
}

/**
 * Consistent page header component
 * 
 * @example
 * ```tsx
 * <PageHeader
 *   title="Research Agent"
 *   subtitle="AI-powered prospect research"
 *   icon="search"
 *   iconColor="text-blue-600"
 *   actions={
 *     <Button onClick={handleNew}>
 *       <Icons.plus className="h-4 w-4 mr-2" />
 *       New Research
 *     </Button>
 *   }
 * />
 * ```
 */
export function PageHeader({
  title,
  subtitle,
  icon,
  iconColor = 'text-slate-600 dark:text-slate-400',
  showBack = false,
  backUrl,
  backLabel = 'Back',
  actions,
  children,
  className,
  badge,
}: PageHeaderProps) {
  const router = useRouter()
  const Icon = icon ? Icons[icon] : null

  const handleBack = () => {
    if (backUrl) {
      router.push(backUrl)
    } else {
      router.back()
    }
  }

  return (
    <div className={cn('mb-6', className)}>
      {/* Back button */}
      {showBack && (
        <button
          onClick={handleBack}
          className="flex items-center gap-1 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 mb-4 transition-colors"
        >
          <Icons.arrowLeft className="h-4 w-4" />
          {backLabel}
        </button>
      )}

      {/* Main header row */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-4 min-w-0">
          {/* Icon */}
          {Icon && (
            <div className={cn(
              'flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center',
              'bg-slate-100 dark:bg-slate-800'
            )}>
              <Icon className={cn('h-6 w-6', iconColor)} />
            </div>
          )}

          {/* Title & subtitle */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white truncate">
                {title}
              </h1>
              {badge}
            </div>
            {subtitle && (
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {subtitle}
              </p>
            )}
          </div>
        </div>

        {/* Actions */}
        {actions && (
          <div className="flex-shrink-0 flex items-center gap-2">
            {actions}
          </div>
        )}
      </div>

      {/* Additional content */}
      {children && (
        <div className="mt-4">
          {children}
        </div>
      )}
    </div>
  )
}

/**
 * Page header with tabs
 * 
 * @example
 * ```tsx
 * <PageHeaderWithTabs
 *   title="Settings"
 *   tabs={[
 *     { id: 'general', label: 'General', icon: 'settings' },
 *     { id: 'billing', label: 'Billing', icon: 'creditCard' },
 *   ]}
 *   activeTab="general"
 *   onTabChange={setActiveTab}
 * />
 * ```
 */
interface Tab {
  id: string
  label: string
  icon?: keyof typeof Icons
  badge?: string | number
}

interface PageHeaderWithTabsProps extends Omit<PageHeaderProps, 'children'> {
  tabs: Tab[]
  activeTab: string
  onTabChange: (tabId: string) => void
}

export function PageHeaderWithTabs({
  tabs,
  activeTab,
  onTabChange,
  ...headerProps
}: PageHeaderWithTabsProps) {
  return (
    <PageHeader {...headerProps}>
      <div className="border-b border-slate-200 dark:border-slate-800 -mx-6 px-6">
        <nav className="flex gap-6" aria-label="Tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon ? Icons[tab.icon] : null
            const isActive = tab.id === activeTab
            
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={cn(
                  'flex items-center gap-2 py-3 text-sm font-medium border-b-2 -mb-px transition-colors',
                  isActive
                    ? 'border-blue-600 text-blue-600 dark:border-blue-500 dark:text-blue-500'
                    : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:border-slate-300 dark:hover:border-slate-600'
                )}
              >
                {Icon && <Icon className="h-4 w-4" />}
                {tab.label}
                {tab.badge !== undefined && (
                  <span className={cn(
                    'ml-1 px-1.5 py-0.5 text-xs rounded-full',
                    isActive
                      ? 'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                  )}>
                    {tab.badge}
                  </span>
                )}
              </button>
            )
          })}
        </nav>
      </div>
    </PageHeader>
  )
}

/**
 * Simple section header for within-page sections
 * 
 * @example
 * ```tsx
 * <SectionHeader
 *   title="Contact Persons"
 *   action={<Button size="sm">Add Contact</Button>}
 * />
 * ```
 */
interface SectionHeaderProps {
  title: string
  subtitle?: string
  action?: ReactNode
  className?: string
}

export function SectionHeader({
  title,
  subtitle,
  action,
  className,
}: SectionHeaderProps) {
  return (
    <div className={cn('flex items-center justify-between mb-4', className)}>
      <div>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
          {title}
        </h2>
        {subtitle && (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {subtitle}
          </p>
        )}
      </div>
      {action}
    </div>
  )
}

