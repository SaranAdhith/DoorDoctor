import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'

export interface CardProps {
  title?: ReactNode
  /** Small print under the title. */
  description?: ReactNode
  /** Right-aligned in the header — a link, a filter, a button. */
  action?: ReactNode
  children: ReactNode
  className?: string
  /** Removes the body padding, for a card whose child is a full-bleed table. */
  flush?: boolean
  as?: 'section' | 'article' | 'div'
}

export function Card({
  title,
  description,
  action,
  children,
  className,
  flush = false,
  as: Tag = 'section',
}: CardProps) {
  return (
    <Tag
      className={cn(
        'rounded-2xl border border-border-subtle bg-surface-raised shadow-card',
        flush ? 'overflow-hidden' : 'p-5',
        className,
      )}
    >
      {(title || action) && (
        <header
          className={cn(
            // Wraps rather than stacks: a short action link stays on the title
            // row when it fits, and a wide one (tabs, filters) drops below it.
            'flex flex-wrap items-start justify-between gap-x-3 gap-y-2',
            flush ? 'border-b border-border-subtle px-5 py-4' : 'mb-4',
          )}
        >
          <div className="min-w-0">
            {title && (
              <h2 className="text-caption font-semibold uppercase tracking-wide text-text-secondary">
                {title}
              </h2>
            )}
            {description && <p className="mt-1 text-small text-text-muted">{description}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </Tag>
  )
}
