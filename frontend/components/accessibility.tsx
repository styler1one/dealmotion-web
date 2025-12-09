'use client'

import { ReactNode, forwardRef, useId } from 'react'
import { cn } from '@/lib/utils'

// ===========================================
// VisuallyHidden
// ===========================================

interface VisuallyHiddenProps {
  children: ReactNode
  /** Render as different element */
  as?: 'span' | 'div' | 'p' | 'label'
}

/**
 * Visually hide content while keeping it accessible to screen readers
 * 
 * @example
 * ```tsx
 * <button>
 *   <SearchIcon />
 *   <VisuallyHidden>Search</VisuallyHidden>
 * </button>
 * ```
 */
export function VisuallyHidden({ children, as: Component = 'span' }: VisuallyHiddenProps) {
  return (
    <Component
      className="absolute w-px h-px p-0 -m-px overflow-hidden whitespace-nowrap border-0"
      style={{ clip: 'rect(0, 0, 0, 0)' }}
    >
      {children}
    </Component>
  )
}

// ===========================================
// SkipLink
// ===========================================

interface SkipLinkProps {
  /** Target element ID to skip to */
  targetId: string
  /** Link text */
  children?: ReactNode
  /** Additional CSS classes */
  className?: string
}

/**
 * Skip link for keyboard users to bypass navigation
 * 
 * @example
 * ```tsx
 * // In layout
 * <SkipLink targetId="main-content">Skip to main content</SkipLink>
 * <nav>...</nav>
 * <main id="main-content">...</main>
 * ```
 */
export function SkipLink({ 
  targetId, 
  children = 'Skip to main content',
  className 
}: SkipLinkProps) {
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    const target = document.getElementById(targetId)
    if (target) {
      target.tabIndex = -1
      target.focus()
      target.scrollIntoView()
    }
  }

  return (
    <a
      href={`#${targetId}`}
      onClick={handleClick}
      className={cn(
        'sr-only focus:not-sr-only',
        'focus:fixed focus:top-4 focus:left-4 focus:z-[100]',
        'focus:px-4 focus:py-2 focus:rounded-md',
        'focus:bg-blue-600 focus:text-white focus:outline-none',
        'focus:ring-2 focus:ring-blue-400 focus:ring-offset-2',
        className
      )}
    >
      {children}
    </a>
  )
}

// ===========================================
// LiveRegion
// ===========================================

interface LiveRegionProps {
  /** Message to announce */
  message: string
  /** Politeness level */
  politeness?: 'polite' | 'assertive'
  /** Should clear after announcement */
  clearAfter?: number
}

/**
 * Live region for screen reader announcements
 * 
 * @example
 * ```tsx
 * <LiveRegion message={statusMessage} politeness="polite" />
 * ```
 */
export function LiveRegion({ 
  message, 
  politeness = 'polite',
  clearAfter 
}: LiveRegionProps) {
  return (
    <div
      role="status"
      aria-live={politeness}
      aria-atomic="true"
      className="sr-only"
    >
      {message}
    </div>
  )
}

// ===========================================
// AccessibleIcon
// ===========================================

interface AccessibleIconProps {
  /** The icon component */
  children: ReactNode
  /** Accessible label for the icon */
  label: string
}

/**
 * Wrapper for icons to make them accessible
 * 
 * @example
 * ```tsx
 * <AccessibleIcon label="Settings">
 *   <SettingsIcon />
 * </AccessibleIcon>
 * ```
 */
export function AccessibleIcon({ children, label }: AccessibleIconProps) {
  return (
    <span role="img" aria-label={label}>
      {children}
    </span>
  )
}

// ===========================================
// FocusRing
// ===========================================

interface FocusRingProps {
  children: ReactNode
  /** Focus ring color */
  color?: 'blue' | 'green' | 'red' | 'amber'
  /** Ring offset */
  offset?: number
  /** Additional CSS classes */
  className?: string
}

/**
 * Wrapper that adds a consistent focus ring to its child
 * 
 * @example
 * ```tsx
 * <FocusRing>
 *   <button>Click me</button>
 * </FocusRing>
 * ```
 */
