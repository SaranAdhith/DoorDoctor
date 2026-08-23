import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { visitsApi } from '../../api/visits'
import { screeningsApi } from '../../api/clinical'
import { AlertCard } from '../../components/alerts/AlertCard'
import { EmergencyBlock, Phq2Form } from '../../components/clinical'
import { MedicationLogRow } from '../../components/forms/MedicationLogRow'
import { VitalsForm } from '../../components/forms/VitalsForm'
import { useAsync } from '../../hooks/useAsync'
import { formatDateTime, formatNumber, formatTime } from '../../lib/format'
import { bloodPressure } from '../../lib/vitals'
import type {
  Alert,
  MedicationLogStatus,
  ScreeningInstrument,
  ScreeningStatus,
  VisitDetail,
  VitalsSubmission,
} from '../../types'
import { Button, Card, EmptyState, ErrorState, LoadingScreen, Textarea, VisitStatusBadge, useToast } from '../../components/ui'

/** Optional browser location; check-in never blocks on it in this MVP. */
async function tryGetLocation(): Promise<{ lat: number; lng: number } | undefined> {
  if (!('geolocation' in navigator)) return undefined
  return new Promise((resolve) => {
    const timeout = setTimeout(() => resolve(undefined), 4000)
    navigator.geolocation.getCurrentPosition(
      (position) => {
        clearTimeout(timeout)
        resolve({ lat: position.coords.latitude, lng: position.coords.longitude })
      },
      () => {
        clearTimeout(timeout)
        resolve(undefined)
      },
      { timeout: 4000 },
    )
  })
}

