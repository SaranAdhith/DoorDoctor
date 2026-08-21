import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from 'react'
import { Check } from 'lucide-react'

import { cn } from '../../lib/cn'

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'id'> {
  label: ReactNode
  hint?: string
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { label, hint, className, disabled, ...rest },
  ref,
) {
  const id = useId()
  const hintId = `${id}-hint`

  return (
    <div className={cn('flex gap-3', className)}>
      {/*
        The native input stays in the DOM and keeps focus and keyboard
        behaviour; it is made transparent and stretched over the drawn box so
        the visible control and the real control are the same hit target.
      */}
      <span className="relative mt-0.5 inline-flex h-5 w-5 shrink-0">
        <input
          ref={ref}
          id={id}
          type="checkbox"
          disabled={disabled}
          aria-describedby={hint ? hintId : undefined}
          className="peer absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
          {...rest}
        />
        <span
          className={cn(
            'pointer-events-none flex h-5 w-5 items-center justify-center rounded-sm border transition-colors',
            'border-border-strong bg-surface-raised',
            'peer-checked:border-brand-500 peer-checked:bg-brand-500 peer-checked:text-text-inverted',
            'peer-focus-visible:ring-2 peer-focus-visible:ring-brand-500 peer-focus-visible:ring-offset-2',
            'peer-disabled:bg-surface-sunken peer-disabled:opacity-60',
          )}
          aria-hidden="true"
        >
          <Check className="h-3.5 w-3.5 opacity-0 peer-checked:opacity-100" strokeWidth={3} />
        </span>
      </span>

      <span className="min-w-0">
        <label
          htmlFor={id}
          className={cn(
            'block cursor-pointer text-body text-text-primary',
            disabled && 'cursor-not-allowed text-text-muted',
          )}
        >
          {label}
        </label>
        {hint && (
          <span id={hintId} className="mt-0.5 block text-caption text-text-muted">
            {hint}
          </span>
        )}
      </span>
    </div>
  )
})
