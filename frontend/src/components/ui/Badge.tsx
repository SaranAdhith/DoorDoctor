import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'
import { SEVERITY_LABELS, VISIT_STATUS_LABELS } from '../../lib/format'
import type { AlertSeverity, AlertStatus, VisitStatus } from '../../types'

/**
 * `good | watch | attention | critical` carry clinical meaning and map to the
 * status tokens. `neutral | info` are chrome and must never be used to
 * describe a reading.
 */
export type BadgeTone = 'neutral' | 'info' | 'good' | 'watch' | 'attention' | 'critical'

const TONES: Record<BadgeTone, string> = {
  neutral: 'bg-surface-sunken text-text-secondary ring-border-subtle',
  info: 'bg-navy-50 text-navy-700 ring-navy-200',
  good: 'bg-status-good-bg text-status-good ring-status-good-border',
  watch: 'bg-status-watch-bg text-status-watch ring-status-watch-border',
  attention: 'bg-status-attention-bg text-status-attention ring-status-attention-border',
  critical: 'bg-status-critical-bg text-status-critical ring-status-critical-border',
}

export interface BadgeProps {
  tone?: BadgeTone
  children: ReactNode
  /** Shows a leading dot — useful when the badge sits in a dense table. */
  dot?: boolean
  className?: string
}

export function Badge({ tone = 'neutral', dot = false, className, children }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-caption font-semibold ring-1 ring-inset',
        TONES[tone],
        className,
      )}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />}
      {children}
    </span>
  )
}

const VISIT_TONES: Record<VisitStatus, BadgeTone> = {
  scheduled: 'info',
  in_progress: 'watch',
  completed: 'good',
  missed: 'critical',
  cancelled: 'neutral',
}

export function VisitStatusBadge({ status }: { status: VisitStatus }) {
  return <Badge tone={VISIT_TONES[status]}>{VISIT_STATUS_LABELS[status]}</Badge>
}

const SEVERITY_TONES: Record<AlertSeverity, BadgeTone> = {
  info: 'info',
  warning: 'watch',
  critical: 'critical',
}

export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  return <Badge tone={SEVERITY_TONES[severity]}>{SEVERITY_LABELS[severity]}</Badge>
}

const ALERT_STATUS_TONES: Record<AlertStatus, BadgeTone> = {
  active: 'critical',
  acknowledged: 'watch',
  resolved: 'good',
}

const ALERT_STATUS_LABELS: Record<AlertStatus, string> = {
  active: 'Active',
  acknowledged: 'Acknowledged',
  resolved: 'Resolved',
}

export function AlertStatusBadge({ status }: { status: AlertStatus }) {
  return <Badge tone={ALERT_STATUS_TONES[status]}>{ALERT_STATUS_LABELS[status]}</Badge>
}
