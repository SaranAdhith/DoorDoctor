import { Link, type LinkProps } from 'react-router-dom'

import { cn } from '../../lib/cn'
import { buttonClasses, type ButtonSize, type ButtonVariant } from './Button'

export interface LinkButtonProps extends LinkProps {
  variant?: ButtonVariant
  size?: ButtonSize
  fullWidth?: boolean
}

/**
 * A router link that looks like a button.
 *
 * Kept separate from `Button` rather than adding a polymorphic `as` prop: a
 * navigation is an anchor and an action is a button, and that distinction
 * matters to assistive tech and to middle-click.
 */
export function LinkButton({
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  className,
  children,
  ...rest
}: LinkButtonProps) {
  return (
    <Link className={cn(buttonClasses({ variant, size, fullWidth }), className)} {...rest}>
      {children}
    </Link>
  )
}
