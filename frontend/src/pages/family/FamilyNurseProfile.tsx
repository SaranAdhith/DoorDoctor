import { ArrowLeft, Languages, Stethoscope } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { patientsApi } from '../../api/patients'
import { nursesApi } from '../../api/trust'
import { CredentialList } from '../../components/trust'
import { Badge, Card, EmptyState, ErrorState, LoadingScreen } from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import { formatDate } from '../../lib/format'
import type { NurseProfile, Patient } from '../../types'

/**
 * The nurse at the door, checkable (§4.10).
 *
 * Reached through the patient — `/patients/{id}/nurses/{id}` — and there is no
 * route a family can call to browse the roster. A family knows their own
 * nurses, not the staff list.
 *
 * The visit count says **visits to your relative**, and it is scoped that way on
 * the server too. "240 visits this quarter" would be a fact about twenty other
 * households.
 */
export function FamilyNurseProfile() {
  const { nurseId } = useParams<{ nurseId: string }>()
  const patients = useAsync<Patient[]>(() => patientsApi.list(), [])
  const patient = patients.data?.[0] ?? null

  const profile = useAsync<NurseProfile | null>(
    async () =>
      patient && nurseId ? nursesApi.one(patient.id, Number(nurseId)) : null,
    [patient?.id, nurseId],
  )

  if (patients.loading || profile.loading) return <LoadingScreen label="Loading the nurse profile" />
  if (profile.error) return <ErrorState message={profile.error} onRetry={() => profile.reload()} />
  const nurse = profile.data
  if (!nurse) {
    return (
      <EmptyState
        icon={<Stethoscope aria-hidden />}
        title="Nurse not found"
        description="This nurse has not visited your relative."
      />
    )
  }

  return (
    <div className="space-y-6">
      <Link
        to="/family/care"
        className="inline-flex items-center gap-1 text-small font-medium text-brand-700 hover:underline"
      >
        <ArrowLeft aria-hidden className="h-4 w-4" />
        Back to care
      </Link>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-h1 font-semibold text-text-primary">{nurse.name}</h1>
          <p className="text-small text-text-secondary">
            {nurse.credential}
            {nurse.zone && ` · ${nurse.zone}`}
          </p>
        </div>
        {nurse.verification_status === 'verified' && (
          <Badge tone="good">Credentials verified by DoorDoctor</Badge>
        )}
      </header>

      {nurse.bio && (
        <Card>
          <p className="text-text-secondary">{nurse.bio}</p>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Card title="With your family">
          <dl className="space-y-2 text-small">
            <div className="flex justify-between gap-3">
              <dt className="text-text-secondary">Visits to your relative</dt>
              <dd className="tnum font-medium text-text-primary">
                {nurse.visits_to_this_patient}
              </dd>
            </div>
            {nurse.last_visit_at && (
              <div className="flex justify-between gap-3">
                <dt className="text-text-secondary">Last visit</dt>
                <dd className="font-medium text-text-primary">{formatDate(nurse.last_visit_at)}</dd>
              </div>
            )}
            {nurse.joined_on && (
              <div className="flex justify-between gap-3">
                <dt className="text-text-secondary">With DoorDoctor since</dt>
                <dd className="font-medium text-text-primary">{formatDate(nurse.joined_on)}</dd>
              </div>
            )}
            {nurse.years_experience != null && (
              <div className="flex justify-between gap-3">
                <dt className="text-text-secondary">Years in nursing</dt>
                <dd className="tnum font-medium text-text-primary">{nurse.years_experience}</dd>
              </div>
            )}
          </dl>

          {nurse.languages.length > 0 && (
            <p className="mt-4 flex items-center gap-2 text-small text-text-secondary">
              <Languages aria-hidden className="h-4 w-4 text-text-muted" />
              Speaks {nurse.languages.join(', ')}
            </p>
          )}
        </Card>

        <Card
          title="Credentials"
          description="Each one was checked by a named member of the DoorDoctor team."
        >
          <CredentialList credentials={nurse.credentials} />
        </Card>
      </div>
    </div>
  )
}
