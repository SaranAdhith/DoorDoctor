import { useState } from 'react'
import { Link } from 'react-router-dom'

import { patientsApi } from '../../api/patients'
import { useAuth } from '../../auth/AuthContext'
import { AlertBanner } from '../../components/alerts/AlertBanner'
import { AdherenceCard } from '../../components/cards/AdherenceCard'
import { VitalCard } from '../../components/cards/VitalCard'
import { VitalsTrendChart } from '../../components/charts/VitalsTrendChart'
import { Card, EmptyState } from '../../components/common/Card'
import { VisitStatusBadge } from '../../components/common/Badge'
import { ErrorBanner } from '../../components/common/ErrorBanner'
import { LoadingScreen } from '../../components/common/Loading'
import { useAsync } from '../../hooks/useAsync'
import { formatDate, formatDateTime, formatNumber, formatTime, greeting } from '../../lib/format'
import { bloodPressure, evaluateReading } from '../../lib/vitals'
import type { Patient } from '../../types'

const STATUS_STYLES: Record<string, string> = {
  Stable: 'bg-brand-50 text-brand-700 ring-brand-200',
  'Attention Required': 'bg-warning-50 text-warning-700 ring-warning-200',
  'Critical Alert': 'bg-critical-50 text-critical-700 ring-critical-200',
}

