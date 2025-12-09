/**
 * Accessibility utilities
 * 
 * Helpers for screen readers, focus management, and ARIA attributes.
 */

// ===========================================
// Screen Reader Announcements
// ===========================================

let announcer: HTMLElement | null = null

/**
 * Get or create the live region announcer element
 */
function getAnnouncer(): HTMLElement {
  if (typeof document === 'undefined') {
    throw new Error('getAnnouncer can only be used in browser environment')
  }

  if (!announcer) {
    announcer = document.createElement('div')
    announcer.setAttribute('aria-live', 'polite')
    announcer.setAttribute('aria-atomic', 'true')
    announcer.setAttribute('role', 'status')
    announcer.style.cssText = `
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    `
    document.body.appendChild(announcer)
  }

  return announcer
}

/**
 * Announce a message to screen readers
 * 
 * @example
 * ```ts
 * announce('Item deleted successfully')
 * announce('Error: Please fix the form', 'assertive')
 * ```
 */
export function announce(
  message: string,
  priority: 'polite' | 'assertive' = 'polite'
): void {
  if (typeof document === 'undefined') return

  const element = getAnnouncer()
  element.setAttribute('aria-live', priority)
  
  // Clear and set message (needed for repeated announcements)
  element.textContent = ''
  
  // Use requestAnimationFrame to ensure the clear is processed
  requestAnimationFrame(() => {
    element.textContent = message
  })
}

/**
 * Announce for assertive/important messages (interrupts current speech)
 */
export function announceAssertive(message: string): void {
  announce(message, 'assertive')
}

// ===========================================
// Focus Management
// ===========================================

/**
 * Get all focusable elements within a container
 */
export function getFocusableElements(container: HTMLElement): HTMLElement[] {
  const focusableSelectors = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
    'audio[controls]',
    'video[controls]',
    '[contenteditable]:not([contenteditable="false"])',
  ].join(', ')

  const elements = container.querySelectorAll<HTMLElement>(focusableSelectors)
  
  return Array.from(elements).filter((el) => {
    // Check if element is visible
    const style = window.getComputedStyle(el)
    return style.display !== 'none' && style.visibility !== 'hidden'
  })
}

/**
 * Get the first focusable element in a container
 */
export function getFirstFocusable(container: HTMLElement): HTMLElement | null {
  const elements = getFocusableElements(container)
  return elements[0] || null
}

/**
 * Get the last focusable element in a container
 */
export function getLastFocusable(container: HTMLElement): HTMLElement | null {
  const elements = getFocusableElements(container)
  return elements[elements.length - 1] || null
}

/**
 * Focus the first focusable element in a container
 */
export function focusFirst(container: HTMLElement): boolean {
  const element = getFirstFocusable(container)
  if (element) {
    element.focus()
    return true
  }
  return false
}

/**
 * Focus the last focusable element in a container
 */
export function focusLast(container: HTMLElement): boolean {
  const element = getLastFocusable(container)
  if (element) {
    element.focus()
    return true
  }
  return false
}

/**
 * Save and restore focus (useful for modals)
 * 
 * @example
 * ```ts
 * const restoreFocus = saveFocus()
 * openModal()
 * // When modal closes:
 * restoreFocus()
 * ```
 */
export function saveFocus(): () => void {
  const previouslyFocused = document.activeElement as HTMLElement | null
  
  return () => {
    if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
      previouslyFocused.focus()
    }
  }
}

// ===========================================
// Focus Trap
// ===========================================

interface FocusTrapOptions {
  /** Element to trap focus within */
  container: HTMLElement
  /** Initial element to focus (defaults to first focusable) */
  initialFocus?: HTMLElement | null
  /** Element to return focus to on deactivation */
  returnFocus?: HTMLElement | null
  /** Allow escape key to deactivate */
  escapeDeactivates?: boolean
  /** Called when escape is pressed (if escapeDeactivates is true) */
  onEscape?: () => void
}

/**
 * Create a focus trap for modal dialogs
 * 
 * @example
 * ```ts
 * const trap = createFocusTrap({
 *   container: modalElement,
 *   escapeDeactivates: true,
 *   onEscape: closeModal,
 * })
 * 
 * trap.activate()
 * // When done:
 * trap.deactivate()
 * ```
 */
