import { forwardRef, type SelectHTMLAttributes } from 'react'
import { ChevronDown } from 'lucide-react'

import { cn } from '../../lib/cn'
import { Field, controlClasses, type FieldProps } from './Field'

type NativeProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id' | 'required'>

export interface SelectProps extends NativeProps, Omit<FieldProps, 'children'> {}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, required, hideLabel, className, labelAction, children, ...rest },
  ref,
) {
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
          <select
            ref={ref}
            id={id}
            required={required}
            aria-invalid={invalid || undefined}
            aria-describedby={describedBy}
            className={cn(controlClasses(invalid), 'appearance-none pr-10')}
            {...rest}
          >
            {children}
          </select>
          <ChevronDown
            className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted"
            aria-hidden="true"
          />
        </div>
      )}
    </Field>
  )
})
