import { MapPin } from 'lucide-react'

import { formatDate, formatTime, isToday } from '../../lib/format'
import type { Visit } from '../../types'
import { LinkButton, VisitStatusBadge } from '../ui'

interface Props {
  visit: Visit
  actionLabel: string
  to: string
  /** The nurse's own worklist already knows who the nurse is. */
  showNurse?: boolean
}

export function VisitCard({ visit, actionLabel, to, showNurse = true }: Props) {
  const patientName = visit.patient?.name ?? 'Patient'

  return (
    <article className="flex flex-col gap-4 rounded-2xl border border-border-subtle bg-surface-raised p-5 shadow-card sm:flex-row sm:items-center sm:justify-between">
      <div className="flex gap-4">
        <div className="flex min-w-[4.5rem] shrink-0 flex-col items-center justify-center rounded-xl bg-navy-800 px-2.5 py-2 text-text-inverted">
          <span className="tnum whitespace-nowrap text-small font-bold leading-tight">
            {formatTime(visit.scheduled_at)}
          </span>
          <span className="mt-0.5 whitespace-nowrap text-caption uppercase tracking-wide text-navy-100">
            {isToday(visit.scheduled_at) ? 'Today' : formatDate(visit.scheduled_at).slice(0, 6)}
          </span>
        </div>

        <div className="min-w-0">
          <h3 className="truncate text-body font-semibold text-text-primary">{patientName}</h3>
          {visit.patient?.address && (
            <p className="mt-0.5 flex items-center gap-1.5 truncate text-small text-text-secondary">
              <MapPin className="h-3.5 w-3.5 shrink-0 text-text-muted" aria-hidden="true" />
              {visit.patient.address}
            </p>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <VisitStatusBadge status={visit.status} />
            {showNurse && visit.nurse?.name && (
              <span className="text-caption text-text-secondary">Nurse: {visit.nurse.name}</span>
            )}
          </div>
        </div>
      </div>

      <LinkButton to={to} className="w-full justify-center sm:w-auto">
        {actionLabel}
      </LinkButton>
    </article>
  )
}
