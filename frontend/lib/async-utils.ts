/**
 * Async and timing utilities
 * 
 * Includes debounce, throttle, retry, and other async helpers.
 */

// ===========================================
// Debounce & Throttle
// ===========================================

/**
 * Debounce a function - only execute after delay with no new calls
 * 
 * @example
 * ```ts
 * const debouncedSearch = debounce((query: string) => {
 *   searchAPI(query)
 * }, 300)
 * 
 * // In onChange handler
 * debouncedSearch(inputValue)
 * ```
 */
export function debounce<T extends (...args: Parameters<T>) => void>(
  fn: T,
  delay: number
): ((...args: Parameters<T>) => void) & { cancel: () => void } {
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  const debouncedFn = (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    timeoutId = setTimeout(() => {
      fn(...args)
      timeoutId = null
    }, delay)
  }

  debouncedFn.cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }

  return debouncedFn
}

/**
 * Throttle a function - execute at most once per interval
 * 
 * @example
 * ```ts
 * const throttledScroll = throttle(() => {
 *   updateScrollPosition()
 * }, 100)
 * 
 * window.addEventListener('scroll', throttledScroll)
 * ```
 */
export function throttle<T extends (...args: Parameters<T>) => void>(
  fn: T,
  interval: number
): ((...args: Parameters<T>) => void) & { cancel: () => void } {
  let lastCallTime = 0
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  const throttledFn = (...args: Parameters<T>) => {
    const now = Date.now()
    const timeSinceLastCall = now - lastCallTime

    if (timeSinceLastCall >= interval) {
      lastCallTime = now
      fn(...args)
    } else if (!timeoutId) {
      timeoutId = setTimeout(() => {
        lastCallTime = Date.now()
        fn(...args)
        timeoutId = null
      }, interval - timeSinceLastCall)
    }
  }

  throttledFn.cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }

  return throttledFn
}

// ===========================================
// Delay & Sleep
// ===========================================

/**
 * Sleep for a specified duration
 * 
 * @example
 * ```ts
 * await sleep(1000) // Wait 1 second
 * ```
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Wait for a condition to be true
 * 
 * @example
 * ```ts
 * await waitFor(() => document.querySelector('.modal') !== null)
 * ```
 */
export async function waitFor(
  condition: () => boolean,
  options: { timeout?: number; interval?: number } = {}
): Promise<void> {
  const { timeout = 5000, interval = 100 } = options
  const startTime = Date.now()

  while (!condition()) {
    if (Date.now() - startTime > timeout) {
      throw new Error('waitFor timeout exceeded')
    }
    await sleep(interval)
  }
}

// ===========================================
// Retry
// ===========================================

interface RetryOptions {
  /** Maximum number of attempts */
  maxAttempts?: number
  /** Delay between attempts in ms */
  delay?: number
  /** Multiply delay by this factor after each attempt */
  backoffFactor?: number
  /** Maximum delay between attempts */
  maxDelay?: number
  /** Should retry on this error? */
  shouldRetry?: (error: Error, attempt: number) => boolean
  /** Called before each retry */
  onRetry?: (error: Error, attempt: number) => void
}

/**
 * Retry an async function with exponential backoff
 * 
 * @example
 * ```ts
 * const data = await retry(
 *   () => fetchAPI('/unstable-endpoint'),
 *   { maxAttempts: 3, delay: 1000 }
 * )
 * ```
 */
export async function retry<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const {
    maxAttempts = 3,
    delay = 1000,
    backoffFactor = 2,
    maxDelay = 30000,
    shouldRetry = () => true,
    onRetry,
  } = options

  let lastError: Error
  let currentDelay = delay

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error))

      if (attempt === maxAttempts || !shouldRetry(lastError, attempt)) {
        throw lastError
      }

      onRetry?.(lastError, attempt)
      
      await sleep(currentDelay)
      currentDelay = Math.min(currentDelay * backoffFactor, maxDelay)
    }
  }

  throw lastError!
}

// ===========================================
// Timeout
// ===========================================

/**
 * Wrap a promise with a timeout
 * 
 * @example
 * ```ts
 * const data = await withTimeout(fetchData(), 5000)
 * ```
 */
export async function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
  errorMessage = 'Operation timed out'
): Promise<T> {
  let timeoutId: ReturnType<typeof setTimeout>

  const timeoutPromise = new Promise<never>((_, reject) => {
    timeoutId = setTimeout(() => {
      reject(new Error(errorMessage))
    }, timeoutMs)
  })

  try {
    return await Promise.race([promise, timeoutPromise])
  } finally {
    clearTimeout(timeoutId!)
  }
}

// ===========================================
// Queue
// ===========================================

/**
 * Simple async queue that processes items one at a time
 * 
 * @example
 * ```ts
 * const queue = createQueue<UploadTask>(async (task) => {
 *   await uploadFile(task.file)
 * })
 * 
 * queue.add({ file: file1 })
 * queue.add({ file: file2 })
 * ```
 */
export function createQueue<T>(
  processor: (item: T) => Promise<void>,
  options: { concurrency?: number } = {}
) {
  const { concurrency = 1 } = options
  const queue: T[] = []
  let activeCount = 0
  let isPaused = false

  const processNext = async () => {
    if (isPaused || activeCount >= concurrency || queue.length === 0) {
      return
    }

    const item = queue.shift()!
    activeCount++

    try {
      await processor(item)
    } catch (error) {
      console.error('Queue processor error:', error)
    } finally {
      activeCount--
      processNext()
    }
  }

  return {
    add: (item: T) => {
      queue.push(item)
      processNext()
    },
    pause: () => {
      isPaused = true
    },
    resume: () => {
      isPaused = false
      processNext()
    },
    clear: () => {
      queue.length = 0
    },
    get size() {
      return queue.length
    },
    get isProcessing() {
      return activeCount > 0
    },
  }
}

// ===========================================
// Polling
// ===========================================

/**
 * Poll a function until condition is met or timeout
 * 
 * @example
 * ```ts
 * const status = await poll(
 *   () => checkJobStatus(jobId),
 *   (status) => status === 'completed' || status === 'failed',
 *   { interval: 2000, timeout: 60000 }
 * )
 * ```
 */
export async function poll<T>(
  fn: () => Promise<T>,
  condition: (result: T) => boolean,
  options: { interval?: number; timeout?: number } = {}
): Promise<T> {
  const { interval = 1000, timeout = 30000 } = options
  const startTime = Date.now()

  while (true) {
    const result = await fn()
    
    if (condition(result)) {
      return result
    }

    if (Date.now() - startTime > timeout) {
      throw new Error('Polling timeout exceeded')
    }

    await sleep(interval)
  }
}

// ===========================================
// Mutex / Lock
// ===========================================

/**
 * Simple mutex for preventing concurrent execution
 * 
 * @example
 * ```ts
 * const mutex = createMutex()
 * 
 * async function criticalSection() {
 *   const release = await mutex.acquire()
 *   try {
 *     // Only one execution at a time
 *     await doWork()
 *   } finally {
 *     release()
 *   }
 * }
 * ```
 */
export function createMutex() {
  let locked = false
  const waitQueue: (() => void)[] = []

  return {
    acquire: (): Promise<() => void> => {
      return new Promise((resolve) => {
        const tryAcquire = () => {
          if (!locked) {
            locked = true
            resolve(() => {
              locked = false
              const next = waitQueue.shift()
              if (next) next()
            })
          } else {
            waitQueue.push(tryAcquire)
          }
        }
        tryAcquire()
      })
    },
    get isLocked() {
      return locked
    },
  }
}

