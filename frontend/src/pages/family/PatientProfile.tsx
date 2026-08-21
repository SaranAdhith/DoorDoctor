import { useParams } from 'react-router-dom'

import { patientsApi } from '../../api/patients'
import { Card, EmptyState } from '../../components/common/Card'
import { VisitStatusBadge } from '../../components/common/Badge'
import { ErrorBanner } from '../../components/common/ErrorBanner'
import { LoadingScreen } from '../../components/common/Loading'
import { useAsync } from '../../hooks/useAsync'
import { METRIC_LABELS, METRIC_UNITS, formatDate, formatDateTime, formatNumber } from '../../lib/format'
import { bloodPressure } from '../../lib/vitals'
import type { VitalMetric } from '../../types'

export function PatientProfile() {
  const { patientId } = useParams()
  const id = Number(patientId)

  const dashboard = useAsync(() => patientsApi.dashboard(id), [id])

  if (dashboard.loading) return <LoadingScreen label="Loading patient" />
  if (dashboard.error) return <ErrorBanner message={dashboard.error} onRetry={() => void dashboard.reload()} />
  if (!dashboard.data) return <EmptyState title="Patient not found" />

  const { patient, thresholds, vitals_history: history } = dashboard.data

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-navy-800">{patient.name}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {patient.age} years · {patient.gender} · {patient.address}
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Profile">
          <dl className="space-y-2 text-sm">
            <Row label="Emergency contact" value={patient.emergency_contact ?? '--'} />
            <Row label="Status" value={patient.status} />
            <Row label="Enrolled" value={formatDate(patient.created_at)} />
          </dl>
        </Card>

        <Card title="Monitoring thresholds" className="lg:col-span-2">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="pb-2 pr-4 font-semibold">Metric</th>
                  <th className="pb-2 pr-4 font-semibold">Low</th>
                  <th className="pb-2 pr-4 font-semibold">High</th>
                  <th className="pb-2 font-semibold">Unit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {thresholds.map((threshold) => (
                  <tr key={threshold.metric}>
                    <td className="py-2 pr-4 font-medium text-navy-800">
                      {METRIC_LABELS[threshold.metric as VitalMetric] ?? threshold.metric}
                    </td>
                    <td className="py-2 pr-4 tabular-nums text-slate-600">{threshold.low_threshold ?? '--'}</td>
                    <td className="py-2 pr-4 tabular-nums text-slate-600">{threshold.high_threshold ?? '--'}</td>
                    <td className="py-2 text-slate-500">{METRIC_UNITS[threshold.metric as VitalMetric]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Threshold values are demo configuration, not clinical standards.
          </p>
        </Card>
      </div>

      <Card title="Reading history">
        {history.length === 0 ? (
          <EmptyState title="No readings recorded yet" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="pb-2 pr-4 font-semibold">Recorded</th>
                  <th className="pb-2 pr-4 font-semibold">BP</th>
                  <th className="pb-2 pr-4 font-semibold">HR</th>
                  <th className="pb-2 pr-4 font-semibold">SpO2</th>
                  <th className="pb-2 pr-4 font-semibold">Glucose</th>
                  <th className="pb-2 pr-4 font-semibold">Temp</th>
                  <th className="pb-2 font-semibold">Flag</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {[...history].reverse().map((entry) => (
                  <tr key={entry.id}>
                    <td className="py-2 pr-4 text-slate-600">{formatDateTime(entry.recorded_at)}</td>
                    <td className="py-2 pr-4 font-medium tabular-nums text-navy-800">{bloodPressure(entry)}</td>
                    <td className="py-2 pr-4 tabular-nums text-slate-600">{formatNumber(entry.heart_rate)}</td>
                    <td className="py-2 pr-4 tabular-nums text-slate-600">{formatNumber(entry.spo2)}</td>
                    <td className="py-2 pr-4 tabular-nums text-slate-600">{formatNumber(entry.blood_glucose)}</td>
                    <td className="py-2 pr-4 tabular-nums text-slate-600">{formatNumber(entry.temperature)}</td>
                    <td className="py-2">
                      {entry.threshold_breached ? (
                        <span className="rounded-full bg-critical-50 px-2 py-0.5 text-xs font-semibold text-critical-700">
                          Out of range
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">In range</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Visits">
        {dashboard.data.recent_visits.length === 0 ? (
          <EmptyState title="No completed visits yet" />
        ) : (
          <ul className="divide-y divide-slate-100">
            {dashboard.data.recent_visits.map((visit) => (
              <li key={visit.id} className="flex items-center justify-between gap-3 py-3">
                <div>
                  <p className="text-sm font-medium text-navy-800">{formatDateTime(visit.scheduled_at)}</p>
                  <p className="text-xs text-slate-500">{visit.nurse_name ?? 'Nurse'}</p>
                </div>
                <VisitStatusBadge status={visit.status} />
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-navy-800">{value}</dd>
    </div>
  )
}
