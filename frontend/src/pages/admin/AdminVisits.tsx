import { useState } from 'react'

import { ApiError } from '../../api/client'
import { adminApi } from '../../api/admin'
import { patientsApi } from '../../api/patients'
import { visitsApi } from '../../api/visits'
import { VisitStatusBadge } from '../../components/common/Badge'
import { Card, EmptyState } from '../../components/common/Card'
import { ErrorBanner } from '../../components/common/ErrorBanner'
import { LoadingScreen } from '../../components/common/Loading'
import { useToast } from '../../components/common/Toast'
import { ScheduleVisitForm } from '../../components/forms/ScheduleVisitForm'
import { useAsync } from '../../hooks/useAsync'
import { formatDate, formatTime } from '../../lib/format'

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
  if (data.error) return <ErrorBanner message={data.error} onRetry={() => void data.reload()} />
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
        <h1 className="text-2xl font-bold text-navy-800">Visits</h1>
        <p className="mt-1 text-sm text-slate-500">Schedule visits and assign nurses.</p>
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
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
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
                      <td className="py-2.5 pr-4 text-slate-700">{formatDate(visit.scheduled_at)}</td>
                      <td className="py-2.5 pr-4 tabular-nums text-slate-700">
                        {formatTime(visit.scheduled_at)}
                      </td>
                      <td className="py-2.5 pr-4 font-medium text-navy-800">{visit.patient?.name ?? '--'}</td>
                      <td className="py-2.5 pr-4 text-slate-700">{visit.nurse?.name ?? 'Unassigned'}</td>
                      <td className="py-2.5 pr-4">
                        <VisitStatusBadge status={visit.status} />
                      </td>
                      <td className="py-2.5">
                        <label className="sr-only" htmlFor={`assign-${visit.id}`}>
                          Assign nurse for visit {visit.id}
                        </label>
                        <select
                          id={`assign-${visit.id}`}
                          className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs disabled:bg-slate-50 disabled:text-slate-400"
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
