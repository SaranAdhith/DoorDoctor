import { useState, type FormEvent } from 'react'

import { localInputToApi, toLocalInputValue } from '../../lib/format'
import type { Nurse, Patient } from '../../types'

interface Props {
  patients: Patient[]
  nurses: Nurse[]
  submitting: boolean
  onSubmit: (payload: { patient_id: number; nurse_id: number | null; scheduled_at: string }) => Promise<void>
}

function defaultSlot(): string {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  date.setHours(10, 30, 0, 0)
  return toLocalInputValue(date)
}

export function ScheduleVisitForm({ patients, nurses, submitting, onSubmit }: Props) {
  const [patientId, setPatientId] = useState(String(patients[0]?.id ?? ''))
  const [nurseId, setNurseId] = useState(String(nurses[0]?.id ?? ''))
  const [scheduledAt, setScheduledAt] = useState(defaultSlot)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!patientId) {
      setError('Choose a patient.')
      return
    }
    if (!scheduledAt) {
      setError('Choose a date and time.')
      return
    }
    setError(null)
    await onSubmit({
      patient_id: Number(patientId),
      nurse_id: nurseId ? Number(nurseId) : null,
      scheduled_at: localInputToApi(scheduledAt),
    })
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 lg:items-end">
      <div>
        <label className="field-label" htmlFor="visit-patient">
          Patient
        </label>
        <select
          id="visit-patient"
          className="field-input"
          value={patientId}
          onChange={(event) => setPatientId(event.target.value)}
        >
          {patients.map((patient) => (
            <option key={patient.id} value={patient.id}>
              {patient.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="field-label" htmlFor="visit-nurse">
          Nurse
        </label>
        <select
          id="visit-nurse"
          className="field-input"
          value={nurseId}
          onChange={(event) => setNurseId(event.target.value)}
        >
          <option value="">Unassigned</option>
          {nurses.map((nurse) => (
            <option key={nurse.id} value={nurse.id}>
              {nurse.name} ({nurse.credential})
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="field-label" htmlFor="visit-time">
          Date and time
        </label>
        <input
          id="visit-time"
          type="datetime-local"
          className="field-input"
          value={scheduledAt}
          onChange={(event) => setScheduledAt(event.target.value)}
        />
      </div>

      <button type="submit" className="btn-accent h-[46px]" disabled={submitting}>
        {submitting ? 'Scheduling...' : 'Schedule visit'}
      </button>

      {error && (
        <p className="field-error sm:col-span-2 lg:col-span-4">{error}</p>
      )}
    </form>
  )
}
