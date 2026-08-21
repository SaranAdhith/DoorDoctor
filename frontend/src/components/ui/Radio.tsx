import { useId, type ReactNode } from 'react'

import { cn } from '../../lib/cn'

export interface RadioOption<T extends string> {
  value: T
  label: ReactNode
  hint?: string
  disabled?: boolean
}

export interface RadioGroupProps<T extends string> {
  legend: string
  name: string
  value: T | null
  options: ReadonlyArray<RadioOption<T>>
  onChange: (value: T) => void
  /** Visually hides the legend but keeps it announced. */
  hideLegend?: boolean
  className?: string
}

/**
 * A radio group is one control, not N controls, so it owns the fieldset and
 * legend. Arrow-key navigation comes free from the native radio roving
 * tabindex once the inputs share a `name`.
 */
export function RadioGroup<T extends string>({
  legend,
  name,
  value,
  options,
  onChange,
  hideLegend = false,
  className,
}: RadioGroupProps<T>) {
  const groupId = useId()

  return (
    <fieldset className={cn('w-full', className)}>
      <legend
        className={cn(
          'mb-2 text-small font-medium text-text-primary',
          hideLegend && 'sr-only',
        )}
      >
        {legend}
      </legend>

      <div className="space-y-2">
        {options.map((option) => {
          const id = `${groupId}-${option.value}`
          const hintId = `${id}-hint`
          return (
            <div key={option.value} className="flex gap-3">
              <span className="relative mt-0.5 inline-flex h-5 w-5 shrink-0">
                <input
                  id={id}
                  type="radio"
                  name={name}
                  value={option.value}
                  checked={value === option.value}
                  disabled={option.disabled}
                  onChange={() => onChange(option.value)}
                  aria-describedby={option.hint ? hintId : undefined}
                  className="peer absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
                />
                <span
                  className={cn(
                    'pointer-events-none flex h-5 w-5 items-center justify-center rounded-full border transition-colors',
                    'border-border-strong bg-surface-raised',
                    'peer-checked:border-brand-500 peer-checked:border-[6px]',
                    'peer-focus-visible:ring-2 peer-focus-visible:ring-brand-500 peer-focus-visible:ring-offset-2',
                    'peer-disabled:bg-surface-sunken peer-disabled:opacity-60',
                  )}
                  aria-hidden="true"
                />
              </span>

              <span className="min-w-0">
                <label
                  htmlFor={id}
                  className={cn(
                    'block cursor-pointer text-body text-text-primary',
                    option.disabled && 'cursor-not-allowed text-text-muted',
                  )}
                >
                  {option.label}
                </label>
                {option.hint && (
                  <span id={hintId} className="mt-0.5 block text-caption text-text-muted">
                    {option.hint}
                  </span>
                )}
              </span>
            </div>
          )
        })}
      </div>
    </fieldset>
  )
}
