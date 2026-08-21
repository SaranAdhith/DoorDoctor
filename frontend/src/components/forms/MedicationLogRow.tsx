import { useState } from 'react'

import type { Medication, MedicationLog, MedicationLogStatus } from '../../types'

interface Props {
  medication: Medication
  existingLog?: MedicationLog
  disabled: boolean
  onSubmit: (status: MedicationLogStatus, reason: string | null) => Promise<void>
}

const OPTIONS: { value: MedicationLogStatus; label: string; active: string }[] = [
  { value: 'administered', label: 'Administered', active: 'bg-brand-500 text-white border-brand-500' },
  { value: 'skipped', label: 'Skipped', active: 'bg-warning-500 text-white border-warning-500' },
  { value: 'refused', label: 'Refused', active: 'bg-critical-600 text-white border-critical-600' },
]

export function MedicationLogRow({ medication, existingLog, disabled, onSubmit }: Props) {
  const [status, setStatus] = useState<MedicationLogStatus | null>(existingLog?.status ?? null)
  const [reason, setReason] = useState(existingLog?.reason ?? '')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const needsReason = status === 'skipped' || status === 'refused'
  const reasonId = `reason-${medication.id}`

  async function save() {
    if (!status) {
      setError('Choose an outcome for this dose.')
      return
    }
    if (needsReason && !reason.trim()) {
      setError('A reason is required when a dose is skipped or refused.')
      return
    }
    setError(null)
    setSaving(true)
    try {
      await onSubmit(status, needsReason ? reason.trim() : null)
    } finally {
      setSaving(false)
    }
  }

  return (
    <li className="rounded-2xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="font-semibold text-navy-800">
            {medication.name} <span className="font-normal text-slate-500">{medication.dosage}</span>
          </p>
          <p className="text-xs text-slate-500">
            {medication.frequency} · scheduled {medication.scheduled_time}
          </p>
        </div>
        {existingLog && (
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-600">
            Logged: {existingLog.status}
          </span>
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label={`Outcome for ${medication.name}`}>
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            disabled={disabled || saving}
            aria-pressed={status === option.value}
            onClick={() => {
              setStatus(option.value)
              setError(null)
            }}
            className={`rounded-xl border px-3 py-2 text-sm font-semibold transition-colors disabled:opacity-50 ${
              status === option.value
                ? option.active
                : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {needsReason && (
        <div className="mt-3">
          <label className="field-label" htmlFor={reasonId}>
            Reason (required)
          </label>
          <input
            id={reasonId}
            type="text"
            value={reason}
            disabled={disabled || saving}
            onChange={(event) => setReason(event.target.value)}
            placeholder="e.g. Patient had not eaten yet"
            className="field-input"
            aria-invalid={Boolean(error)}
          />
        </div>
      )}

      {error && <p className="field-error">{error}</p>}

      <button
        type="button"
        onClick={() => void save()}
        disabled={disabled || saving}
        className="btn-ghost mt-3 py-2 text-xs"
      >
        {saving ? 'Saving...' : existingLog ? 'Update log' : 'Save medication log'}
      </button>
    </li>
  )
}
