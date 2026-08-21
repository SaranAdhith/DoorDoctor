import { forwardRef, type TextareaHTMLAttributes } from 'react'

import { cn } from '../../lib/cn'
import { Field, controlClasses, type FieldProps } from './Field'

type NativeProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id' | 'required'>

export interface TextareaProps extends NativeProps, Omit<FieldProps, 'children'> {}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, required, hideLabel, className, labelAction, rows = 4, ...rest },
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
        <textarea
          ref={ref}
          id={id}
          rows={rows}
          required={required}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          className={cn(controlClasses(invalid), 'resize-y leading-6')}
          {...rest}
        />
      )}
    </Field>
  )
})