export function createFocusTrap(options: FocusTrapOptions) {
  const {
    container,
    initialFocus,
    returnFocus,
    escapeDeactivates = true,
    onEscape,
  } = options

  let previouslyFocused: HTMLElement | null = null
  let isActive = false

  const handleKeyDown = (event: KeyboardEvent) => {
    if (!isActive) return

    if (event.key === 'Tab') {
      const focusableElements = getFocusableElements(container)
      
      if (focusableElements.length === 0) {
        event.preventDefault()
        return
      }

      const firstElement = focusableElements[0]
      const lastElement = focusableElements[focusableElements.length - 1]

      if (event.shiftKey) {
        // Shift + Tab
        if (document.activeElement === firstElement) {
          event.preventDefault()
          lastElement.focus()
        }
      } else {
        // Tab
        if (document.activeElement === lastElement) {
          event.preventDefault()
          firstElement.focus()
        }
      }
    }

    if (event.key === 'Escape' && escapeDeactivates) {
      event.preventDefault()
      onEscape?.()
    }
  }

  return {
    activate: () => {
      if (isActive) return

      isActive = true
      previouslyFocused = document.activeElement as HTMLElement

      document.addEventListener('keydown', handleKeyDown)

      // Focus initial element or first focusable
      requestAnimationFrame(() => {
        if (initialFocus) {
          initialFocus.focus()
        } else {
          focusFirst(container)
        }
      })
    },

    deactivate: () => {
      if (!isActive) return

      isActive = false
      document.removeEventListener('keydown', handleKeyDown)

      // Return focus
      const elementToFocus = returnFocus || previouslyFocused
      if (elementToFocus && typeof elementToFocus.focus === 'function') {
        elementToFocus.focus()
      }
    },

    get isActive() {
      return isActive
    },
  }
}

// ===========================================
// ARIA Helpers
// ===========================================

/**
 * Generate a unique ID for ARIA relationships
 */
let idCounter = 0
export function generateAriaId(prefix: string = 'aria'): string {
  return `${prefix}-${++idCounter}`
}

/**
 * Create ARIA describedby relationship
 * 
 * @example
 * ```tsx
 * const { describedById, descriptionProps, triggerProps } = createAriaDescription()
 * 
 * <button {...triggerProps}>Click me</button>
 * <div {...descriptionProps}>This button does something</div>
 * ```
 */
export function createAriaDescription() {
  const id = generateAriaId('description')
  
  return {
    describedById: id,
    descriptionProps: { id },
    triggerProps: { 'aria-describedby': id },
  }
}

/**
 * Create ARIA labelledby relationship
 */
export function createAriaLabel() {
  const id = generateAriaId('label')
  
  return {
    labelledById: id,
    labelProps: { id },
    targetProps: { 'aria-labelledby': id },
  }
}

// ===========================================
// Keyboard Helpers
// ===========================================

/**
 * Check if event is an activation key (Enter or Space)
 */
export function isActivationKey(event: KeyboardEvent): boolean {
  return event.key === 'Enter' || event.key === ' '
}

/**
 * Check if event is an arrow key
 */
export function isArrowKey(event: KeyboardEvent): boolean {
  return ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)
}

/**
 * Get direction from arrow key
 */
export function getArrowDirection(
  event: KeyboardEvent
): 'up' | 'down' | 'left' | 'right' | null {
  switch (event.key) {
    case 'ArrowUp': return 'up'
    case 'ArrowDown': return 'down'
    case 'ArrowLeft': return 'left'
    case 'ArrowRight': return 'right'
    default: return null
  }
}

/**
 * Handle keyboard navigation in a list
 * 
 * @example
 * ```tsx
 * const handleKeyDown = (e: KeyboardEvent) => {
 *   const newIndex = handleListNavigation(e, currentIndex, items.length)
 *   if (newIndex !== null) setCurrentIndex(newIndex)
 * }
 * ```
 */
export function handleListNavigation(
  event: KeyboardEvent,
  currentIndex: number,
  totalItems: number,
  options: { wrap?: boolean; orientation?: 'vertical' | 'horizontal' } = {}
): number | null {
  const { wrap = true, orientation = 'vertical' } = options
  
  const prevKey = orientation === 'vertical' ? 'ArrowUp' : 'ArrowLeft'
  const nextKey = orientation === 'vertical' ? 'ArrowDown' : 'ArrowRight'

  if (event.key === nextKey) {
    event.preventDefault()
    if (currentIndex < totalItems - 1) {
      return currentIndex + 1
    }
    return wrap ? 0 : null
  }

  if (event.key === prevKey) {
    event.preventDefault()
    if (currentIndex > 0) {
      return currentIndex - 1
    }
    return wrap ? totalItems - 1 : null
  }

  if (event.key === 'Home') {
    event.preventDefault()
    return 0
  }

  if (event.key === 'End') {
    event.preventDefault()
    return totalItems - 1
  }

  return null
}

// ===========================================
// Reduced Motion
// ===========================================

/**
 * Check if user prefers reduced motion
 */
export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Get animation duration based on reduced motion preference
 */
export function getAnimationDuration(normalMs: number): number {
  return prefersReducedMotion() ? 0 : normalMs
}