export function FamilyDashboard() {
  const { user } = useAuth()
  const [selectedPatientId, setSelectedPatientId] = useState<number | null>(null)

  const patients = useAsync<Patient[]>(() => patientsApi.list(), [])
  const patientId = selectedPatientId ?? patients.data?.[0]?.id ?? null

  const dashboard = useAsync(
    () => (patientId ? patientsApi.dashboard(patientId) : Promise.resolve(null)),
    [patientId],
  )

  if (patients.loading || (dashboard.loading && !dashboard.data)) {
    return <LoadingScreen label="Loading dashboard" />
  }

  if (patients.error) return <ErrorBanner message={patients.error} onRetry={() => void patients.reload()} />
  if (dashboard.error) return <ErrorBanner message={dashboard.error} onRetry={() => void dashboard.reload()} />

  const data = dashboard.data
  if (!data) {
    return <EmptyState title="No patient linked to this account" description="Ask a coordinator to link a patient." />
  }

  const { patient, current_vitals: vitals, thresholds, active_alerts: alerts } = data
  const nextVisit = data.upcoming_visits[0]
  const lastVisit = data.recent_visits[0]

  const bpState =
    vitals && (evaluateReading('systolic_bp', vitals.systolic_bp, thresholds) !== 'normal' ||
      evaluateReading('diastolic_bp', vitals.diastolic_bp, thresholds) !== 'normal')
      ? evaluateReading('systolic_bp', vitals.systolic_bp, thresholds) !== 'normal'
        ? evaluateReading('systolic_bp', vitals.systolic_bp, thresholds)
        : evaluateReading('diastolic_bp', vitals.diastolic_bp, thresholds)
      : 'normal'

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-navy-800">{greeting(user?.name ?? 'there')}</h1>
          <p className="mt-1 text-sm text-slate-500">
            Here is how {patient.name.split(' ')[0]} is doing today.
          </p>
        </div>

        {(patients.data?.length ?? 0) > 1 && (
          <div>
            <label className="sr-only" htmlFor="patient-select">
              Select patient
            </label>
            <select
              id="patient-select"
              className="field-input"
              value={patientId ?? ''}
              onChange={(event) => setSelectedPatientId(Number(event.target.value))}
            >
              {patients.data?.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {alerts.length > 0 && <AlertBanner alert={alerts[0]} to={`/family/alerts?alert=${alerts[0].id}`} />}

      {/* Health status */}
      <section className="card">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-navy-800 text-lg font-bold text-white">
              {patient.name
                .split(' ')
                .map((part) => part[0])
                .slice(0, 2)
                .join('')}
            </div>
            <div>
              <h2 className="text-xl font-bold text-navy-800">{patient.name}</h2>
              <p className="text-sm text-slate-500">
                {patient.age} years · {patient.gender} · {patient.address}
              </p>
              <p className="mt-2 text-sm text-slate-600">
                Last visit: {lastVisit ? formatDate(lastVisit.scheduled_at) : 'No completed visits yet'}
                {data.caregiver ? ` · Caregiver: ${data.caregiver.name}` : ''}
              </p>
              <Link
                to={`/family/patient/${patient.id}`}
                className="mt-2 inline-block text-sm font-semibold text-brand-600 hover:underline"
              >
                View full profile and history
              </Link>
            </div>
          </div>

          <span
            className={`inline-flex shrink-0 items-center gap-2 self-start rounded-full px-3.5 py-2 text-sm font-bold ring-1 ring-inset ${
              STATUS_STYLES[data.overall_status] ?? STATUS_STYLES.Stable
            }`}
          >
            <span className="h-2 w-2 rounded-full bg-current" aria-hidden="true" />
            {data.overall_status}
          </span>
        </div>
      </section>

      {/* Vitals */}
      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Latest Vitals</h2>
          {vitals && (
            <p className="text-xs text-slate-500">Recorded {formatDateTime(vitals.recorded_at)}</p>
          )}
        </div>

        {vitals ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <VitalCard
              label="Blood Pressure"
              metric="systolic_bp"
              value={bloodPressure(vitals)}
              numericValue={vitals.systolic_bp}
              thresholds={thresholds}
              recordedAt={vitals.recorded_at}
              stateOverride={bpState}
            />
            <VitalCard
              label="Heart Rate"
              metric="heart_rate"
              value={formatNumber(vitals.heart_rate)}
              numericValue={vitals.heart_rate}
              thresholds={thresholds}
              recordedAt={vitals.recorded_at}
            />
            <VitalCard
              label="SpO2"
              metric="spo2"
              value={formatNumber(vitals.spo2)}
              numericValue={vitals.spo2}
              thresholds={thresholds}
              recordedAt={vitals.recorded_at}
            />
            <VitalCard
              label="Glucose"
              metric="blood_glucose"
              value={formatNumber(vitals.blood_glucose)}
              numericValue={vitals.blood_glucose}
              thresholds={thresholds}
              recordedAt={vitals.recorded_at}
            />
            <VitalCard
              label="Temperature"
              metric="temperature"
              value={formatNumber(vitals.temperature)}
              numericValue={vitals.temperature}
              thresholds={thresholds}
              recordedAt={vitals.recorded_at}
            />
            <VitalCard
              label="Weight"
              metric="weight"
              value={formatNumber(vitals.weight)}
              numericValue={vitals.weight}
              thresholds={thresholds}
              recordedAt={vitals.recorded_at}
            />
          </div>
        ) : (
          <EmptyState
            title="No vitals recorded yet"
            description="Readings appear here after the first caregiver visit."
          />
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <VitalsTrendChart history={data.vitals_history} thresholds={thresholds} />
        </div>
        <AdherenceCard adherence={data.medication_adherence} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card
          title="Upcoming Visit"
          action={
            <Link to="/family/alerts" className="text-xs font-semibold text-brand-600 hover:underline">
              View alerts
            </Link>
          }
        >
          {nextVisit ? (
            <div>
              <p className="text-lg font-semibold text-navy-800">{formatDate(nextVisit.scheduled_at)}</p>
              <p className="text-sm text-slate-500">{formatTime(nextVisit.scheduled_at)}</p>
              <p className="mt-2 text-sm text-slate-600">
                Caregiver: {nextVisit.caregiver_name ?? data.caregiver?.name ?? 'To be assigned'}
              </p>
              <div className="mt-3">
                <VisitStatusBadge status={nextVisit.status} />
              </div>
            </div>
          ) : (
            <EmptyState title="No upcoming visit scheduled" />
          )}
        </Card>

        <Card title="Caregiver">
          {data.caregiver ? (
            <div>
              <p className="text-lg font-semibold text-navy-800">{data.caregiver.name}</p>
              <p className="text-sm text-slate-500">{data.caregiver.credential}</p>
              <dl className="mt-3 space-y-1 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Verification</dt>
                  <dd className="font-medium capitalize text-navy-800">
                    {data.caregiver.verification_status}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Contact</dt>
                  <dd className="font-medium text-navy-800">{data.caregiver.phone ?? '--'}</dd>
                </div>
              </dl>
            </div>
          ) : (
            <EmptyState title="No caregiver assigned yet" />
          )}
        </Card>

        <Card
          title="Recent Visits"
          action={
            <Link to="/family/medications" className="text-xs font-semibold text-brand-600 hover:underline">
              Medications
            </Link>
          }
        >
          {data.recent_visits.length === 0 ? (
            <EmptyState title="No completed visits yet" />
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.recent_visits.slice(0, 4).map((visit) => (
                <li key={visit.id} className="flex items-center justify-between gap-3 py-2.5">
                  <div>
                    <p className="text-sm font-medium text-navy-800">{formatDate(visit.scheduled_at)}</p>
                    <p className="text-xs text-slate-500">{visit.caregiver_name ?? 'Caregiver'}</p>
                  </div>
                  <VisitStatusBadge status={visit.status} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