export function NurseVisitDetail() {
  const { visitId } = useParams()
  const id = Number(visitId)
  const { notify } = useToast()

  const visit = useAsync<VisitDetail>(() => visitsApi.get(id), [id])
  const [busy, setBusy] = useState(false)
  const [notes, setNotes] = useState<string | null>(null)
  const [lastAlerts, setLastAlerts] = useState<Alert[]>([])
  const [lastResultMessage, setLastResultMessage] = useState<string | null>(null)
  const [screeningBusy, setScreeningBusy] = useState(false)

  // Served, not hard-coded: PHQ-2's wording is a published instrument's, and a
  // frontend does not get to paraphrase it to fit a layout.
  const instrument = useAsync<ScreeningInstrument>(() => screeningsApi.instrument(), [])
  const patientId = visit.data?.patient?.id ?? null
  const screening = useAsync<ScreeningStatus | null>(
    () => (patientId ? screeningsApi.status(patientId) : Promise.resolve(null)),
    [patientId],
  )

  async function recordScreening(answers: number[]) {
    if (!patientId) return
    setScreeningBusy(true)
    try {
      const recorded = await screeningsApi.record(patientId, answers, id)
      notify(
        recorded.positive
          ? 'Mood check recorded. A follow-up conversation has been added to the care team\u2019s list.'
          : 'Mood check recorded.',
        recorded.positive ? 'warning' : 'success',
      )
      await screening.reload({ quiet: true })
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'Could not record the mood check.', 'error')
    } finally {
      setScreeningBusy(false)
    }
  }

  if (visit.loading) return <LoadingScreen label="Loading visit" />
  if (visit.error) return <ErrorState message={visit.error} onRetry={() => void visit.reload()} />
  if (!visit.data) return <EmptyState title="Visit not found" />

  const data = visit.data
  const isScheduled = data.status === 'scheduled'
  const isInProgress = data.status === 'in_progress'
  const isCompleted = data.status === 'completed'
  const noteValue = notes ?? data.notes ?? ''

  function handleError(error: unknown, fallback: string) {
    notify(error instanceof ApiError ? error.message : fallback, 'error')
  }

  async function checkIn() {
    setBusy(true)
    try {
      const location = await tryGetLocation()
      await visitsApi.checkIn(id, location)
      notify('Checked in. You can now record vitals.', 'success')
      await visit.reload({ quiet: true })
    } catch (error) {
      handleError(error, 'Could not start the visit.')
    } finally {
      setBusy(false)
    }
  }

  async function saveVitals(values: VitalsSubmission) {
    setBusy(true)
    try {
      const result = await visitsApi.recordVitals(id, values)
      setLastAlerts(result.alerts_created)
      if (result.threshold_breached) {
        setLastResultMessage('Threshold exceeded. An alert has been created for the care team.')
        notify('Threshold exceeded - an alert has been created for the care team.', 'warning')
      } else {
        setLastResultMessage('Vitals saved. All readings are within the configured range.')
        notify('Vitals saved. All readings are within the configured range.', 'success')
      }
      await visit.reload({ quiet: true })
    } catch (error) {
      handleError(error, 'Could not save the vitals.')
    } finally {
      setBusy(false)
    }
  }

  async function logMedication(medicationId: number, status: MedicationLogStatus, reason: string | null) {
    try {
      await visitsApi.logMedication(id, { medication_id: medicationId, status, reason })
      notify('Medication log saved.', 'success')
      await visit.reload({ quiet: true })
    } catch (error) {
      handleError(error, 'Could not save the medication log.')
    }
  }

  async function saveNotes() {
    setBusy(true)
    try {
      await visitsApi.saveNotes(id, noteValue)
      notify('Observations saved.', 'success')
      await visit.reload({ quiet: true })
    } catch (error) {
      handleError(error, 'Could not save the observations.')
    } finally {
      setBusy(false)
    }
  }

  async function completeVisit() {
    setBusy(true)
    try {
      await visitsApi.complete(id)
      notify('Visit completed. The family dashboard has been updated.', 'success')
      await visit.reload({ quiet: true })
    } catch (error) {
      handleError(error, 'Could not complete the visit.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <Link to="/nurse/visits" className="inline-flex items-center gap-1 text-small font-semibold text-text-secondary hover:text-navy-800">
        <span aria-hidden="true">&larr;</span> Back to visits
      </Link>

      {/* Patient summary */}
      <Card>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-h2 font-bold text-text-primary">{data.patient?.name ?? 'Patient'}</h1>
            <p className="mt-0.5 text-small text-text-secondary">
              {data.patient?.age ? `${data.patient.age} years · ` : ''}
              {data.patient?.address}
            </p>
            <p className="mt-2 text-small text-text-secondary">
              Scheduled {formatDateTime(data.scheduled_at)}
              {data.checkin_at ? ` · Checked in ${formatTime(data.checkin_at)}` : ''}
            </p>
          </div>
          <VisitStatusBadge status={data.status} />
        </div>

        <div className="mt-4 flex flex-wrap gap-2 border-t border-border-subtle pt-4">
          {isScheduled && (
            <Button variant="accent" onClick={() => void checkIn()} loading={busy}>
              {busy ? 'Starting…' : 'Check in'}
            </Button>
          )}
          {isInProgress && (
            <Button onClick={() => void completeVisit()} disabled={busy}>
              Complete visit
            </Button>
          )}
          {isCompleted && (
            <p className="text-small font-medium text-brand-700">
              Visit completed {data.checkout_at ? `at ${formatTime(data.checkout_at)}` : ''} — this record
              is now read-only.
            </p>
          )}
        </div>
      </Card>

      {/* Permanent on every clinical screen (§4.9). A nurse standing in
          somebody's home is the person most likely to need it. */}
      <EmergencyBlock compact />

      {lastResultMessage && (
        <div
          className={`rounded-2xl border px-4 py-3 text-small font-semibold ${
            lastAlerts.length > 0
              ? 'border-warning-200 bg-warning-50 text-warning-700'
              : 'border-brand-200 bg-brand-50 text-brand-700'
          }`}
          role="status"
        >
          {lastResultMessage}
        </div>
      )}

      {lastAlerts.map((alert) => (
        <AlertCard key={alert.id} alert={alert} patientName={data.patient?.name} />
      ))}

      {/* Vitals */}
      <Card title="Record vitals">
        {isScheduled ? (
          <EmptyState title="Check in first" description="Vitals can be recorded once the visit has started." />
        ) : (
          <VitalsForm disabled={isCompleted} submitting={busy} onSubmit={saveVitals} />
        )}

        {data.vitals.length > 0 && (
          <div className="mt-6 border-t border-border-subtle pt-4">
            <h3 className="text-caption font-semibold uppercase tracking-wide text-text-secondary">
              Recorded this visit
            </h3>
            <ul className="mt-3 space-y-2">
              {data.vitals.map((entry) => (
                <li
                  key={entry.id}
                  className={`rounded-xl px-3 py-2.5 text-small ${
                    entry.threshold_breached ? 'bg-status-critical-bg text-status-critical' : 'bg-surface text-text-primary'
                  }`}
                >
                  <span className="font-semibold tnum">{bloodPressure(entry)} mmHg</span>
                  <span className="tnum">
                    {' '}
                    · {formatNumber(entry.heart_rate)} bpm · SpO2 {formatNumber(entry.spo2)}% ·{' '}
                    {formatNumber(entry.blood_glucose)} mg/dL · {formatNumber(entry.temperature)} °F ·{' '}
                    {formatNumber(entry.weight)} kg
                  </span>
                  <span className="mt-1 block text-caption">
                    {formatTime(entry.recorded_at)}
                    {entry.threshold_breached ? ' · outside configured range' : ' · within configured range'}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {/* Medication */}
      <Card title="Medication">
        {data.medications.length === 0 ? (
          <EmptyState title="No medications scheduled for this patient" />
        ) : (
          <ul className="space-y-3">
            {data.medications.map((medication) => (
              <MedicationLogRow
                key={medication.id}
                medication={medication}
                existingLog={data.medication_logs.find((log) => log.medication_id === medication.id)}
                disabled={!isInProgress}
                onSubmit={(status, reason) => logMedication(medication.id, status, reason)}
              />
            ))}
          </ul>
        )}
      </Card>

      {/* Mood check (§4.7). Offered when it is due, and closed once it is not,
          so the visit screen does not ask the same two questions every day. */}
      <Card
        title="Mood check"
        description={
          screening.data?.latest
            ? `Last recorded ${formatDateTime(screening.data.latest.administered_at)}`
            : 'Two questions, asked roughly once a month.'
        }
      >
        {screening.data && !screening.data.due && (
          <p className="text-small text-text-secondary">
            Not due yet — the last one was inside the {screening.data.cadence_days}-day window.
          </p>
        )}
        {screening.data?.due && instrument.data && (
          <Phq2Form
            instrument={instrument.data}
            submitting={screeningBusy}
            onSubmit={recordScreening}
          />
        )}
      </Card>

      {/* Notes */}
      <Card title="Observations">
        <Textarea
          label="Observations"
          hideLabel
          rows={5}
          value={noteValue}
          disabled={!isInProgress}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Describe what you observed during the visit. Do not record a diagnosis."
        />
        <Button
          variant="ghost"
          className="mt-3"
          onClick={() => void saveNotes()}
          disabled={!isInProgress || busy}
        >
          Save observations
        </Button>
      </Card>

      <p className="text-caption text-text-secondary">
        Alerts describe readings outside the patient's configured monitoring thresholds. They are not
        medical diagnoses.
      </p>
    </div>
  )
}
