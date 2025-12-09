'use client'

import { useEffect, useCallback, useRef } from 'react'

// ===========================================
// Types
// ===========================================

type KeyboardModifiers = {
  ctrl?: boolean
  alt?: boolean
  shift?: boolean
  meta?: boolean
}

type KeyHandler = (event: KeyboardEvent) => void

interface KeyBinding {
  key: string
  modifiers?: KeyboardModifiers
  handler: KeyHandler
  /** Only trigger when this element or its children have focus */
  scope?: 'global' | 'focused'
  /** Prevent default browser behavior */
  preventDefault?: boolean
}

// ===========================================
// useKeyboardShortcut
// ===========================================

/**
 * Hook for handling keyboard shortcuts
 * 
 * @example
 * ```tsx
 * // Single shortcut
 * useKeyboardShortcut('Escape', () => closeModal())
 * 
 * // With modifiers
 * useKeyboardShortcut('s', () => save(), { ctrl: true })
 * 
 * // Multiple shortcuts
 * useKeyboardShortcut(['ArrowUp', 'ArrowDown'], handleNavigation)
 * ```
 */
export function useKeyboardShortcut(
  key: string | string[],
  handler: KeyHandler,
  modifiers?: KeyboardModifiers & { enabled?: boolean }
) {
  const { enabled = true, ...mods } = modifiers || {}

  useEffect(() => {
    if (!enabled) return

    const keys = Array.isArray(key) ? key : [key]

    const handleKeyDown = (event: KeyboardEvent) => {
      // Check if key matches
      if (!keys.includes(event.key)) return

      // Check modifiers
      if (mods.ctrl !== undefined && event.ctrlKey !== mods.ctrl) return
      if (mods.alt !== undefined && event.altKey !== mods.alt) return
      if (mods.shift !== undefined && event.shiftKey !== mods.shift) return
      if (mods.meta !== undefined && event.metaKey !== mods.meta) return

      handler(event)
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [key, handler, enabled, mods.ctrl, mods.alt, mods.shift, mods.meta])
}

// ===========================================
// useKeyboardNavigation
// ===========================================

interface UseKeyboardNavigationOptions {
  /** Total number of items */
  itemCount: number
  /** Current active index */
  activeIndex: number
  /** Called when active index should change */
  onActiveIndexChange: (index: number) => void
  /** Called when item is selected (Enter/Space) */
  onSelect?: (index: number) => void
  /** Wrap around at ends */
  wrap?: boolean
  /** Navigation orientation */
  orientation?: 'vertical' | 'horizontal' | 'both'
  /** Enable type-ahead search */
  typeAhead?: boolean
  /** Get label for type-ahead (required if typeAhead is true) */
  getItemLabel?: (index: number) => string
}

/**
 * Hook for keyboard navigation in lists/grids
 * 
 * @example
 * ```tsx
 * const { containerProps, getItemProps } = useKeyboardNavigation({
 *   itemCount: items.length,
 *   activeIndex,
 *   onActiveIndexChange: setActiveIndex,
 *   onSelect: handleSelect,
 * })
 * 
 * <ul {...containerProps}>
 *   {items.map((item, index) => (
 *     <li key={item.id} {...getItemProps(index)}>
 *       {item.name}
 *     </li>
 *   ))}
 * </ul>
 * ```
 */
export function useKeyboardNavigation(options: UseKeyboardNavigationOptions) {
  const {
    itemCount,
    activeIndex,
    onActiveIndexChange,
    onSelect,
    wrap = true,
    orientation = 'vertical',
    typeAhead = false,
    getItemLabel,
  } = options

  const typeAheadBuffer = useRef('')
  const typeAheadTimeout = useRef<ReturnType<typeof setTimeout>>()

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      let newIndex: number | null = null

      // Navigation keys based on orientation
      const prevKeys = orientation === 'horizontal' 
        ? ['ArrowLeft'] 
        : orientation === 'vertical' 
          ? ['ArrowUp'] 
          : ['ArrowUp', 'ArrowLeft']
      
      const nextKeys = orientation === 'horizontal'
        ? ['ArrowRight']
        : orientation === 'vertical'
          ? ['ArrowDown']
          : ['ArrowDown', 'ArrowRight']

      if (prevKeys.includes(event.key)) {
        event.preventDefault()
        if (activeIndex > 0) {
          newIndex = activeIndex - 1
        } else if (wrap) {
          newIndex = itemCount - 1
        }
      }

      if (nextKeys.includes(event.key)) {
        event.preventDefault()
        if (activeIndex < itemCount - 1) {
          newIndex = activeIndex + 1
        } else if (wrap) {
          newIndex = 0
        }
      }

      if (event.key === 'Home') {
        event.preventDefault()
        newIndex = 0
      }

      if (event.key === 'End') {
        event.preventDefault()
        newIndex = itemCount - 1
      }

      if ((event.key === 'Enter' || event.key === ' ') && onSelect) {
        event.preventDefault()
        onSelect(activeIndex)
      }

      // Type-ahead search
      if (typeAhead && getItemLabel && event.key.length === 1 && !event.ctrlKey && !event.metaKey) {
        event.preventDefault()
        
        // Clear timeout and add to buffer
        if (typeAheadTimeout.current) {
          clearTimeout(typeAheadTimeout.current)
        }
        typeAheadBuffer.current += event.key.toLowerCase()

        // Find matching item
        for (let i = 0; i < itemCount; i++) {
          const label = getItemLabel(i).toLowerCase()
          if (label.startsWith(typeAheadBuffer.current)) {
            newIndex = i
            break
          }
        }

        // Clear buffer after delay
        typeAheadTimeout.current = setTimeout(() => {
          typeAheadBuffer.current = ''
        }, 500)
      }

      if (newIndex !== null && newIndex !== activeIndex) {
        onActiveIndexChange(newIndex)
      }
    },
    [activeIndex, itemCount, onActiveIndexChange, onSelect, wrap, orientation, typeAhead, getItemLabel]
  )

  const containerProps = {
    role: 'listbox',
    tabIndex: 0,
    onKeyDown: handleKeyDown as unknown as React.KeyboardEventHandler,
    'aria-activedescendant': `item-${activeIndex}`,
  }

  const getItemProps = (index: number) => ({
    id: `item-${index}`,
    role: 'option',
    'aria-selected': index === activeIndex,
    tabIndex: index === activeIndex ? 0 : -1,
  })

  return {
    containerProps,
    getItemProps,
  }
}

