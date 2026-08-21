import { AlertTriangle } from 'lucide-react'

import { cn } from '../../lib/cn'
import { formatRelative } from '../../lib/format'
import type { Alert } from '../../types'
import { LinkButton } from '../ui'

const STYLES = {
  critical: {
    wrapper: 'border-status-critical-border bg-status-critical-bg',
    title: 'text-status-critical',
    icon: 'bg-critical-600',
  },
  warning: {
    wrapper: 'border-status-watch-border bg-status-watch-bg',
    title: 'text-status-watch',
    icon: 'bg-warning-500',
  },
  info: {
    wrapper: 'border-navy-200 bg-navy-50',
    title: 'text-text-primary',
    icon: 'bg-navy-600',
  },
} as const

export function AlertBanner({ alert, to }: { alert: Alert; to: string }) {
  const styles = STYLES[alert.severity]

  return (
    <div className={cn('rounded-2xl border p-4 shadow-card sm:p-5', styles.wrapper)} role="alert">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex gap-3">
          <span
            className={cn(
              'mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-text-inverted',
              styles.icon,
            )}
            aria-hidden="true"
          >
            <AlertTriangle className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <p className={cn('text-body font-bold', styles.title)}>
              {alert.severity === 'critical' ? 'Reading well outside range' : 'Reading outside range'}
            </p>
            <p className="mt-1 text-small text-text-secondary">{alert.message}</p>
            <p className="mt-1.5 text-caption text-text-muted">
              Detected {formatRelative(alert.created_at)} · Monitoring alert, not a medical diagnosis.
            </p>
          </div>
        </div>

        <LinkButton to={to} className="w-full sm:w-auto">
          View alert
        </LinkButton>
      </div>
    </div>
  )
}
