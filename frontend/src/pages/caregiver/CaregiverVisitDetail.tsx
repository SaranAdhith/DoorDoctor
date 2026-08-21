import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { visitsApi } from '../../api/visits'
import { AlertCard } from '../../components/alerts/AlertCard'
import { Card, EmptyState } from '../../components/common/Card'
import { VisitStatusBadge } from '../../components/common/Badge'
import { ErrorBanner } from '../../components/common/ErrorBanner'
import { LoadingScreen } from '../../components/common/Loading'
import { useToast } from '../../components/common/Toast'
import { MedicationLogRow } from '../../components/forms/MedicationLogRow'
import { VitalsForm } from '../../components/forms/VitalsForm'
import { useAsync } from '../../hooks/useAsync'
import { formatDateTime, formatNumber, formatTime } from '../../lib/format'
import { bloodPressure } from '../../lib/vitals'
import type { Alert, MedicationLogStatus, VisitDetail, VitalsSubmission } from '../../types'

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

export function CaregiverVisitDetail() {
  const { visitId } = useParams()
  const id = Number(visitId)
  const { notify } = useToast()

  const visit = useAsync<VisitDetail>(() => visitsApi.get(id), [id])
  const [busy, setBusy] = useState(false)
  const [notes, setNotes] = useState<string | null>(null)
  const [lastAlerts, setLastAlerts] = useState<Alert[]>([])
  const [lastResultMessage, setLastResultMessage] = useState<string | null>(null)

  if (visit.loading) return <LoadingScreen label="Loading visit" />
  if (visit.error) return <ErrorBanner message={visit.error} onRetry={() => void visit.reload()} />
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
      <Link to="/caregiver/visits" className="inline-flex items-center gap-1 text-sm font-semibold text-slate-500 hover:text-navy-800">
        <span aria-hidden="true">&larr;</span> Back to visits
      </Link>

      {/* Patient summary */}
      <Card>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-navy-800">{data.patient?.name ?? 'Patient'}</h1>
            <p className="mt-0.5 text-sm text-slate-500">
              {data.patient?.age ? `${data.patient.age} years · ` : ''}
              {data.patient?.address}
            </p>
            <p className="mt-2 text-sm text-slate-600">
              Scheduled {formatDateTime(data.scheduled_at)}
              {data.checkin_at ? ` · Checked in ${formatTime(data.checkin_at)}` : ''}
            </p>
          </div>
          <VisitStatusBadge status={data.status} />
        </div>

        <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
          {isScheduled && (
            <button type="button" onClick={() => void checkIn()} className="btn-accent" disabled={busy}>
              {busy ? 'Starting...' : 'Check In'}
            </button>
          )}
          {isInProgress && (
            <button type="button" onClick={() => void completeVisit()} className="btn-primary" disabled={busy}>
              Complete Visit
            </button>
          )}
          {isCompleted && (
            <p className="text-sm font-medium text-brand-700">
              Visit completed {data.checkout_at ? `at ${formatTime(data.checkout_at)}` : ''} - this record is
              now read-only.
            </p>
          )}
        </div>
      </Card>

      {lastResultMessage && (
        <div
          className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${
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
          <div className="mt-6 border-t border-slate-100 pt-4">
            <h3 className="card-heading">Recorded this visit</h3>
            <ul className="mt-3 space-y-2">
              {data.vitals.map((entry) => (
                <li
                  key={entry.id}
                  className={`rounded-xl px-3 py-2.5 text-sm ${
                    entry.threshold_breached ? 'bg-critical-50 text-critical-700' : 'bg-slate-50 text-slate-700'
                  }`}
                >
                  <span className="font-semibold tabular-nums">{bloodPressure(entry)} mmHg</span>
                  <span className="tabular-nums">
                    {' '}
                    · {formatNumber(entry.heart_rate)} bpm · SpO2 {formatNumber(entry.spo2)}% ·{' '}
                    {formatNumber(entry.blood_glucose)} mg/dL · {formatNumber(entry.temperature)} °F ·{' '}
                    {formatNumber(entry.weight)} kg
                  </span>
                  <span className="mt-1 block text-xs">
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

      {/* Notes */}
      <Card title="Observations">
        <label className="sr-only" htmlFor="visit-notes">
          Observations
        </label>
        <textarea
          id="visit-notes"
          className="field-input min-h-[120px]"
          value={noteValue}
          disabled={!isInProgress}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Describe what you observed during the visit. Do not record a diagnosis."
        />
        <button
          type="button"
          onClick={() => void saveNotes()}
          className="btn-ghost mt-3"
          disabled={!isInProgress || busy}
        >
          Save observations
        </button>
      </Card>

      <p className="text-xs text-slate-500">
        Alerts describe readings outside the patient's configured monitoring thresholds. They are not
        medical diagnoses.
      </p>
    </div>
  )
}
