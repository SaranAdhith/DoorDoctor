import { useId, type ReactNode } from 'react'

import { cn } from '../../lib/cn'

export interface FieldProps {
  label: string
  /** Helper text shown under the control while it is valid. */
  hint?: string
  error?: string | null
  required?: boolean
  /** Visually hides the label but keeps it for screen readers. */
  hideLabel?: boolean
  className?: string
  /** Rendered to the right of the label — e.g. a "Forgot password?" link. */
  labelAction?: ReactNode
  children: (ids: { id: string; describedBy: string | undefined; invalid: boolean }) => ReactNode
}

/**
 * Wraps a control with its label, hint and error, and wires the ARIA between
 * them. Every form control in the product goes through this so a labelled,
 * described, correctly-invalid input is the default rather than an effort.
 */
export function Field({
  label,
  hint,
  error,
  required = false,
  hideLabel = false,
  className,
  labelAction,
  children,
}: FieldProps) {
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const invalid = Boolean(error)
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ') || undefined

  return (
    <div className={cn('w-full', className)}>
      <div className={cn('flex items-baseline justify-between gap-3', hideLabel && 'sr-only')}>
        <label htmlFor={id} className="mb-1.5 block text-small font-medium text-text-primary">
          {label}
          {required && (
            <span className="ml-1 text-critical-600" aria-hidden="true">
              *
            </span>
          )}
        </label>
        {labelAction}
      </div>

      {children({ id, describedBy, invalid })}

      {hint && !error && (
        <p id={hintId} className="mt-1.5 text-caption text-text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="mt-1.5 text-small font-medium text-critical-600">
          {error}
        </p>
      )}
    </div>
  )
}

/** Shared look for every text-like control, so an input and a select match. */
export const controlClasses = (invalid: boolean) =>
  cn(
    'w-full min-h-control rounded-xl border bg-surface-raised px-3.5 py-2.5 text-body text-text-primary',
    'placeholder:text-text-muted transition-colors',
    'disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-text-muted',
    invalid
      ? 'border-critical-500 focus:border-critical-600'
      : 'border-border-strong focus:border-brand-500',
  )
