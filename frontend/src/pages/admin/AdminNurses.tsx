import { useState } from 'react'

import { nursesApi } from '../../api/trust'
import { useAsync } from '../../hooks/useAsync'
import { formatDate } from '../../lib/format'
import type { NurseAdminRecord, NurseCredential } from '../../types'
import {
  Badge,
  Button,
  Card,
  Drawer,
  EmptyState,
  ErrorState,
  LoadingScreen,
  Textarea,
  useToast,
} from '../../components/ui'

/**
 * The nurse roster, and the verification queue inside it (§4.10).
 *
 * A credential is verified **by a named person on a named day**, and this is
 * where that name is created. The backend refuses to call a credential verified
 * without both, so there is no path here that produces a badge a family reads as
 * checked when nobody checked it.
 *
 * The registration number appears on this screen and nowhere a family can
 * reach: the two projections are different objects on the server, not one
 * object with fields hidden in the UI.
 */

function credentialTone(credential: NurseCredential) {
  if (credential.expired) return 'attention' as const
  if (credential.verification_status === 'verified') return 'good' as const
  if (credential.verification_status === 'rejected') return 'critical' as const
  return 'watch' as const
}

export function AdminNurses() {
  const { notify } = useToast()
  const nurses = useAsync<NurseAdminRecord[]>(() => nursesApi.list(), [])
  const [open, setOpen] = useState<NurseAdminRecord | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  if (nurses.loading) return <LoadingScreen label="Loading nurses" />
  if (nurses.error)
    return <ErrorState message={nurses.error} onRetry={() => void nurses.reload()} />

  const rows = nurses.data ?? []
  const pending = rows.filter((nurse) =>
    nurse.credentials.some((credential) => credential.verification_status === 'pending'),
  )

  async function decide(credentialId: number, action: 'verify' | 'reject', nurseId: number) {
    setBusy(true)
    try {
      if (action === 'verify') await nursesApi.verifyCredential(credentialId, note.trim() || undefined)
      else await nursesApi.rejectCredential(credentialId, note.trim() || undefined)
      notify(action === 'verify' ? 'Credential verified.' : 'Credential rejected.', 'success')
      setNote('')
      const refreshed = await nurses.reload({ quiet: true })
      const updated = refreshed?.find((nurse) => nurse.id === nurseId) ?? null
      setOpen(updated)
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not update that.', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 font-bold text-text-primary">Nurses</h1>
        <p className="mt-1 text-small text-text-secondary">
          Field staff, their zones and the credentials families can see.
        </p>
      </div>

      {pending.length > 0 && (
        <Card
          title={`${pending.length} nurse${pending.length === 1 ? '' : 's'} waiting on a credential check`}
          description="A family only ever sees credentials that a named person has checked."
        >
          <ul className="flex flex-wrap gap-2">
            {pending.map((nurse) => (
              <li key={nurse.id}>
                <Button size="sm" variant="subtle" onClick={() => setOpen(nurse)}>
                  {nurse.name}
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {rows.length === 0 ? (
        <EmptyState title="No nurses registered" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((nurse) => (
            <Card key={nurse.id}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-body font-semibold text-text-primary">{nurse.name}</h2>
                  <p className="text-small text-text-secondary">
                    {nurse.credential}
                    {nurse.zone && ` · ${nurse.zone}`}
                  </p>
                </div>
                <Badge tone={nurse.verification_status === 'verified' ? 'good' : 'watch'}>
                  {nurse.verification_status}
                </Badge>
              </div>

              <dl className="mt-4 space-y-1.5 text-small">
                <div className="flex justify-between gap-3">
                  <dt className="text-text-secondary">Email</dt>
                  <dd className="truncate font-medium text-text-primary">{nurse.email}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-text-secondary">Phone</dt>
                  <dd className="font-medium text-text-primary">{nurse.phone ?? '--'}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-text-secondary">Open visits</dt>
                  <dd className="tnum font-semibold text-text-primary">{nurse.open_visits}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-text-secondary">Patients covered</dt>
                  <dd className="tnum font-semibold text-text-primary">{nurse.patients_covered}</dd>
                </div>
              </dl>

              <Button
                variant="ghost"
                size="sm"
                className="mt-3"
                onClick={() => setOpen(nurse)}
              >
                Credentials ({nurse.credentials.length})
              </Button>
            </Card>
          ))}
        </div>
      )}

      <Drawer open={open !== null} onClose={() => setOpen(null)} title={open?.name ?? 'Nurse'}>
        {open && (
          <div className="space-y-4">
            <p className="text-small text-text-secondary">
              {open.credential}
              {open.zone && ` · ${open.zone}`}
              {open.years_experience != null && ` · ${open.years_experience} years in nursing`}
            </p>

            <ul className="space-y-3">
              {open.credentials.map((credential) => (
                <li
                  key={credential.id}
                  className="rounded-lg border border-border-subtle p-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium text-text-primary">{credential.title}</p>
                      <p className="text-small text-text-secondary">{credential.issuing_body}</p>
                      {credential.registration_number && (
                        <p className="tnum mt-1 text-caption text-text-muted">
                          {credential.registration_number}
                        </p>
                      )}
                      {credential.expires_on && (
                        <p className="text-caption text-text-muted">
                          Expires {formatDate(credential.expires_on)}
                        </p>
                      )}
                      {credential.verified_at && credential.verified_by_name && (
                        <p className="mt-1 text-caption text-text-muted">
                          Checked by {credential.verified_by_name} on{' '}
                          {formatDate(credential.verified_at)}
                        </p>
                      )}
                      {credential.note && (
                        <p className="mt-1 text-caption text-text-secondary">{credential.note}</p>
                      )}
                    </div>
                    <Badge tone={credentialTone(credential)}>
                      {credential.expired ? 'expired' : credential.verification_status}
                    </Badge>
                  </div>

                  {credential.verification_status === 'pending' && !credential.expired && (
                    <div className="mt-3 flex gap-2">
                      <Button
                        size="sm"
                        disabled={busy}
                        onClick={() => void decide(credential.id, 'verify', open.id)}
                      >
                        Verify
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={busy}
                        onClick={() => void decide(credential.id, 'reject', open.id)}
                      >
                        Reject
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>

            <Textarea
              label="Note for the next decision"
              hint="Stored against the credential you verify or reject next."
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={2}
            />
          </div>
        )}
      </Drawer>
    </div>
  )
}
