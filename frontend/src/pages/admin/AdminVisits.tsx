import { useState } from 'react'

import { ApiError } from '../../api/client'
import { adminApi } from '../../api/admin'
import { patientsApi } from '../../api/patients'
import { visitsApi } from '../../api/visits'
import { ScheduleVisitForm } from '../../components/forms/ScheduleVisitForm'
import { useAsync } from '../../hooks/useAsync'
import { formatDate, formatTime } from '../../lib/format'
import { Card, EmptyState, ErrorState, LoadingScreen, VisitStatusBadge, useToast } from '../../components/ui'

export function AdminVisits() {
  const { notify } = useToast()
  const [submitting, setSubmitting] = useState(false)

  const data = useAsync(async () => {
    const [visits, patients, nurses] = await Promise.all([
      visitsApi.list(),
      patientsApi.list(),
      adminApi.nurses(),
    ])
    return { visits, patients, nurses }
  }, [])

  if (data.loading) return <LoadingScreen label="Loading visits" />
  if (data.error) return <ErrorState message={data.error} onRetry={() => void data.reload()} />
  if (!data.data) return null

  const { visits, patients, nurses } = data.data

  async function schedule(payload: { patient_id: number; nurse_id: number | null; scheduled_at: string }) {
    setSubmitting(true)
    try {
      await visitsApi.create(payload)
      notify('Visit scheduled. It is now on the nurse worklist.', 'success')
      await data.reload({ quiet: true })
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'Could not schedule the visit.', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  async function assign(visitId: number, nurseId: number) {
    try {
      await visitsApi.assign(visitId, nurseId)
      notify('Nurse assigned.', 'success')
      await data.reload({ quiet: true })
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'Could not assign the nurse.', 'error')
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 font-bold text-text-primary">Visits</h1>
        <p className="mt-1 text-small text-text-secondary">Schedule visits and assign nurses.</p>
      </div>

      <Card title="Schedule a visit">
        <ScheduleVisitForm
          patients={patients}
          nurses={nurses}
          submitting={submitting}
          onSubmit={schedule}
        />
      </Card>

      <Card title="All visits">
        {visits.length === 0 ? (
          <EmptyState title="No visits yet" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-small">
              <thead>
                <tr className="text-left text-caption uppercase tracking-wide text-text-secondary">
                  <th className="pb-2 pr-4 font-semibold">Date</th>
                  <th className="pb-2 pr-4 font-semibold">Time</th>
                  <th className="pb-2 pr-4 font-semibold">Patient</th>
                  <th className="pb-2 pr-4 font-semibold">Nurse</th>
                  <th className="pb-2 pr-4 font-semibold">Status</th>
                  <th className="pb-2 font-semibold">Assign</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visits.map((visit) => {
                  const locked = visit.status === 'completed' || visit.status === 'cancelled'
                  return (
                    <tr key={visit.id}>
                      <td className="py-2.5 pr-4 text-text-primary">{formatDate(visit.scheduled_at)}</td>
                      <td className="py-2.5 pr-4 tnum text-text-primary">
                        {formatTime(visit.scheduled_at)}
                      </td>
                      <td className="py-2.5 pr-4 font-medium text-text-primary">{visit.patient?.name ?? '--'}</td>
                      <td className="py-2.5 pr-4 text-text-primary">{visit.nurse?.name ?? 'Unassigned'}</td>
                      <td className="py-2.5 pr-4">
                        <VisitStatusBadge status={visit.status} />
                      </td>
                      <td className="py-2.5">
                        <label className="sr-only" htmlFor={`assign-${visit.id}`}>
                          Assign nurse for visit {visit.id}
                        </label>
                        <select
                          id={`assign-${visit.id}`}
                          className="rounded-lg border border-border-strong bg-surface-raised px-2 py-1.5 text-caption disabled:bg-surface-sunken disabled:text-text-muted"
                          value={visit.nurse_id ?? ''}
                          disabled={locked}
                          onChange={(event) => void assign(visit.id, Number(event.target.value))}
                        >
                          <option value="" disabled>
                            Select
                          </option>
                          {nurses.map((nurse) => (
                            <option key={nurse.id} value={nurse.id}>
                              {nurse.name}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
