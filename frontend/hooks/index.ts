/**
 * Custom React hooks for DealMotion.
 * 
 * Import hooks from here:
 * @example
 * import { useAuth, useRequireAuth, useFetch, useMutation, useKeyboardShortcut } from '@/hooks'
 */

export { useAuth, useRequireAuth } from './useAuth'
export { useFetch, useMutation, usePolling } from './useFetch'
export { 
  useKeyboardShortcut, 
  useKeyboardNavigation, 
  useEscapeKey, 
  useArrowKeys, 
  useFocusTrap, 
  useHotkeys 
} from './useKeyboard'
export { useCreditCheck } from './use-credit-check'