// ===========================================
// useEscapeKey
// ===========================================

/**
 * Hook for handling Escape key press
 * 
 * @example
 * ```tsx
 * useEscapeKey(() => closeModal(), { enabled: isOpen })
 * ```
 */
export function useEscapeKey(
  handler: () => void,
  options: { enabled?: boolean } = {}
) {
  const { enabled = true } = options

  useKeyboardShortcut('Escape', handler, { enabled })
}

// ===========================================
// useArrowKeys
// ===========================================

type ArrowDirection = 'up' | 'down' | 'left' | 'right'

/**
 * Hook for handling arrow key navigation
 * 
 * @example
 * ```tsx
 * useArrowKeys({
 *   onUp: () => moveUp(),
 *   onDown: () => moveDown(),
 * })
 * ```
 */
export function useArrowKeys(
  handlers: Partial<Record<`on${Capitalize<ArrowDirection>}`, (event: KeyboardEvent) => void>>,
  options: { enabled?: boolean; preventDefault?: boolean } = {}
) {
  const { enabled = true, preventDefault = true } = options

  useEffect(() => {
    if (!enabled) return

    const handleKeyDown = (event: KeyboardEvent) => {
      const handler = {
        ArrowUp: handlers.onUp,
        ArrowDown: handlers.onDown,
        ArrowLeft: handlers.onLeft,
        ArrowRight: handlers.onRight,
      }[event.key]

      if (handler) {
        if (preventDefault) event.preventDefault()
        handler(event)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [enabled, preventDefault, handlers])
}

// ===========================================
// useFocusTrap
// ===========================================

/**
 * Hook for trapping focus within a container
 * 
 * @example
 * ```tsx
 * const modalRef = useRef<HTMLDivElement>(null)
 * useFocusTrap(modalRef, { enabled: isOpen })
 * 
 * <div ref={modalRef}>
 *   <button>First</button>
 *   <button>Last</button>
 * </div>
 * ```
 */
export function useFocusTrap(
  containerRef: React.RefObject<HTMLElement>,
  options: { enabled?: boolean; initialFocus?: React.RefObject<HTMLElement> } = {}
) {
  const { enabled = true, initialFocus } = options
  const previousFocus = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!enabled || !containerRef.current) return

    // Save current focus
    previousFocus.current = document.activeElement as HTMLElement

    // Focus initial element or first focusable
    const focusInitial = () => {
      if (initialFocus?.current) {
        initialFocus.current.focus()
      } else if (containerRef.current) {
        const focusable = containerRef.current.querySelector<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        focusable?.focus()
      }
    }

    requestAnimationFrame(focusInitial)

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !containerRef.current) return

      const focusableElements = containerRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )

      const firstElement = focusableElements[0]
      const lastElement = focusableElements[focusableElements.length - 1]

      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault()
        lastElement?.focus()
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault()
        firstElement?.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      // Restore focus
      previousFocus.current?.focus()
    }
  }, [enabled, containerRef, initialFocus])
}

// ===========================================
// useHotkeys
// ===========================================

type HotkeyConfig = {
  [key: string]: KeyHandler
}

/**
 * Hook for multiple keyboard shortcuts
 * 
 * @example
 * ```tsx
 * useHotkeys({
 *   'ctrl+s': () => save(),
 *   'ctrl+z': () => undo(),
 *   'Escape': () => close(),
 * })
 * ```
 */
export function useHotkeys(
  config: HotkeyConfig,
  options: { enabled?: boolean } = {}
) {
  const { enabled = true } = options

  useEffect(() => {
    if (!enabled) return

    const handleKeyDown = (event: KeyboardEvent) => {
      // Build key string
      const parts: string[] = []
      if (event.ctrlKey) parts.push('ctrl')
      if (event.altKey) parts.push('alt')
      if (event.shiftKey) parts.push('shift')
      if (event.metaKey) parts.push('meta')
      parts.push(event.key.toLowerCase())

      const keyString = parts.join('+')
      const handler = config[keyString] || config[event.key]

      if (handler) {
        event.preventDefault()
        handler(event)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [config, enabled])
}

export default useKeyboardShortcut

