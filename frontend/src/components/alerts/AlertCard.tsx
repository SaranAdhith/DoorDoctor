import { METRIC_LABELS, formatDateTime, formatNumber } from '../../lib/format'
import type { Alert } from '../../types'
import { AlertStatusBadge, SeverityBadge } from '../common/Badge'

interface Props {
  alert: Alert
  patientName?: string | null
  children?: React.ReactNode
}

export function AlertCard({ alert, patientName, children }: Props) {
  const tone =
    alert.severity === 'critical'
      ? 'border-critical-200 bg-critical-50/40'
      : alert.severity === 'warning'
        ? 'border-warning-200 bg-warning-50/40'
        : 'border-slate-200 bg-white'

  return (
    <article className={`rounded-2xl border p-4 shadow-card sm:p-5 ${tone}`}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-navy-800">{alert.title}</h3>
          {patientName && <p className="text-sm text-slate-600">{patientName}</p>}
        </div>
        <div className="flex gap-2">
          <SeverityBadge severity={alert.severity} />
          <AlertStatusBadge status={alert.status} />
        </div>
      </header>

      <ul className="mt-3 space-y-1.5">
        {alert.breached_parameters.map((breach) => (
          <li
            key={breach.metric}
            className="flex flex-wrap items-baseline justify-between gap-x-3 rounded-xl bg-white/70 px-3 py-2 text-sm"
          >
            <span className="font-medium text-navy-800">{METRIC_LABELS[breach.metric] ?? breach.metric}</span>
            <span className="tabular-nums text-slate-600">
              <span className="font-semibold text-navy-800">
                {formatNumber(breach.value)}
                {breach.unit}
              </span>{' '}
              · {breach.direction} threshold {formatNumber(breach.threshold)}
              {breach.unit}
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-3 text-xs text-slate-500">Detected {formatDateTime(alert.created_at)}</p>

      {children && <div className="mt-4 flex flex-wrap gap-2">{children}</div>}
    </article>
  )
}
