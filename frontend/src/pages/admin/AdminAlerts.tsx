import { useState } from 'react'

import { alertsApi } from '../../api/alerts'
import { ApiError } from '../../api/client'
import { AlertCard } from '../../components/alerts/AlertCard'
import { useAsync } from '../../hooks/useAsync'
import { breachContext, breachLabel, breachValue } from '../../lib/breach'
import { formatDateTime } from '../../lib/format'
import type { Alert, AlertDetail } from '../../types'
import { Button, Card, EmptyState, ErrorState, LoadingScreen, useToast } from '../../components/ui'

export function AdminAlerts() {
  const { notify } = useToast()
  const alerts = useAsync<Alert[]>(() => alertsApi.list(), [])
  const [selected, setSelected] = useState<AlertDetail | null>(null)
  const [busy, setBusy] = useState(false)

  if (alerts.loading) return <LoadingScreen label="Loading alerts" />
  if (alerts.error) return <ErrorState message={alerts.error} onRetry={() => void alerts.reload()} />

  const rows = alerts.data ?? []
  const active = rows.filter((alert) => alert.status !== 'resolved')
  const resolved = rows.filter((alert) => alert.status === 'resolved')

  async function open(alertId: number) {
    try {
      setSelected(await alertsApi.get(alertId))
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'Could not open the alert.', 'error')
    }
  }

  async function act(alertId: number, action: 'acknowledge' | 'resolve') {
    setBusy(true)
    try {
      await (action === 'acknowledge' ? alertsApi.acknowledge(alertId) : alertsApi.resolve(alertId))
      notify(action === 'acknowledge' ? 'Alert acknowledged.' : 'Alert resolved.', 'success')
      await alerts.reload({ quiet: true })
      if (selected?.id === alertId) setSelected(await alertsApi.get(alertId))
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'Could not update the alert.', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 font-bold text-text-primary">Alerts</h1>
        <p className="mt-1 text-small text-text-secondary">
          Threshold events raised during nurse visits. Acknowledge, then resolve once handled.
        </p>
      </div>

      {selected && (
        <Card
          title="Alert detail"
          action={
            <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>
              Close
            </Button>
          }
        >
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Detail label="Patient" value={selected.patient_name ?? '--'} />
            <Detail label="Recorded by" value={selected.nurse_name ?? '--'} />
            <Detail label="Detected" value={formatDateTime(selected.created_at)} />
            <Detail label="Status" value={selected.status} className="capitalize" />
          </dl>

          <p className="mt-4 text-small text-text-secondary">{selected.message}</p>

          <ul className="mt-3 space-y-1.5">
            {selected.breached_parameters.map((breach, index) => (
              <li
                key={`${breach.metric}-${index}`}
                className="flex flex-wrap items-baseline justify-between gap-x-3 rounded-xl bg-surface px-3 py-2 text-small"
              >
                <span className="font-medium text-text-primary">{breachLabel(breach)}</span>
                <span className="tnum text-text-secondary">
                  Reading{' '}
                  <span className="font-semibold text-text-primary">{breachValue(breach)}</span>
                  {breachContext(breach) && <> · {breachContext(breach)}</>}
                </span>
              </li>
            ))}
          </ul>

          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              variant="ghost"
              disabled={busy || selected.status !== 'active'}
              onClick={() => void act(selected.id, 'acknowledge')}
            >
              Acknowledge
            </Button>
            <Button
              disabled={busy || selected.status === 'resolved'}
              onClick={() => void act(selected.id, 'resolve')}
            >
              Resolve
            </Button>
          </div>

          <p className="mt-4 text-caption text-text-secondary">Monitoring alert, not a medical diagnosis.</p>
        </Card>
      )}

      <section className="space-y-3">
        <h2 className="text-caption font-semibold uppercase tracking-wide text-text-secondary">Active</h2>
        {active.length === 0 ? (
          <EmptyState title="No active alerts" description="Nothing needs attention right now." />
        ) : (
          active.map((alert) => (
            <AlertCard key={alert.id} alert={alert}>
              <Button variant="ghost" size="sm" onClick={() => void open(alert.id)}>
                View details
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={busy || alert.status !== 'active'}
                onClick={() => void act(alert.id, 'acknowledge')}
              >
                Acknowledge
              </Button>
              <Button size="sm" disabled={busy} onClick={() => void act(alert.id, 'resolve')}>
                Resolve
              </Button>
            </AlertCard>
          ))
        )}
      </section>

      {resolved.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-caption font-semibold uppercase tracking-wide text-text-secondary">Resolved</h2>
          {resolved.map((alert) => (
            <AlertCard key={alert.id} alert={alert} />
          ))}
        </section>
      )}
    </div>
  )
}

function Detail({ label, value, className = '' }: { label: string; value: string; className?: string }) {
  return (
    <div>
      <dt className="text-caption font-semibold uppercase tracking-wide text-text-secondary">{label}</dt>
      <dd className={`mt-0.5 text-small font-medium text-text-primary ${className}`}>{value}</dd>
    </div>
  )
}
