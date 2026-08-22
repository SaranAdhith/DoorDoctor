import { useState } from 'react'

import { patientsApi } from '../../api/patients'
import { AssistantPanel } from '../../components/assistant/AssistantPanel'
import { useAsync } from '../../hooks/useAsync'
import type { Patient } from '../../types'
import { ErrorState, LoadingScreen, Select } from '../../components/ui'

/**
 * "Ask DoorDoctor" for a family member.
 *
 * Scoped to one patient, which the server re-authorizes on every question — a
 * patient this account cannot see is a 404, so the picker is a convenience and
 * never a permission.
 */
export function FamilyAssistant() {
  const [selectedPatientId, setSelectedPatientId] = useState<number | null>(null)
  const patients = useAsync<Patient[]>(() => patientsApi.list(), [])
  const patientId = selectedPatientId ?? patients.data?.[0]?.id ?? null
  const patient = patients.data?.find((candidate) => candidate.id === patientId)
  const firstName = patient?.name.split(' ')[0]

  if (patients.loading) return <LoadingScreen label="Loading assistant" />
  if (patients.error) {
    return <ErrorState message={patients.error} onRetry={() => void patients.reload()} />
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-h1 font-bold text-text-primary">Ask DoorDoctor</h1>
          <p className="mt-1 text-small text-text-secondary">
            Questions about {firstName ? `${firstName}'s` : 'your relative’s'} care, answered from
            the visit records.
          </p>
        </div>
        {patients.data && patients.data.length > 1 && (
          <Select
            label="Patient"
            hideLabel
            className="sm:w-56"
            value={patientId ?? ''}
            onChange={(event) => setSelectedPatientId(Number(event.target.value))}
          >
            {patients.data.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
              </option>
            ))}
          </Select>
        )}
      </div>

      <AssistantPanel
        patientId={patientId}
        showEmergencyBlock
        intro={
          firstName
            ? `Ask about ${firstName}'s readings, medicines, visits, nurse or your plan.`
            : 'Ask about your DoorDoctor plan and payments.'
        }
      />
    </div>
  )
}
