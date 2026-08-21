import { useId, type ReactNode } from 'react'

import { cn } from '../../lib/cn'

export interface SwitchProps {
  label: ReactNode
  hint?: string
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  className?: string
}

/**
 * A switch takes effect immediately, unlike a checkbox which is submitted.
 * Built on `role="switch"` rather than a styled checkbox so assistive tech
 * announces "on/off" rather than "checked".
 */
export function Switch({ label, hint, checked, onChange, disabled = false, className }: SwitchProps) {
  const id = useId()
  const hintId = `${id}-hint`

  return (
    <div className={cn('flex items-start justify-between gap-4', className)}>
      <span className="min-w-0">
        <label htmlFor={id} className="block text-body font-medium text-text-primary">
          {label}
        </label>
        {hint && (
          <span id={hintId} className="mt-0.5 block text-caption text-text-muted">
            {hint}
          </span>
        )}
      </span>

      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-describedby={hint ? hintId : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors',
          'disabled:cursor-not-allowed disabled:opacity-50',
          checked ? 'bg-brand-500' : 'bg-border-strong',
        )}
      >
        <span
          className={cn(
            'inline-block h-5 w-5 transform rounded-full bg-surface-raised shadow-card transition-transform',
            checked ? 'translate-x-[1.375rem]' : 'translate-x-0.5',
          )}
          aria-hidden="true"
        />
      </button>
    </div>
  )
}
