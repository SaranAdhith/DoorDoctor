import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'

export interface EmptyStateProps {
  title: string
  description?: ReactNode
  /** A primary action that resolves the emptiness — "Schedule a visit". */
  action?: ReactNode
  icon?: ReactNode
  className?: string
}

export function EmptyState({ title, description, action, icon, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-dashed border-border-subtle bg-surface/60 px-4 py-10 text-center',
        className,
      )}
    >
      {icon && (
        <span className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-surface-sunken text-text-muted">
          {icon}
        </span>
      )}
      <p className="text-body font-semibold text-text-primary">{title}</p>
      {description && (
        <p className="mx-auto mt-1 max-w-md text-small text-text-secondary">{description}</p>
      )}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  )
}
