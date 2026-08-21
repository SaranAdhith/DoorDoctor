import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'

export type StatTone = 'default' | 'good' | 'watch' | 'attention' | 'critical'

const VALUE_TONES: Record<StatTone, string> = {
  default: 'text-text-primary',
  good: 'text-status-good',
  watch: 'text-status-watch',
  attention: 'text-status-attention',
  critical: 'text-status-critical',
}

export interface StatTileProps {
  label: string
  value: ReactNode
  hint?: ReactNode
  tone?: StatTone
  icon?: ReactNode
  className?: string
}

/** One number with its meaning attached. Never a bare figure. */
export function StatTile({ label, value, hint, tone = 'default', icon, className }: StatTileProps) {
  return (
    <article
      className={cn(
        'rounded-2xl border border-border-subtle bg-surface-raised p-5 shadow-card',
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-caption font-semibold uppercase tracking-wide text-text-secondary">
          {label}
        </h3>
        {icon && (
          <span className="shrink-0 text-text-muted" aria-hidden="true">
            {icon}
          </span>
        )}
      </div>
      <p className={cn('tnum mt-2 text-display font-bold', VALUE_TONES[tone])}>{value}</p>
      {hint && <p className="mt-1 text-caption text-text-muted">{hint}</p>}
    </article>
  )
}
