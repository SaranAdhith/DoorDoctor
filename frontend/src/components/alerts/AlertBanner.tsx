import { Link } from 'react-router-dom'

import { formatRelative } from '../../lib/format'
import type { Alert } from '../../types'

const STYLES = {
  critical: {
    wrapper: 'border-critical-200 bg-critical-50',
    title: 'text-critical-700',
    body: 'text-critical-700/90',
    icon: 'bg-critical-600',
  },
  warning: {
    wrapper: 'border-warning-200 bg-warning-50',
    title: 'text-warning-700',
    body: 'text-warning-700/90',
    icon: 'bg-warning-500',
  },
  info: {
    wrapper: 'border-navy-200 bg-navy-50',
    title: 'text-navy-800',
    body: 'text-navy-700',
    icon: 'bg-navy-600',
  },
}

export function AlertBanner({ alert, to }: { alert: Alert; to: string }) {
  const styles = STYLES[alert.severity]

  return (
    <div className={`rounded-2xl border p-4 shadow-card sm:p-5 ${styles.wrapper}`} role="alert">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex gap-3">
          <span
            className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white ${styles.icon}`}
            aria-hidden="true"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
            </svg>
          </span>
          <div>
            <p className={`text-base font-bold ${styles.title}`}>
              {alert.severity === 'critical' ? 'Critical Alert' : 'Attention Required'}
            </p>
            <p className={`mt-1 text-sm ${styles.body}`}>{alert.message}</p>
            <p className="mt-1.5 text-xs text-slate-500">
              Detected {formatRelative(alert.created_at)} · Monitoring alert - not a medical diagnosis.
            </p>
          </div>
        </div>

        <Link to={to} className="btn-primary w-full justify-center sm:w-auto">
          View alert
        </Link>
      </div>
    </div>
  )
}
