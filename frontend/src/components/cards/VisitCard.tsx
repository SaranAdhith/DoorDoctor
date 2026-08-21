import { Link } from 'react-router-dom'

import { formatDate, formatTime, isToday } from '../../lib/format'
import type { Visit } from '../../types'
import { VisitStatusBadge } from '../common/Badge'

interface Props {
  visit: Visit
  actionLabel: string
  to: string
}

export function VisitCard({ visit, actionLabel, to }: Props) {
  const patientName = visit.patient?.name ?? 'Patient'

  return (
    <article className="card flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex gap-4">
        <div className="flex min-w-[4.5rem] shrink-0 flex-col items-center justify-center rounded-xl bg-navy-800 px-2.5 py-2 text-white">
          <span className="whitespace-nowrap text-sm font-bold leading-tight">
            {formatTime(visit.scheduled_at)}
          </span>
          <span className="mt-0.5 whitespace-nowrap text-[10px] uppercase tracking-wide text-navy-100">
            {isToday(visit.scheduled_at) ? 'Today' : formatDate(visit.scheduled_at).slice(0, 6)}
          </span>
        </div>

        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-navy-800">{patientName}</h3>
          {visit.patient?.address && (
            <p className="mt-0.5 truncate text-sm text-slate-500">{visit.patient.address}</p>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <VisitStatusBadge status={visit.status} />
            {visit.nurse?.name && (
              <span className="text-xs text-slate-500">Nurse: {visit.nurse.name}</span>
            )}
          </div>
        </div>
      </div>

      <Link to={to} className="btn-primary w-full justify-center sm:w-auto">
        {actionLabel}
      </Link>
    </article>
  )
}
