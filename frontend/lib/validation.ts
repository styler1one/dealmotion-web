/**
 * Form validation utilities
 * 
 * Simple, type-safe validation functions for common form fields.
 * Can be used with any form library or custom form handling.
 */

// ===========================================
// Types
// ===========================================

export interface ValidationResult {
  valid: boolean
  error?: string
}

export type Validator<T = string> = (value: T) => ValidationResult

// ===========================================
// Validation Result Helpers
// ===========================================

const valid = (): ValidationResult => ({ valid: true })
const invalid = (error: string): ValidationResult => ({ valid: false, error })

// ===========================================
// Basic Validators
// ===========================================

/**
 * Check if value is required (not empty)
 */
export const required = (message = 'This field is required'): Validator => 
  (value) => {
    if (!value || (typeof value === 'string' && !value.trim())) {
      return invalid(message)
    }
    return valid()
  }

/**
 * Check minimum length
 */
export const minLength = (min: number, message?: string): Validator =>
  (value) => {
    if (value.length < min) {
      return invalid(message || `Must be at least ${min} characters`)
    }
    return valid()
  }

/**
 * Check maximum length
 */
export const maxLength = (max: number, message?: string): Validator =>
  (value) => {
    if (value.length > max) {
      return invalid(message || `Must be at most ${max} characters`)
    }
    return valid()
  }

/**
 * Check if value matches a pattern
 */
export const pattern = (regex: RegExp, message = 'Invalid format'): Validator =>
  (value) => {
    if (!regex.test(value)) {
      return invalid(message)
    }
    return valid()
  }

// ===========================================
// Specific Field Validators
// ===========================================

/**
 * Validate email format
 */
export const email = (message = 'Invalid email address'): Validator =>
  (value) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(value)) {
      return invalid(message)
    }
    return valid()
  }

/**
 * Validate URL format
 */
export const url = (message = 'Invalid URL'): Validator =>
  (value) => {
    if (!value) return valid() // Optional field
    try {
      new URL(value)
      return valid()
    } catch {
      return invalid(message)
    }
  }

/**
 * Validate LinkedIn URL
 */
export const linkedinUrl = (message = 'Invalid LinkedIn URL'): Validator =>
  (value) => {
    if (!value) return valid() // Optional field
    const linkedinRegex = /^https?:\/\/(www\.)?linkedin\.com\/(in|company)\/[a-zA-Z0-9-]+\/?$/i
    if (!linkedinRegex.test(value)) {
      return invalid(message)
    }
    return valid()
  }

/**
 * Validate phone number (basic format)
 */
export const phone = (message = 'Invalid phone number'): Validator =>
  (value) => {
    if (!value) return valid() // Optional field
    const phoneRegex = /^[+]?[(]?[0-9]{1,4}[)]?[-\s./0-9]*$/
    if (!phoneRegex.test(value) || value.replace(/\D/g, '').length < 10) {
      return invalid(message)
    }
    return valid()
  }

/**
 * Validate password strength
 */
export const password = (options?: {
  minLength?: number
  requireUppercase?: boolean
  requireLowercase?: boolean
  requireNumbers?: boolean
  requireSpecial?: boolean
}): Validator => {
  const {
    minLength: min = 8,
    requireUppercase = true,
    requireLowercase = true,
    requireNumbers = true,
    requireSpecial = false,
  } = options || {}

  return (value) => {
    if (value.length < min) {
      return invalid(`Password must be at least ${min} characters`)
    }
    if (requireUppercase && !/[A-Z]/.test(value)) {
      return invalid('Password must contain an uppercase letter')
    }
    if (requireLowercase && !/[a-z]/.test(value)) {
      return invalid('Password must contain a lowercase letter')
    }
    if (requireNumbers && !/\d/.test(value)) {
      return invalid('Password must contain a number')
    }
    if (requireSpecial && !/[!@#$%^&*(),.?":{}|<>]/.test(value)) {
      return invalid('Password must contain a special character')
    }
    return valid()
  }
}

// ===========================================
// Composition Utilities
// ===========================================

/**
 * Combine multiple validators - all must pass
 */
export const combine = (...validators: Validator[]): Validator =>
  (value) => {
    for (const validator of validators) {
      const result = validator(value)
      if (!result.valid) {
        return result
      }
    }
    return valid()
  }

/**
 * Make a validator optional (only validate if value exists)
 */
export const optional = (validator: Validator): Validator =>
  (value) => {
    if (!value || (typeof value === 'string' && !value.trim())) {
      return valid()
    }
    return validator(value)
  }

// ===========================================
// Form Validation Helper
// ===========================================

export interface FieldValidation {
  [fieldName: string]: Validator | Validator[]
}

export interface FormErrors {
  [fieldName: string]: string | undefined
}

/**
 * Validate an entire form
 * 
 * @example
 * ```ts
 * const errors = validateForm(
 *   { email: 'test@', name: '' },
 *   {
 *     email: [required(), email()],
 *     name: required('Name is required'),
 *   }
 * )
 * // errors = { email: 'Invalid email address', name: 'Name is required' }
 * ```
 */
export function validateForm<T extends Record<string, string>>(
  values: T,
  validations: Partial<Record<keyof T, Validator | Validator[]>>
): FormErrors {
  const errors: FormErrors = {}

  for (const [field, validators] of Object.entries(validations)) {
    const value = values[field as keyof T] || ''
    const validatorArray = Array.isArray(validators) ? validators : [validators]

    for (const validator of validatorArray) {
      if (validator) {
        const result = validator(value)
        if (!result.valid) {
          errors[field] = result.error
          break
        }
      }
    }
  }

  return errors
}

/**
 * Check if form has any errors
 */
export function hasErrors(errors: FormErrors): boolean {
  return Object.values(errors).some(error => error !== undefined)
}

/**
 * Get first error from form errors
 */
export function getFirstError(errors: FormErrors): string | undefined {
  return Object.values(errors).find(error => error !== undefined)
}

// ===========================================
// File Validation
// ===========================================

/**
 * Validate file size
 */
export function validateFileSize(
  file: File,
  maxSizeBytes: number,
  message?: string
): ValidationResult {
  if (file.size > maxSizeBytes) {
    const maxSizeMB = Math.round(maxSizeBytes / (1024 * 1024))
    return invalid(message || `File size must be less than ${maxSizeMB}MB`)
  }
  return valid()
}

/**
 * Validate file type
 */
export function validateFileType(
  file: File,
  allowedTypes: string[],
  message = 'Invalid file type'
): ValidationResult {
  if (!allowedTypes.includes(file.type)) {
    return invalid(message)
  }
  return valid()
}

/**
 * Validate file
 */
export function validateFile(
  file: File,
  options: {
    maxSize?: number
    allowedTypes?: string[]
    maxSizeMessage?: string
    typeMessage?: string
  } = {}
): ValidationResult {
  const { maxSize, allowedTypes, maxSizeMessage, typeMessage } = options

  if (maxSize) {
    const sizeResult = validateFileSize(file, maxSize, maxSizeMessage)
    if (!sizeResult.valid) return sizeResult
  }

  if (allowedTypes) {
    const typeResult = validateFileType(file, allowedTypes, typeMessage)
    if (!typeResult.valid) return typeResult
  }

  return valid()
}

