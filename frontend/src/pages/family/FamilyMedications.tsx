import { useState, type FormEvent } from 'react'

import { patientsApi } from '../../api/patients'
import { ApiError } from '../../api/client'
import { AdherenceCard } from '../../components/cards/AdherenceCard'
import { useAsync } from '../../hooks/useAsync'
import type { Patient } from '../../types'
import { Button, Card, EmptyState, ErrorState, Input, LoadingScreen, Select, useToast } from '../../components/ui'

export function FamilyMedications() {
  const { notify } = useToast()
  const patients = useAsync<Patient[]>(() => patientsApi.list(), [])
  const patientId = patients.data?.[0]?.id ?? null

  const data = useAsync(
    async () =>
      patientId
        ? {
            medications: await patientsApi.medications(patientId),
            adherence: await patientsApi.adherence(patientId),
          }
        : null,
    [patientId],
  )

  const [form, setForm] = useState({ name: '', dosage: '', frequency: 'Once daily', scheduled_time: '08:00' })
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  async function addMedication(event: FormEvent) {
    event.preventDefault()
    if (!patientId) return
    if (!form.name.trim() || !form.dosage.trim()) {
      setFormError('Name and dosage are required.')
      return
    }
    setFormError(null)
    setSubmitting(true)
    try {
      await patientsApi.createMedication(patientId, form)
      notify(`${form.name} added to the schedule.`, 'success')
      setForm({ name: '', dosage: '', frequency: 'Once daily', scheduled_time: '08:00' })
      await data.reload({ quiet: true })
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'Could not add the medication.', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  if (patients.loading || data.loading) return <LoadingScreen label="Loading medications" />
  if (patients.error) return <ErrorState message={patients.error} onRetry={() => void patients.reload()} />
  if (data.error) return <ErrorState message={data.error} onRetry={() => void data.reload()} />
  if (!data.data) return <EmptyState title="No patient linked to this account" />

  const { medications, adherence } = data.data

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 font-bold text-text-primary">Medications</h1>
        <p className="mt-1 text-small text-text-secondary">
          The schedule nurses follow during each visit, and how doses have been logged.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card title="Schedule">
            {medications.length === 0 ? (
              <EmptyState title="No medications scheduled" description="Add the first one below." />
            ) : (
              <ul className="divide-y divide-slate-100">
                {medications.map((medication) => (
                  <li key={medication.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                    <div>
                      <p className="font-semibold text-text-primary">
                        {medication.name}{' '}
                        <span className="font-normal text-text-secondary">{medication.dosage}</span>
                      </p>
                      <p className="text-caption text-text-secondary">{medication.frequency}</p>
                    </div>
                    <span className="rounded-lg bg-navy-50 px-2.5 py-1 text-small font-semibold tnum text-navy-700">
                      {medication.scheduled_time}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <AdherenceCard adherence={adherence} />
      </div>

      <Card title="Add a medication">
        <form onSubmit={addMedication} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <Input
            className="lg:col-span-2"
            label="Name"
            value={form.name}
            error={formError && !form.name.trim() ? formError : null}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            placeholder="e.g. Amlodipine"
          />
          <Input
            label="Dosage"
            value={form.dosage}
            error={formError && !form.dosage.trim() ? formError : null}
            onChange={(event) => setForm({ ...form, dosage: event.target.value })}
            placeholder="5 mg"
          />
          <Select
            label="Frequency"
            value={form.frequency}
            onChange={(event) => setForm({ ...form, frequency: event.target.value })}
          >
            <option>Once daily</option>
            <option>Twice daily</option>
            <option>Three times daily</option>
            <option>Weekly</option>
            <option>As needed</option>
          </Select>
          <Input
            label="Time"
            type="time"
            value={form.scheduled_time}
            onChange={(event) => setForm({ ...form, scheduled_time: event.target.value })}
          />

          <Button
            type="submit"
            variant="accent"
            loading={submitting}
            className="lg:col-span-5 lg:w-auto lg:justify-self-start"
          >
            {submitting ? 'Adding…' : 'Add medication'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
