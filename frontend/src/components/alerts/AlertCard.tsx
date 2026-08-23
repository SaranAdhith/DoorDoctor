import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'
import { breachContext, breachLabel, breachValue } from '../../lib/breach'
import { formatDateTime } from '../../lib/format'
import type { Alert } from '../../types'
import { AlertStatusBadge, SeverityBadge } from '../ui'

interface Props {
  alert: Alert
  patientName?: string | null
  children?: ReactNode
}

const TONES = {
  critical: 'border-status-critical-border bg-status-critical-bg/40',
  warning: 'border-status-watch-border bg-status-watch-bg/40',
  info: 'border-border-subtle bg-surface-raised',
} as const

export function AlertCard({ alert, patientName, children }: Props) {
  return (
    <article className={cn('rounded-2xl border p-4 shadow-card sm:p-5', TONES[alert.severity])}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-body font-semibold text-text-primary">{alert.title}</h3>
          {patientName && <p className="text-small text-text-secondary">{patientName}</p>}
        </div>
        <div className="flex gap-2">
          <SeverityBadge severity={alert.severity} />
          <AlertStatusBadge status={alert.status} />
        </div>
      </header>

      <ul className="mt-3 space-y-1.5">
        {alert.breached_parameters.map((breach, index) => (
          <li
            key={`${breach.metric}-${index}`}
            className="flex flex-wrap items-baseline justify-between gap-x-3 rounded-xl bg-surface-raised/70 px-3 py-2 text-small"
          >
            <span className="font-medium text-text-primary">{breachLabel(breach)}</span>
            <span className="tnum text-text-secondary">
              <span className="font-semibold text-text-primary">{breachValue(breach)}</span>
              {breachContext(breach) && <> · {breachContext(breach)}</>}
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-3 text-caption text-text-muted">Detected {formatDateTime(alert.created_at)}</p>

      {children && <div className="mt-4 flex flex-wrap gap-2">{children}</div>}
    </article>
  )
}
