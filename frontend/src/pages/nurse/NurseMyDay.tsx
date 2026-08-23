import { AlertTriangle, CalendarCheck, LogIn, LogOut, MapPin } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { nurseOpsApi } from '../../api/trust'
import { LocationBadge } from '../../components/trust'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingScreen,
  StatTile,
  useToast,
  VisitStatusBadge,
} from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import { formatDateTime, formatTime } from '../../lib/format'
import type { NurseDay, WorklistVisit } from '../../types'

/**
 * The nurse's day (§4.16).
 *
 * **Unfinished work from an earlier day is at the top**, in its own block, with
 * the day it was scheduled for. A chronological list buries a visit left open
 * on Tuesday under Wednesday's work, where it stays forever.
 *
 * The shift control asks the browser for a position and hands it straight to
 * the server, which classifies it. Nothing here decides what `verified` means.
 */

function useGeolocation() {
  return async (): Promise<{ lat?: number; lng?: number; accuracy_m?: number }> => {
    if (!('geolocation' in navigator)) return {}
    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (position) =>
          resolve({
            lat: position.coords.latitude,
            lng: position.coords.longitude,
            accuracy_m: position.coords.accuracy,
          }),
        // A refused or failed fix is not an error here: the server classifies a
        // missing position as `unavailable`, which is a true answer.
        () => resolve({}),
        { enableHighAccuracy: true, timeout: 8000 },
      )
    })
  }
}

function VisitRow({ visit }: { visit: WorklistVisit }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle py-3 last:border-0">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/nurse/visits/${visit.id}`}
            className="font-medium text-text-primary hover:underline"
          >
            {visit.patient_name}
          </Link>
          <VisitStatusBadge status={visit.status} />
          {visit.open_alerts > 0 && (
            <Badge tone="attention">
              <AlertTriangle aria-hidden className="mr-1 inline h-3.5 w-3.5" />
              {visit.open_alerts} open
            </Badge>
          )}
        </div>
        <p className="mt-0.5 flex items-center gap-1 text-small text-text-secondary">
          <MapPin aria-hidden className="h-3.5 w-3.5 text-text-muted" />
          {visit.address}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <span className="tnum text-small text-text-secondary">
          {visit.carried_over ? formatDateTime(visit.scheduled_at) : formatTime(visit.scheduled_at)}
        </span>
        <Link
          to={`/nurse/visits/${visit.id}`}
          className="text-small font-medium text-brand-700 hover:underline"
        >
          Open
        </Link>
      </div>
    </li>
  )
}

export function NurseMyDay() {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const locate = useGeolocation()
  const day = useAsync<NurseDay>(() => nurseOpsApi.myDay(), [])

  async function startShift() {
    setBusy(true)
    try {
      const position = await locate()
      const shift = await nurseOpsApi.startShift(position)
      toast.notify(
        shift.location_status === 'verified'
          ? 'Shift started at the hub.'
          : 'Shift started. Your location could not be confirmed.',
        shift.location_status === 'verified' ? 'success' : 'info',
      )
      await day.reload({ quiet: true })
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not start the shift.', 'error')
    } finally {
      setBusy(false)
    }
  }

  async function endShift() {
    setBusy(true)
    try {
      await nurseOpsApi.endShift()
      toast.notify('Shift closed.', 'success')
      await day.reload({ quiet: true })
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not close the shift.', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (day.loading) return <LoadingScreen label="Loading your day" />
  if (day.error) return <ErrorState message={day.error} onRetry={() => day.reload()} />
  const data = day.data
  if (!data) return null

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-h1 font-semibold text-text-primary">My day</h1>
          <p className="text-small text-text-secondary">
            {data.zone ? `${data.zone} · ` : ''}
            {data.counts.remaining} visit{data.counts.remaining === 1 ? '' : 's'} left
          </p>
        </div>
        {data.shift?.is_open ? (
          <Button variant="subtle" onClick={endShift} disabled={busy}>
            <LogOut aria-hidden className="mr-1 h-4 w-4" />
            End shift
          </Button>
        ) : (
          <Button onClick={startShift} disabled={busy}>
            <LogIn aria-hidden className="mr-1 h-4 w-4" />
            Start shift at the hub
          </Button>
        )}
      </header>

      {data.shift && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-small text-text-secondary">
              Shift started {formatDateTime(data.shift.started_at)}
              {data.shift.zone && ` at the ${data.shift.zone} hub`}
            </p>
            <LocationBadge
              status={data.shift.location_status}
              distanceM={data.shift.location_distance_m}
              detail={data.shift.location_detail}
            />
          </div>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile label="Visits today" value={String(data.counts.total)} />
        <StatTile label="Completed" value={String(data.counts.completed)} tone="good" />
        <StatTile
          label="Carried over"
          value={String(data.counts.carried_over)}
          tone={data.counts.carried_over > 0 ? 'watch' : undefined}
        />
      </div>

      {data.carried_over.length > 0 && (
        <Card
          title="Still open from before today"
          description="Finish these first — they were scheduled for an earlier day."
        >
          <ul>
            {data.carried_over.map((visit) => (
              <VisitRow key={visit.id} visit={visit} />
            ))}
          </ul>
        </Card>
      )}

      <Card title="Today">
        {data.visits.length === 0 ? (
          <EmptyState
            icon={<CalendarCheck aria-hidden />}
            title="Nothing scheduled today"
            description="Your next visits will appear here."
          />
        ) : (
          <ul>
            {data.visits.map((visit) => (
              <VisitRow key={visit.id} visit={visit} />
            ))}
          </ul>
        )}
      </Card>

      {data.tasks.length > 0 && (
        <Card title="Tasks assigned to you">
          <ul className="space-y-2">
            {data.tasks.map((task) => (
              <li key={task.id} className="flex items-center justify-between gap-3 text-small">
                <span className="text-text-primary">{task.title}</span>
                <Badge tone={task.overdue ? 'attention' : 'neutral'}>
                  {task.overdue ? 'Overdue' : `Due ${formatDateTime(task.due_at)}`}
                </Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
