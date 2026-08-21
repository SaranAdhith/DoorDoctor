import { useId, useState, type ReactNode } from 'react'

import { cn } from '../../lib/cn'

export interface TooltipProps {
  /** Plain text — a tooltip is never the only place information lives. */
  content: string
  children: ReactNode
  side?: 'top' | 'bottom'
  className?: string
}

/**
 * Opens on hover and on focus, so it is reachable by keyboard. The trigger
 * keeps `aria-describedby`, meaning the content is announced rather than
 * depending on the visual popup.
 */
export function Tooltip({ content, children, side = 'top', className }: TooltipProps) {
  const id = useId()
  const [open, setOpen] = useState(false)

  return (
    <span
      className={cn('relative inline-flex', className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocusCapture={() => setOpen(true)}
      onBlurCapture={() => setOpen(false)}
    >
      <span aria-describedby={id}>{children}</span>
      {open && (
        <span
          id={id}
          role="tooltip"
          className={cn(
            'pointer-events-none absolute left-1/2 z-overlay w-max max-w-[16rem] -translate-x-1/2',
            'animate-fade-in rounded-md bg-navy-800 px-2.5 py-1.5 text-caption font-medium text-text-inverted shadow-raised',
            side === 'top' ? 'bottom-full mb-2' : 'top-full mt-2',
          )}
        >
          {content}
        </span>
      )}
    </span>
  )
}
