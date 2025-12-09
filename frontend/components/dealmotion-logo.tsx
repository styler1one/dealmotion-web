'use client'

import { cn } from '@/lib/utils'

interface LogoIconProps {
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

/**
 * DealMotion Icon - The "D" with motion lines
 * Used for favicon, app icon, and small logo representations
 */
export function LogoIcon({ className, size = 'md' }: LogoIconProps) {
  const sizes = {
    sm: 'w-6 h-6',
    md: 'w-8 h-8',
    lg: 'w-10 h-10',
  }

  return (
    <svg 
      viewBox="0 0 32 32" 
      fill="none" 
      xmlns="http://www.w3.org/2000/svg"
      className={cn(sizes[size], className)}
    >
      <defs>
        <linearGradient id="dmGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#3B82F6"/>
          <stop offset="100%" stopColor="#8B5CF6"/>
        </linearGradient>
      </defs>
      
      {/* Background rounded square */}
      <rect width="32" height="32" rx="8" fill="url(#dmGradient)"/>
      
      {/* D shape (white) */}
      <path d="M10 8h6c4.418 0 8 3.582 8 8s-3.582 8-8 8h-6V8z" fill="white"/>
      
      {/* Inner cut for D */}
      <path d="M14 12h2c2.209 0 4 1.791 4 4s-1.791 4-4 4h-2V12z" fill="url(#dmGradient)"/>
      
      {/* Motion lines */}
      <rect x="6" y="12" width="4" height="1.5" rx="0.75" fill="white" opacity="0.7"/>
      <rect x="5" y="15.5" width="5" height="1.5" rx="0.75" fill="white" opacity="0.5"/>
      <rect x="6" y="19" width="4" height="1.5" rx="0.75" fill="white" opacity="0.7"/>
    </svg>
  )
}

interface LogoProps {
  className?: string
  showText?: boolean
  darkMode?: boolean
}

/**
 * Full DealMotion Logo with text
 * Used in headers, footers, and marketing pages
 */
export function Logo({ className, showText = true, darkMode = false }: LogoProps) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <LogoIcon size="md" />
      {showText && (
        <span className={cn(
          'font-bold text-xl',
          darkMode ? 'text-white' : 'text-slate-900 dark:text-white'
        )}>
          Deal<span className="bg-gradient-to-r from-blue-500 to-violet-600 bg-clip-text text-transparent">Motion</span>
        </span>
      )}
    </div>
  )
}

/**
 * Compact logo for sidebar when collapsed
 */
export function LogoCompact({ className }: { className?: string }) {
  return <LogoIcon size="md" className={className} />
}

