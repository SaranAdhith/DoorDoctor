import { useState, type FormEvent } from 'react'

import type { VitalsSubmission } from '../../types'
import { Button, Input } from '../ui'

interface VitalField {
  name: keyof VitalsSubmission
  label: string
  unit: string
  min: number
  max: number
  step: number
  placeholder: string
}

// Bounds mirror the backend input validation. The server re-validates everything.
const FIELDS: VitalField[] = [
  { name: 'systolic_bp', label: 'Systolic BP', unit: 'mmHg', min: 50, max: 250, step: 1, placeholder: '130' },
  { name: 'diastolic_bp', label: 'Diastolic BP', unit: 'mmHg', min: 30, max: 150, step: 1, placeholder: '80' },
  { name: 'heart_rate', label: 'Heart rate', unit: 'bpm', min: 20, max: 250, step: 1, placeholder: '82' },
  { name: 'blood_glucose', label: 'Blood glucose', unit: 'mg/dL', min: 20, max: 600, step: 1, placeholder: '110' },
  { name: 'spo2', label: 'SpO2', unit: '%', min: 50, max: 100, step: 1, placeholder: '98' },
  { name: 'temperature', label: 'Temperature', unit: '°F', min: 80, max: 115, step: 0.1, placeholder: '98.2' },
  { name: 'weight', label: 'Weight', unit: 'kg', min: 20, max: 250, step: 0.1, placeholder: '64' },
]

type FormValues = Record<keyof VitalsSubmission, string>

const EMPTY: FormValues = {
  systolic_bp: '',
  diastolic_bp: '',
  heart_rate: '',
  blood_glucose: '',
  spo2: '',
  temperature: '',
  weight: '',
}

interface Props {
  disabled?: boolean
  submitting?: boolean
  onSubmit: (values: VitalsSubmission) => Promise<void>
}

export function VitalsForm({ disabled = false, submitting = false, onSubmit }: Props) {
  const [values, setValues] = useState<FormValues>(EMPTY)
  const [errors, setErrors] = useState<Partial<Record<keyof VitalsSubmission, string>>>({})

  function validate(): VitalsSubmission | null {
    const nextErrors: Partial<Record<keyof VitalsSubmission, string>> = {}
    const parsed: Partial<VitalsSubmission> = {}

    for (const field of FIELDS) {
      const raw = values[field.name].trim()
      if (raw === '') {
        nextErrors[field.name] = 'This reading is required.'
        continue
      }
      const numeric = Number(raw)
      if (Number.isNaN(numeric)) {
        nextErrors[field.name] = 'Enter a number.'
        continue
      }
      if (numeric < field.min || numeric > field.max) {
        nextErrors[field.name] = `Enter a value between ${field.min} and ${field.max} ${field.unit}.`
        continue
      }
      parsed[field.name] = numeric
    }

    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0 ? (parsed as VitalsSubmission) : null
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const parsed = validate()
    if (!parsed) return
    await onSubmit(parsed)
    setValues(EMPTY)
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FIELDS.map((field) => (
          <Input
            key={field.name}
            label={`${field.label} (${field.unit})`}
            name={field.name}
            type="number"
            inputMode="decimal"
            step={field.step}
            min={field.min}
            max={field.max}
            placeholder={field.placeholder}
            disabled={disabled || submitting}
            value={values[field.name]}
            error={errors[field.name] ?? null}
            onChange={(event) =>
              setValues((current) => ({ ...current, [field.name]: event.target.value }))
            }
          />
        ))}
      </div>

      <Button
        type="submit"
        variant="accent"
        className="mt-5 w-full sm:w-auto"
        disabled={disabled}
        loading={submitting}
      >
        {submitting ? 'Saving readings…' : 'Save readings'}
      </Button>
    </form>
  )
}
