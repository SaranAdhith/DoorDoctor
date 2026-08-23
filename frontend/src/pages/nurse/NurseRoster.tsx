import { CalendarDays } from 'lucide-react'
import { Link } from 'react-router-dom'

import { nurseOpsApi } from '../../api/trust'
import {
  Card,
  EmptyState,
  ErrorState,
  LoadingScreen,
  VisitStatusBadge,
} from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import { formatDate, formatTime } from '../../lib/format'
import type { NurseRoster as NurseRosterData } from '../../types'

/**
 * The week ahead (§4.16).
 *
 * Grouped by day rather than listed, because the question a nurse asks a roster
 * is "what does Thursday look like", not "what is the 47th visit".
 * Empty days are shown as empty rather than skipped — a gap in a list of dates
 * reads as missing data, and a day with no visits is information.
 */
export function NurseRoster() {
  const roster = useAsync<NurseRosterData>(() => nurseOpsApi.roster(7), [])

  if (roster.loading) return <LoadingScreen label="Loading your week" />
  if (roster.error) return <ErrorState message={roster.error} onRetry={() => roster.reload()} />
  const data = roster.data
  if (!data) return null

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-h1 font-semibold text-text-primary">My week</h1>
        <p className="text-small text-text-secondary">
          {formatDate(data.from)} to {formatDate(data.to)} · {data.total} visit
          {data.total === 1 ? '' : 's'}
        </p>
      </header>

      {data.total === 0 && (
        <EmptyState
          icon={<CalendarDays aria-hidden />}
          title="Nothing scheduled this week"
          description="Visits appear here as they are assigned to you."
        />
      )}

      <div className="space-y-4">
        {data.days.map((day) => (
          <Card key={day.date} title={formatDate(day.date)}>
            {day.visits.length === 0 ? (
              <p className="text-small text-text-muted">No visits.</p>
            ) : (
              <ul className="divide-y divide-border-subtle">
                {day.visits.map((visit) => (
                  <li
                    key={visit.id}
                    className="flex flex-wrap items-center justify-between gap-3 py-2"
                  >
                    <div className="min-w-0">
                      <Link
                        to={`/nurse/visits/${visit.id}`}
                        className="font-medium text-text-primary hover:underline"
                      >
                        {visit.patient_name}
                      </Link>
                      <p className="text-small text-text-secondary">{visit.address}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <VisitStatusBadge status={visit.status} />
                      <span className="tnum text-small text-text-secondary">
                        {formatTime(visit.scheduled_at)}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}
