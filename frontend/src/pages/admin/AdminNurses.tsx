import { adminApi } from '../../api/admin'
import { useAsync } from '../../hooks/useAsync'
import type { Nurse } from '../../types'
import { Badge, Card, EmptyState, ErrorState, LoadingScreen } from '../../components/ui'

export function AdminNurses() {
  const nurses = useAsync<Nurse[]>(() => adminApi.nurses(), [])

  if (nurses.loading) return <LoadingScreen label="Loading nurses" />
  if (nurses.error)
    return <ErrorState message={nurses.error} onRetry={() => void nurses.reload()} />

  const rows = nurses.data ?? []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 font-bold text-text-primary">Nurses</h1>
        <p className="mt-1 text-small text-text-secondary">Field staff available for visit assignment.</p>
      </div>

      {rows.length === 0 ? (
        <EmptyState title="No nurses registered" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((nurse) => (
            <Card key={nurse.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-body font-semibold text-text-primary">{nurse.name}</h2>
                  <p className="text-small text-text-secondary">{nurse.credential}</p>
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
                  <dd className="font-semibold tnum text-text-primary">{nurse.open_visits ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-text-secondary">Status</dt>
                  <dd className="font-medium capitalize text-text-primary">{nurse.status}</dd>
                </div>
              </dl>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
