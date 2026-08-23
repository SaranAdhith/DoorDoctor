import { UsersRound } from 'lucide-react'

import { careApi } from '../../api/clinical'
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  LoadingScreen,
  ProgressMeter,
} from '../../components/ui'
import type { MeterTone } from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import type { CareManager } from '../../types'

/**
 * The care manager roster and its caseloads (§4.4).
 *
 * The capacity on each card is the **recorded** ratio — 1:20 shared, 1:10
 * dedicated — served from `core/pricing.py` rather than restated here. That
 * matters on this screen more than most: a roster page that showed a made-up
 * capacity would look exactly like one that showed the real one.
 */

function loadTone(manager: CareManager): MeterTone {
  if (manager.at_capacity) return 'critical'
  if (manager.available <= 2) return 'watch'
  return 'good'
}

export function AdminCare() {
  const managers = useAsync<CareManager[]>(() => careApi.managers(), [])

  const total = managers.data?.reduce((sum, manager) => sum + manager.caseload, 0) ?? 0
  const capacity = managers.data?.reduce((sum, manager) => sum + manager.capacity, 0) ?? 0

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-h1 font-semibold text-text-primary">Care managers</h1>
        <p className="text-small text-text-secondary">
          Who carries which caseload, against the ratio each plan promises.
        </p>
      </header>

      {managers.loading && <LoadingScreen label="Loading care managers" />}
      {managers.error && <ErrorState message={managers.error} onRetry={() => managers.reload()} />}

      {managers.data?.length === 0 && (
        <EmptyState
          icon={<UsersRound aria-hidden />}
          title="No care managers yet"
          description="An admin account becomes a care manager once a caseload is assigned to it."
        />
      )}

      {managers.data && managers.data.length > 0 && (
        <>
          <Card>
            <p className="text-body text-text-primary">
              <span className="tnum font-semibold">{total}</span> patients across{' '}
              <span className="tnum">{managers.data.length}</span> care managers, against a combined
              capacity of <span className="tnum">{capacity}</span>.
            </p>
            <p className="mt-1 text-caption text-text-muted">
              A shared care manager carries up to 20 patients and a dedicated one up to 10. Those
              ratios come from the plan, and assignment past them is refused.
            </p>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2">
            {managers.data.map((manager) => (
              <Card
                key={manager.id}
                title={manager.name}
                description={manager.languages || undefined}
                action={
                  <Badge tone={manager.kind === 'dedicated' ? 'good' : 'neutral'}>
                    {manager.kind === 'dedicated' ? 'Dedicated' : 'Shared'}
                  </Badge>
                }
              >
                <ProgressMeter
                  label={`${manager.name}'s caseload`}
                  showLabel={false}
                  value={manager.caseload}
                  max={manager.capacity}
                  tone={loadTone(manager)}
                />
                <p className="mt-2 text-small text-text-secondary">
                  <span className="tnum font-medium">{manager.caseload}</span> of{' '}
                  <span className="tnum">{manager.capacity}</span> patients
                  {manager.at_capacity ? (
                    <span className="text-status-critical"> · at capacity</span>
                  ) : (
                    <span className="text-text-muted"> · room for {manager.available} more</span>
                  )}
                </p>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
