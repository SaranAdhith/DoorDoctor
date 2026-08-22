import type { ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router-dom'

import { cn } from '../../lib/cn'
import { buttonClasses, type ButtonSize, type ButtonVariant } from './Button'

export interface LinkButtonProps extends LinkProps {
  variant?: ButtonVariant
  size?: ButtonSize
  fullWidth?: boolean
  /** Rendered before the label, mirroring `Button.icon`.
   *
   * The two carry the same prop so a row of actions does not have to know which
   * of them navigates — `buttonClasses` already supplies the gap. */
  icon?: ReactNode
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
  icon,
  className,
  children,
  ...rest
}: LinkButtonProps) {
  return (
    <Link className={cn(buttonClasses({ variant, size, fullWidth }), className)} {...rest}>
      {icon}
      {children}
    </Link>
  )
}
