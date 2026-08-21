import type { AlertSeverity, AlertStatus, VisitStatus } from '../../types'
import { SEVERITY_LABELS, VISIT_STATUS_LABELS } from '../../lib/format'

type Tone = 'neutral' | 'success' | 'warning' | 'critical' | 'info'

const TONE_CLASSES: Record<Tone, string> = {
  neutral: 'bg-slate-100 text-slate-700 ring-slate-200',
  success: 'bg-brand-50 text-brand-700 ring-brand-200',
  warning: 'bg-warning-50 text-warning-700 ring-warning-200',
  critical: 'bg-critical-50 text-critical-700 ring-critical-200',
  info: 'bg-navy-50 text-navy-700 ring-navy-200',
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  )
}

const VISIT_TONES: Record<VisitStatus, Tone> = {
  scheduled: 'info',
  in_progress: 'warning',
  completed: 'success',
  missed: 'critical',
  cancelled: 'neutral',
}

export function VisitStatusBadge({ status }: { status: VisitStatus }) {
  return <Badge tone={VISIT_TONES[status]}>{VISIT_STATUS_LABELS[status]}</Badge>
}

const SEVERITY_TONES: Record<AlertSeverity, Tone> = {
  info: 'info',
  warning: 'warning',
  critical: 'critical',
}

export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  return <Badge tone={SEVERITY_TONES[severity]}>{SEVERITY_LABELS[severity]}</Badge>
}

const ALERT_STATUS_TONES: Record<AlertStatus, Tone> = {
  active: 'critical',
  acknowledged: 'warning',
  resolved: 'success',
}

export function AlertStatusBadge({ status }: { status: AlertStatus }) {
  return (
    <Badge tone={ALERT_STATUS_TONES[status]}>{status.charAt(0).toUpperCase() + status.slice(1)}</Badge>
  )
}
