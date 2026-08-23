import { HeartPulse, MessageSquare, Phone, StickyNote, Video } from 'lucide-react'

import { careApi, safetyApi, screeningsApi } from '../../api/clinical'
import { patientsApi } from '../../api/patients'
import { nursesApi } from '../../api/trust'
import { EmergencyBlock, SafetyScoreCard, SafetyScoreCardSkeleton } from '../../components/clinical'
import { Badge, Card, EmptyState, ErrorState, LoadingScreen } from '../../components/ui'
import { Link } from 'react-router-dom'
import { useAsync } from '../../hooks/useAsync'
import { formatDate, formatRelative } from '../../lib/format'
import type {
  CareChannel,
  CareTeam,
  NurseProfile,
  Patient,
  SafetyScore,
  ScreeningStatus,
} from '../../types'

/**
 * The family's care page: who looks after this patient, how they have been, and
 * what has actually been done (§4.4, §4.5, §4.7).
 *
 * The safety score leads, because it is the one number a family will look for.
 * Everything under it is the evidence — the care manager who is accountable,
 * the calls that were made, and the mood check. A score with no visible care
 * behind it is a dashboard; a score with the calls listed under it is a service.
 */

const CHANNEL_ICONS: Record<CareChannel, typeof Phone> = {
  call: Phone,
  video: Video,
  message: MessageSquare,
  visit: HeartPulse,
  note: StickyNote,
}

export function FamilyCareTeam() {
  const patients = useAsync<Patient[]>(() => patientsApi.list(), [])
  const patientId = patients.data?.[0]?.id ?? null

  const score = useAsync<SafetyScore | null>(
    async () => (patientId ? safetyApi.get(patientId) : null),
    [patientId],
  )
  const team = useAsync<CareTeam | null>(
    async () => (patientId ? careApi.team(patientId) : null),
    [patientId],
  )
  // The nurses who have actually been to this house (§4.10). Not the roster —
  // there is no route a family can call to browse the staff list.
  const nurses = useAsync<NurseProfile[]>(
    async () => (patientId ? nursesApi.forPatient(patientId) : []),
    [patientId],
  )
  const screening = useAsync<ScreeningStatus | null>(
    async () => (patientId ? screeningsApi.status(patientId) : null),
    [patientId],
  )

  if (patients.loading) return <LoadingScreen label="Loading care team" />
  if (patients.error) return <ErrorState message={patients.error} onRetry={() => patients.reload()} />
  if (!patientId) {
    return (
      <EmptyState
        icon={<HeartPulse aria-hidden />}
        title="No patient linked yet"
        description="Ask DoorDoctor to link a patient to your account."
      />
    )
  }

  const assignment = team.data?.assignment ?? null
  const interactions = team.data?.interactions ?? []
  const latest = screening.data?.latest ?? null

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-h1 font-semibold text-text-primary">Care</h1>
        <p className="text-small text-text-secondary">
          How things have been, and who is looking after them.
        </p>
      </header>

      {score.loading && <SafetyScoreCardSkeleton />}
      {score.error && <ErrorState message={score.error} onRetry={() => score.reload()} />}
      {score.data && <SafetyScoreCard score={score.data} />}

      <EmergencyBlock />

      <Card
        title="Your nurses"
        description="The people who come to the house. Every credential here was checked by a named member of the DoorDoctor team."
      >
        {nurses.loading && <LoadingScreen label="Loading nurses" />}
        {nurses.error && <ErrorState message={nurses.error} onRetry={() => nurses.reload()} />}
        {nurses.data?.length === 0 && (
          <p className="text-small text-text-muted">
            No nurse has visited yet. The first visit will show here.
          </p>
        )}
        <ul className="divide-y divide-border-subtle">
          {nurses.data?.map((nurse) => (
            <li key={nurse.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div className="min-w-0">
                <Link
                  to={`/family/nurse/${nurse.id}`}
                  className="font-medium text-text-primary hover:underline"
                >
                  {nurse.name}
                </Link>
                <p className="text-small text-text-secondary">
                  {nurse.credential}
                  {nurse.visits_to_this_patient > 0 &&
                    ` · ${nurse.visits_to_this_patient} visit${nurse.visits_to_this_patient === 1 ? '' : 's'} here`}
                </p>
              </div>
              {nurse.verification_status === 'verified' && <Badge tone="good">Verified</Badge>}
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Your care manager">
        {team.loading && <LoadingScreen label="Loading care team" />}
        {team.error && <ErrorState message={team.error} onRetry={() => team.reload()} />}

        {team.data && !assignment && (
          <p className="text-small text-text-secondary">
            A care manager is being assigned. Until then the DoorDoctor team looks after this
            account together.
          </p>
        )}

        {assignment && (
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-body font-medium text-text-primary">
                {assignment.care_manager_name}
              </p>
              {assignment.languages && (
                <p className="text-small text-text-secondary">Speaks {assignment.languages}</p>
              )}
              <p className="mt-1 text-caption text-text-muted">
                Looking after this account since {formatDate(assignment.assigned_at)}.
              </p>
            </div>
            {assignment.care_manager_kind === 'dedicated' && (
              <Badge tone="good">Dedicated care manager</Badge>
            )}
          </div>
        )}
      </Card>

      <Card
        title="Mood check"
        description="Two questions the nurse asks, so low mood is noticed early."
      >
        {screening.loading && <LoadingScreen label="Loading mood check" />}
        {!latest && !screening.loading && (
          <p className="text-small text-text-secondary">
            No mood check has been recorded yet. The nurse will do one at an upcoming visit.
          </p>
        )}
        {latest && (
          <>
            <p className="text-small text-text-primary">
              {latest.positive
                ? 'The last check suggested a longer conversation would help, and the care team has arranged one.'
                : 'The last check did not raise any concern.'}
            </p>
            <p className="mt-1 text-caption text-text-muted">
              Recorded {formatRelative(latest.administered_at)}
              {latest.administered_by_name ? ` by ${latest.administered_by_name}` : ''}. This is a
              short screening question set, not a diagnosis.
            </p>
          </>
        )}
      </Card>

      <Card title="Recent contact" description="What the care team has done, and when.">
        {interactions.length === 0 ? (
          <p className="text-small text-text-muted">Nothing recorded yet.</p>
        ) : (
          <ul className="space-y-3">
            {interactions.map((interaction) => {
              const Icon = CHANNEL_ICONS[interaction.channel] ?? Phone
              return (
                <li key={interaction.id} className="flex items-start gap-3">
                  <span
                    aria-hidden
                    className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface-sunken text-text-secondary"
                  >
                    <Icon size={14} />
                  </span>
                  <div className="min-w-0">
                    <p className="text-small font-medium text-text-primary">
                      {interaction.subject}
                    </p>
                    {interaction.note && (
                      <p className="text-caption text-text-secondary">{interaction.note}</p>
                    )}
                    <p className="text-caption text-text-muted">
                      {formatRelative(interaction.occurred_at)}
                      {interaction.care_manager_name ? ` · ${interaction.care_manager_name}` : ''}
                      {interaction.minutes ? ` · ${interaction.minutes} min` : ''}
                    </p>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </div>
  )
}