export function FocusRing({ 
  children, 
  color = 'blue', 
  offset = 2,
  className 
}: FocusRingProps) {
  const colorClasses = {
    blue: 'focus-within:ring-blue-500',
    green: 'focus-within:ring-green-500',
    red: 'focus-within:ring-red-500',
    amber: 'focus-within:ring-amber-500',
  }

  return (
    <div
      className={cn(
        'focus-within:ring-2',
        colorClasses[color],
        `focus-within:ring-offset-${offset}`,
        'rounded-md',
        className
      )}
    >
      {children}
    </div>
  )
}

// ===========================================
// DescribedBy
// ===========================================

interface DescribedByProps {
  /** The description text */
  description: string
  /** The element to describe */
  children: (props: { 'aria-describedby': string }) => ReactNode
}

/**
 * Utility for creating aria-describedby relationships
 * 
 * @example
 * ```tsx
 * <DescribedBy description="Your password must be at least 8 characters">
 *   {(props) => <input type="password" {...props} />}
 * </DescribedBy>
 * ```
 */
export function DescribedBy({ description, children }: DescribedByProps) {
  const id = useId()
  
  return (
    <>
      {children({ 'aria-describedby': id })}
      <span id={id} className="sr-only">
        {description}
      </span>
    </>
  )
}

// ===========================================
// FormFieldError
// ===========================================

interface FormFieldErrorProps {
  /** Error message */
  error?: string
  /** Field ID for aria-describedby */
  fieldId: string
}

/**
 * Accessible form field error message
 * 
 * @example
 * ```tsx
 * <input id="email" aria-describedby="email-error" />
 * <FormFieldError fieldId="email" error={errors.email} />
 * ```
 */
export function FormFieldError({ error, fieldId }: FormFieldErrorProps) {
  if (!error) return null

  return (
    <p
      id={`${fieldId}-error`}
      role="alert"
      aria-live="polite"
      className="text-sm text-red-600 dark:text-red-400 mt-1"
    >
      {error}
    </p>
  )
}

// ===========================================
// LoadingAnnouncement
// ===========================================

interface LoadingAnnouncementProps {
  /** Whether loading is in progress */
  isLoading: boolean
  /** Loading message */
  loadingMessage?: string
  /** Completed message */
  completedMessage?: string
}

/**
 * Announces loading state to screen readers
 * 
 * @example
 * ```tsx
 * <LoadingAnnouncement 
 *   isLoading={isLoading}
 *   loadingMessage="Loading results..."
 *   completedMessage="Results loaded"
 * />
 * ```
 */
export function LoadingAnnouncement({
  isLoading,
  loadingMessage = 'Loading...',
  completedMessage = 'Content loaded',
}: LoadingAnnouncementProps) {
  return (
    <div role="status" aria-live="polite" className="sr-only">
      {isLoading ? loadingMessage : completedMessage}
    </div>
  )
}

// ===========================================
// ProgressAnnouncement
// ===========================================

interface ProgressAnnouncementProps {
  /** Current progress (0-100) */
  progress: number
  /** Announce at these intervals (default: [25, 50, 75, 100]) */
  announceAt?: number[]
  /** Custom message template */
  messageTemplate?: (progress: number) => string
}

/**
 * Announces progress to screen readers at intervals
 * 
 * @example
 * ```tsx
 * <ProgressAnnouncement progress={uploadProgress} />
 * ```
 */
export function ProgressAnnouncement({
  progress,
  announceAt = [25, 50, 75, 100],
  messageTemplate = (p) => `${p}% complete`,
}: ProgressAnnouncementProps) {
  const shouldAnnounce = announceAt.includes(Math.round(progress))

  return (
    <div role="status" aria-live="polite" className="sr-only">
      {shouldAnnounce && messageTemplate(Math.round(progress))}
    </div>
  )
}

// ===========================================
// TableCaption
// ===========================================

interface TableCaptionProps {
  /** Caption text */
  children: ReactNode
  /** Visually hide the caption */
  visuallyHidden?: boolean
}

/**
 * Accessible table caption
 * 
 * @example
 * ```tsx
 * <table>
 *   <TableCaption>List of users and their roles</TableCaption>
 *   ...
 * </table>
 * ```
 */
export const TableCaption = forwardRef<HTMLTableCaptionElement, TableCaptionProps>(
  ({ children, visuallyHidden = false }, ref) => {
    return (
      <caption
        ref={ref}
        className={cn(
          visuallyHidden && 'sr-only'
        )}
      >
        {children}
      </caption>
    )
  }
)
TableCaption.displayName = 'TableCaption'

