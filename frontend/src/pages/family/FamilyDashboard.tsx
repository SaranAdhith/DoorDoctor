import { useState } from 'react'
import { Link } from 'react-router-dom'
import { MessageCircleQuestion } from 'lucide-react'

import { patientsApi } from '../../api/patients'
import { useAuth } from '../../auth/AuthContext'
import { AlertBanner } from '../../components/alerts/AlertBanner'
import { AdherenceCard } from '../../components/cards/AdherenceCard'
import { safetyApi } from '../../api/clinical'
import { SafetyScoreCard, SafetyScoreCardSkeleton } from '../../components/clinical'
import { PlainSummary } from '../../components/family/PlainSummary'
import { VitalCard } from '../../components/cards/VitalCard'
import { VitalsTrendChart } from '../../components/charts/VitalsTrendChart'
import { useAsync } from '../../hooks/useAsync'
import { formatDate, formatDateTime, formatNumber, formatTime, greeting } from '../../lib/format'
import { bloodPressure, evaluateReading } from '../../lib/vitals'
import type { Patient, SafetyScore } from '../../types'
import { Card, EmptyState, ErrorState, LinkButton, LoadingScreen, Select, VisitStatusBadge } from '../../components/ui'

const STATUS_STYLES: Record<string, string> = {
  Stable: 'bg-brand-50 text-brand-700 ring-brand-200',
  'Attention Required': 'bg-warning-50 text-warning-700 ring-warning-200',
  'Critical Alert': 'bg-status-critical-bg text-status-critical ring-critical-200',
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
  // Its own loader rather than a field on the dashboard payload: the score is
  // recalculated live and the dashboard is cached differently, and a failing
  // score must not blank the whole page.
  const safety = useAsync<SafetyScore | null>(
    () => (patientId ? safetyApi.get(patientId) : Promise.resolve(null)),
    [patientId],
  )

  if (patients.loading || (dashboard.loading && !dashboard.data)) {
    return <LoadingScreen label="Loading dashboard" />
  }

  if (patients.error) return <ErrorState message={patients.error} onRetry={() => void patients.reload()} />
  if (dashboard.error) return <ErrorState message={dashboard.error} onRetry={() => void dashboard.reload()} />

  const data = dashboard.data
  if (!data) {
    return <EmptyState title="No patient linked to this account" description="Ask DoorDoctor to link a patient." />
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
          <h1 className="text-h1 font-bold text-text-primary">{greeting(user?.name ?? 'there')}</h1>
          <p className="mt-1 text-small text-text-secondary">
            Here is how {patient.name.split(' ')[0]} is doing today.
          </p>
        </div>

        {(patients.data?.length ?? 0) > 1 && (
          <Select
            label="Select patient"
            hideLabel
            className="sm:w-64"
            value={patientId ?? ''}
            onChange={(event) => setSelectedPatientId(Number(event.target.value))}
          >
            {patients.data?.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
              </option>
            ))}
          </Select>
        )}
      </div>

      {alerts.length > 0 && <AlertBanner alert={alerts[0]} to={`/family/alerts?alert=${alerts[0].id}`} />}

      <PlainSummary patientId={patient.id} />

      {/* Under the summary, not above it. The summary is the sentence a family
          reads first; the score is the number they check afterwards, and a
          number leading the page would be the exact "interpret this yourself"
          problem Phase 6 moved away from. */}
      {safety.loading && <SafetyScoreCardSkeleton />}
      {safety.data && <SafetyScoreCard score={safety.data} />}

      {/* The summary answers "how has she been?". This answers everything else,
          in the reader's own words, which is the natural next question. */}
      <div className="flex justify-center">
        <LinkButton
          to="/family/assistant"
          variant="ghost"
          icon={<MessageCircleQuestion className="h-4 w-4" aria-hidden="true" />}
        >
          Ask a question about {patient.name.split(' ')[0]}
        </LinkButton>
      </div>

      {/* Everything below the divider is the original clinical dashboard,
          unchanged. It has not been removed or reduced — it has stopped being
          the first thing a worried family member has to interpret. */}
      <div className="flex items-center gap-4 pt-2">
        <h2 className="shrink-0 text-small font-semibold uppercase tracking-wide text-text-secondary">
          Detailed health record
        </h2>
        <span className="h-px flex-1 bg-border-subtle" aria-hidden="true" />
      </div>

      {/* Health status */}
      <Card>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-navy-800 text-h2 font-bold text-white">
              {patient.name
                .split(' ')
                .map((part) => part[0])
                .slice(0, 2)
                .join('')}
            </div>
            <div>
              <h2 className="text-h2 font-bold text-text-primary">{patient.name}</h2>
              <p className="text-small text-text-secondary">
                {patient.age} years · {patient.gender} · {patient.address}
              </p>
              <p className="mt-2 text-small text-text-secondary">
                Last visit: {lastVisit ? formatDate(lastVisit.scheduled_at) : 'No completed visits yet'}
                {data.nurse ? ` · Nurse: ${data.nurse.name}` : ''}
              </p>
              <Link
                to={`/family/patient/${patient.id}`}
                className="mt-2 inline-block text-small font-semibold text-brand-600 hover:underline"
              >
                View full profile and history
              </Link>
            </div>
          </div>

          <span
            className={`inline-flex shrink-0 items-center gap-2 self-start rounded-full px-3.5 py-2 text-small font-bold ring-1 ring-inset ${
              STATUS_STYLES[data.overall_status] ?? STATUS_STYLES.Stable
            }`}
          >
            <span className="h-2 w-2 rounded-full bg-current" aria-hidden="true" />
            {data.overall_status}
          </span>
        </div>
      </Card>

      {/* Vitals */}
      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-small font-semibold uppercase tracking-wide text-text-secondary">Latest Vitals</h2>
          {vitals && (
            <p className="text-caption text-text-secondary">Recorded {formatDateTime(vitals.recorded_at)}</p>
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
            description="Readings appear here after the first nurse visit."
          />
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* The grid item needs `min-w-0` as well as the chart inside it —
            the constraint has to be released at every level between the grid
            and the SVG, or the outermost one that still says `auto` wins. */}
        <div className="min-w-0 lg:col-span-2">
          <VitalsTrendChart history={data.vitals_history} thresholds={thresholds} />
        </div>
        <AdherenceCard adherence={data.medication_adherence} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card
          title="Upcoming Visit"
          action={
            <Link to="/family/alerts" className="text-caption font-semibold text-brand-600 hover:underline">
              View alerts
            </Link>
          }
        >
          {nextVisit ? (
            <div>
              <p className="text-h2 font-semibold text-text-primary">{formatDate(nextVisit.scheduled_at)}</p>
              <p className="text-small text-text-secondary">{formatTime(nextVisit.scheduled_at)}</p>
              <p className="mt-2 text-small text-text-secondary">
                Nurse: {nextVisit.nurse_name ?? data.nurse?.name ?? 'To be assigned'}
              </p>
              <div className="mt-3">
                <VisitStatusBadge status={nextVisit.status} />
              </div>
            </div>
          ) : (
            <EmptyState title="No upcoming visit scheduled" />
          )}
        </Card>

        <Card title="Nurse">
          {data.nurse ? (
            <div>
              <p className="text-h2 font-semibold text-text-primary">{data.nurse.name}</p>
              <p className="text-small text-text-secondary">{data.nurse.credential}</p>
              <dl className="mt-3 space-y-1 text-small">
                <div className="flex justify-between gap-3">
                  <dt className="text-text-secondary">Verification</dt>
                  <dd className="font-medium capitalize text-text-primary">
                    {data.nurse.verification_status}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-text-secondary">Contact</dt>
                  <dd className="font-medium text-text-primary">{data.nurse.phone ?? '--'}</dd>
                </div>
              </dl>
            </div>
          ) : (
            <EmptyState title="No nurse assigned yet" />
          )}
        </Card>

        <Card
          title="Recent Visits"
          action={
            <Link to="/family/medications" className="text-caption font-semibold text-brand-600 hover:underline">
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
                    <p className="text-small font-medium text-text-primary">{formatDate(visit.scheduled_at)}</p>
                    <p className="text-caption text-text-secondary">{visit.nurse_name ?? 'Nurse'}</p>
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
