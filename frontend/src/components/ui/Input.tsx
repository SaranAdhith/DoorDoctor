import { forwardRef, useState, type InputHTMLAttributes, type ReactNode } from 'react'
import { Eye, EyeOff } from 'lucide-react'

import { cn } from '../../lib/cn'
import { Field, controlClasses, type FieldProps } from './Field'

type NativeProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'required'>

export interface InputProps extends NativeProps, Omit<FieldProps, 'children'> {
  /** Rendered inside the control on the left. */
  leadingIcon?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, required, hideLabel, className, labelAction, leadingIcon, type = 'text', ...rest },
  ref,
) {
  // A password field owns a reveal toggle; the type it renders is derived, not passed.
  const isPassword = type === 'password'
  const [revealed, setRevealed] = useState(false)
  const renderedType = isPassword && revealed ? 'text' : type

  return (
    <Field
      label={label}
      hint={hint}
      error={error}
      required={required}
      hideLabel={hideLabel}
      className={className}
      labelAction={labelAction}
    >
      {({ id, describedBy, invalid }) => (
        <div className="relative">
          {leadingIcon && (
            <span
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-text-muted"
              aria-hidden="true"
            >
              {leadingIcon}
            </span>
          )}
          <input
            ref={ref}
            id={id}
            type={renderedType}
            required={required}
            aria-invalid={invalid || undefined}
            aria-describedby={describedBy}
            className={cn(controlClasses(invalid), Boolean(leadingIcon) && 'pl-10', isPassword && 'pr-12')}
            {...rest}
          />
          {isPassword && (
            <button
              type="button"
              onClick={() => setRevealed((current) => !current)}
              className="absolute right-1 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-md text-text-muted hover:text-text-primary"
              aria-label={revealed ? 'Hide password' : 'Show password'}
              aria-pressed={revealed}
            >
              {revealed ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          )}
        </div>
      )}
    </Field>
  )
})
