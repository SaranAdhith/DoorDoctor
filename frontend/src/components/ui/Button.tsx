import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'

import { cn } from '../../lib/cn'
import { Spinner } from './Spinner'

export type ButtonVariant = 'primary' | 'accent' | 'ghost' | 'subtle' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-navy-800 text-text-inverted hover:bg-navy-700 active:bg-navy-900',
  accent: 'bg-brand-500 text-text-inverted hover:bg-brand-600 active:bg-brand-700',
  ghost: 'border border-border-subtle bg-surface-raised text-text-primary hover:bg-surface',
  subtle: 'bg-surface-sunken text-text-primary hover:bg-border-subtle',
  danger: 'bg-critical-600 text-text-inverted hover:bg-critical-700',
}

// `sm` sits below the 44px touch target on purpose: it is only for dense
// desktop toolbars where a pointer is the input, never for a primary action.
const SIZES: Record<ButtonSize, string> = {
  sm: 'h-9 gap-1.5 rounded-md px-3 text-small',
  md: 'min-h-control gap-2 rounded-xl px-4 py-2.5 text-body',
  lg: 'min-h-[3rem] gap-2 rounded-xl px-5 py-3 text-body',
}

/** Shared by Button and LinkButton so an action and a navigation look identical. */
export function buttonClasses({
  variant = 'primary',
  size = 'md',
  fullWidth = false,
}: {
  variant?: ButtonVariant
  size?: ButtonSize
  fullWidth?: boolean
}): string {
  return cn(
    'inline-flex shrink-0 items-center justify-center font-semibold transition-colors',
    'disabled:cursor-not-allowed disabled:opacity-50',
    VARIANTS[variant],
    SIZES[size],
    fullWidth && 'w-full',
  )
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  /** Rendered before the label; omitted while loading so the row never jumps. */
  icon?: ReactNode
  fullWidth?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'primary',
    size = 'md',
    loading = false,
    icon,
    fullWidth = false,
    className,
    children,
    disabled,
    type = 'button',
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(buttonClasses({ variant, size, fullWidth }), className)}
      {...rest}
    >
      {loading ? <Spinner className="h-4 w-4" /> : icon}
      {children}
    </button>
  )
})
