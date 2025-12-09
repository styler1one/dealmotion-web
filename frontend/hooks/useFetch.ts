'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { API_BASE_URL } from '@/lib/constants'

/**
 * Fetch state interface
 */
interface FetchState<T> {
  data: T | null
  error: Error | null
  isLoading: boolean
  isRefetching: boolean
}

/**
 * Fetch options
 */
interface FetchOptions {
  /** Skip initial fetch (useful for conditional fetching) */
  skip?: boolean
  /** Refetch interval in milliseconds */
  refetchInterval?: number
  /** Custom headers */
  headers?: Record<string, string>
  /** Request body for POST/PATCH requests */
  body?: unknown
  /** HTTP method */
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  /** Called when fetch succeeds */
  onSuccess?: (data: unknown) => void
  /** Called when fetch fails */
  onError?: (error: Error) => void
}

/**
 * Custom hook for data fetching with automatic auth handling
 * 
 * @example
 * ```tsx
 * const { data, error, isLoading, refetch } = useFetch<User[]>('/api/v1/users')
 * 
 * if (isLoading) return <Skeleton />
 * if (error) return <ErrorMessage error={error} />
 * return <UserList users={data} />
 * ```
 */
export function useFetch<T = unknown>(
  endpoint: string | null,
  options: FetchOptions = {}
) {
  const {
    skip = false,
    refetchInterval,
    headers: customHeaders,
    body,
    method = 'GET',
    onSuccess,
    onError,
  } = options

  const [state, setState] = useState<FetchState<T>>({
    data: null,
    error: null,
    isLoading: !skip && !!endpoint,
    isRefetching: false,
  })

  const supabase = createClientComponentClient()
  const abortControllerRef = useRef<AbortController | null>(null)

  const fetchData = useCallback(async (isRefetch = false) => {
    if (!endpoint) return

    // Abort previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    // Create new abort controller
    abortControllerRef.current = new AbortController()

    setState(prev => ({
      ...prev,
      isLoading: !isRefetch,
      isRefetching: isRefetch,
      error: null,
    }))

    try {
      // Get auth token
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token

      // Build URL
      const url = endpoint.startsWith('http') 
        ? endpoint 
        : `${API_BASE_URL}${endpoint}`

      // Build headers
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...customHeaders,
      }
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      // Make request
      const response = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(
          errorData.detail || errorData.message || `HTTP ${response.status}`
        )
      }

      const data = await response.json()
      
      setState({
        data,
        error: null,
        isLoading: false,
        isRefetching: false,
      })

      onSuccess?.(data)
      return data
    } catch (error) {
      // Ignore abort errors
      if (error instanceof Error && error.name === 'AbortError') {
        return
      }

      const fetchError = error instanceof Error ? error : new Error('Unknown error')
      
      setState(prev => ({
        ...prev,
        error: fetchError,
        isLoading: false,
        isRefetching: false,
      }))

      onError?.(fetchError)
    }
  }, [endpoint, method, body, customHeaders, supabase, onSuccess, onError])

  // Initial fetch
  useEffect(() => {
    if (!skip && endpoint) {
      fetchData()
    }

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [endpoint, skip, fetchData])

  // Refetch interval
  useEffect(() => {
    if (!refetchInterval || skip || !endpoint) return

    const interval = setInterval(() => {
      fetchData(true)
    }, refetchInterval)

    return () => clearInterval(interval)
  }, [refetchInterval, skip, endpoint, fetchData])

  const refetch = useCallback(() => fetchData(true), [fetchData])

  const mutate = useCallback((newData: T | ((prev: T | null) => T)) => {
    setState(prev => ({
      ...prev,
      data: typeof newData === 'function' 
        ? (newData as (prev: T | null) => T)(prev.data)
        : newData,
    }))
  }, [])

  return {
    ...state,
    refetch,
    mutate,
  }
}

/**
 * Hook for mutations (POST, PATCH, PUT, DELETE)
 * 
 * @example
 * ```tsx
 * const { mutate, isLoading, error } = useMutation<User>('/api/v1/users')
 * 
 * const handleSubmit = async (data: CreateUserData) => {
 *   const result = await mutate(data)
 *   if (result) {
 *     toast.success('User created!')
 *   }
 * }
 * ```
 */
export function useMutation<T = unknown, TInput = unknown>(
  endpoint: string,
  options: Omit<FetchOptions, 'body' | 'skip' | 'refetchInterval'> & {
    method?: 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  } = {}
) {
  const { method = 'POST', headers: customHeaders, onSuccess, onError } = options

  const [state, setState] = useState<{
    data: T | null
    error: Error | null
    isLoading: boolean
  }>({
    data: null,
    error: null,
    isLoading: false,
  })

  const supabase = createClientComponentClient()

  const mutate = useCallback(async (input?: TInput): Promise<T | null> => {
    setState({ data: null, error: null, isLoading: true })

    try {
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token

      const url = endpoint.startsWith('http')
        ? endpoint
        : `${API_BASE_URL}${endpoint}`

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...customHeaders,
      }
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const response = await fetch(url, {
        method,
        headers,
        body: input ? JSON.stringify(input) : undefined,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(
          errorData.detail || errorData.message || `HTTP ${response.status}`
        )
      }

      const data = await response.json()
      
      setState({ data, error: null, isLoading: false })
      onSuccess?.(data)
      return data
    } catch (error) {
      const mutationError = error instanceof Error ? error : new Error('Unknown error')
      setState({ data: null, error: mutationError, isLoading: false })
      onError?.(mutationError)
      return null
    }
  }, [endpoint, method, customHeaders, supabase, onSuccess, onError])

  const reset = useCallback(() => {
    setState({ data: null, error: null, isLoading: false })
  }, [])

  return {
    ...state,
    mutate,
    reset,
  }
}

/**
 * Hook for polling data at regular intervals
 * 
 * @example
 * ```tsx
 * const { data, stop, start } = usePolling<Status>(
 *   '/api/v1/research/123/status',
 *   3000, // Poll every 3 seconds
 *   {
 *     onSuccess: (data) => {
 *       if (data.status === 'completed') stop()
 *     }
 *   }
 * )
 * ```
 */
export function usePolling<T = unknown>(
  endpoint: string | null,
  intervalMs: number = 5000,
  options: Omit<FetchOptions, 'refetchInterval'> = {}
) {
  const [isPolling, setIsPolling] = useState(true)
  
  const fetchResult = useFetch<T>(endpoint, {
    ...options,
    skip: !isPolling || options.skip,
    refetchInterval: isPolling ? intervalMs : undefined,
  })

  const stop = useCallback(() => setIsPolling(false), [])
  const start = useCallback(() => setIsPolling(true), [])

  return {
    ...fetchResult,
    isPolling,
    stop,
    start,
  }
}

export default useFetch

