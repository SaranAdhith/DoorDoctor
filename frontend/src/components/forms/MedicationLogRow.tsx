import { useState, type ReactNode } from 'react'

import { cn } from '../../lib/cn'
import type { Medication, MedicationLog, MedicationLogStatus } from '../../types'
import { Badge, Button, Input } from '../ui'

interface Props {
  medication: Medication
  existingLog?: MedicationLog
  disabled: boolean
  onSubmit: (status: MedicationLogStatus, reason: string | null) => Promise<void>
  /**
   * Rendered inside this row, under the controls. Phase 10 puts the dose
   * photograph here rather than beside the row, because this component owns the
   * `<li>` and a sibling `<li>` holding one button would be invalid markup for
   * no gain.
   */
  footer?: ReactNode
}

const OPTIONS: { value: MedicationLogStatus; label: string; active: string }[] = [
  { value: 'administered', label: 'Taken', active: 'border-brand-500 bg-brand-500 text-text-inverted' },
  { value: 'skipped', label: 'Skipped', active: 'border-warning-500 bg-warning-500 text-text-inverted' },
  { value: 'refused', label: 'Refused', active: 'border-critical-600 bg-critical-600 text-text-inverted' },
]

const LOGGED_LABELS: Record<MedicationLogStatus, string> = {
  administered: 'Taken',
  skipped: 'Skipped',
  refused: 'Refused',
}

export function MedicationLogRow({
  medication,
  existingLog,
  disabled,
  onSubmit,
  footer,
}: Props) {
  const [status, setStatus] = useState<MedicationLogStatus | null>(existingLog?.status ?? null)
  const [reason, setReason] = useState(existingLog?.reason ?? '')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const needsReason = status === 'skipped' || status === 'refused'

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
    <li className="rounded-2xl border border-border-subtle p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="min-w-0">
          <p className="text-body font-semibold text-text-primary">
            {medication.name}{' '}
            <span className="font-normal text-text-secondary">{medication.dosage}</span>
          </p>
          <p className="text-caption text-text-muted">
            {medication.frequency} · scheduled {medication.scheduled_time}
          </p>
        </div>
        {existingLog && <Badge tone="neutral">Logged: {LOGGED_LABELS[existingLog.status]}</Badge>}
      </div>

      <div
        className="mt-3 flex flex-wrap gap-2"
        role="group"
        aria-label={`Outcome for ${medication.name}`}
      >
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
            className={cn(
              'min-h-control rounded-xl border px-3.5 text-small font-semibold transition-colors',
              'disabled:cursor-not-allowed disabled:opacity-50',
              status === option.value
                ? option.active
                : 'border-border-subtle bg-surface-raised text-text-secondary hover:bg-surface',
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      {needsReason && (
        <Input
          className="mt-3"
          label="Reason"
          required
          value={reason}
          disabled={disabled || saving}
          onChange={(event) => setReason(event.target.value)}
          placeholder="e.g. Patient had not eaten yet"
          error={error && !reason.trim() ? error : null}
        />
      )}

      {error && !needsReason && (
        <p className="mt-2 text-small font-medium text-critical-600" role="alert">
          {error}
        </p>
      )}

      <Button
        variant="ghost"
        size="sm"
        className="mt-3"
        onClick={() => void save()}
        disabled={disabled}
        loading={saving}
      >
        {existingLog ? 'Update log' : 'Save medication log'}
      </Button>

      {footer && <div className="mt-3 border-t border-border-subtle pt-3">{footer}</div>}
    </li>
  )
}
