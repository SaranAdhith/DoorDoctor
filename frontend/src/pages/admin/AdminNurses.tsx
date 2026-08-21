import { adminApi } from '../../api/admin'
import { Badge } from '../../components/common/Badge'
import { Card, EmptyState } from '../../components/common/Card'
import { ErrorBanner } from '../../components/common/ErrorBanner'
import { LoadingScreen } from '../../components/common/Loading'
import { useAsync } from '../../hooks/useAsync'
import type { Nurse } from '../../types'

export function AdminNurses() {
  const nurses = useAsync<Nurse[]>(() => adminApi.nurses(), [])

  if (nurses.loading) return <LoadingScreen label="Loading nurses" />
  if (nurses.error)
    return <ErrorBanner message={nurses.error} onRetry={() => void nurses.reload()} />

  const rows = nurses.data ?? []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-navy-800">Nurses</h1>
        <p className="mt-1 text-sm text-slate-500">Field staff available for visit assignment.</p>
      </div>

      {rows.length === 0 ? (
        <EmptyState title="No nurses registered" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((nurse) => (
            <Card key={nurse.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold text-navy-800">{nurse.name}</h2>
                  <p className="text-sm text-slate-500">{nurse.credential}</p>
                </div>
                <Badge tone={nurse.verification_status === 'verified' ? 'success' : 'warning'}>
                  {nurse.verification_status}
                </Badge>
              </div>

              <dl className="mt-4 space-y-1.5 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Email</dt>
                  <dd className="truncate font-medium text-navy-800">{nurse.email}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Phone</dt>
                  <dd className="font-medium text-navy-800">{nurse.phone ?? '--'}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Open visits</dt>
                  <dd className="font-semibold tabular-nums text-navy-800">{nurse.open_visits ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Status</dt>
                  <dd className="font-medium capitalize text-navy-800">{nurse.status}</dd>
                </div>
              </dl>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
