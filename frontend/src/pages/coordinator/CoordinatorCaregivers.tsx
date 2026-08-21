import { coordinatorApi } from '../../api/coordinator'
import { Badge } from '../../components/common/Badge'
import { Card, EmptyState } from '../../components/common/Card'
import { ErrorBanner } from '../../components/common/ErrorBanner'
import { LoadingScreen } from '../../components/common/Loading'
import { useAsync } from '../../hooks/useAsync'
import type { Caregiver } from '../../types'

export function CoordinatorCaregivers() {
  const caregivers = useAsync<Caregiver[]>(() => coordinatorApi.caregivers(), [])

  if (caregivers.loading) return <LoadingScreen label="Loading caregivers" />
  if (caregivers.error)
    return <ErrorBanner message={caregivers.error} onRetry={() => void caregivers.reload()} />

  const rows = caregivers.data ?? []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-navy-800">Caregivers</h1>
        <p className="mt-1 text-sm text-slate-500">Field staff available for visit assignment.</p>
      </div>

      {rows.length === 0 ? (
        <EmptyState title="No caregivers registered" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((caregiver) => (
            <Card key={caregiver.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold text-navy-800">{caregiver.name}</h2>
                  <p className="text-sm text-slate-500">{caregiver.credential}</p>
                </div>
                <Badge tone={caregiver.verification_status === 'verified' ? 'success' : 'warning'}>
                  {caregiver.verification_status}
                </Badge>
              </div>

              <dl className="mt-4 space-y-1.5 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Email</dt>
                  <dd className="truncate font-medium text-navy-800">{caregiver.email}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Phone</dt>
                  <dd className="font-medium text-navy-800">{caregiver.phone ?? '--'}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Open visits</dt>
                  <dd className="font-semibold tabular-nums text-navy-800">{caregiver.open_visits ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Status</dt>
                  <dd className="font-medium capitalize text-navy-800">{caregiver.status}</dd>
                </div>
              </dl>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
