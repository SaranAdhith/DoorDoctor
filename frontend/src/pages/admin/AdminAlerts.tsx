import { useState } from 'react'

import { alertsApi } from '../../api/alerts'
import { adminOpsApi } from '../../api/trust'
import { ApiError } from '../../api/client'
import { AlertCard } from '../../components/alerts/AlertCard'
import { useAsync } from '../../hooks/useAsync'
import { breachContext, breachLabel, breachValue } from '../../lib/breach'
import { formatDateTime } from '../../lib/format'
import type { Alert, AlertDetail, QueuedAlert } from '../../types'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingScreen,
  Modal,
  Textarea,
  useToast,
} from '../../components/ui'

/**
 * The alert queue (§4.17).
 *
 * The open list is **the server's queue**, not this page's sort: breached
 * first, then soonest deadline, which is the order an operator actually works
 * it. The SLA clock is stored on the alert, so an alert that breached last week
 * still says so after somebody edits the constants.
 *
 * Resolving asks for a note, because §8's journey 3 has always described the
 * admin resolving an alert *with a note* and until Phase 9 there was nowhere to
 * put one.
 */
function slaBadge(alert: QueuedAlert) {
  if (alert.breached) return <Badge tone="critical">Past deadline</Badge>
  if (alert.minutes_remaining == null) return null
  const minutes = alert.minutes_remaining
  return (
    <Badge tone={minutes <= 15 ? 'attention' : 'neutral'}>
      {minutes < 60 ? `${minutes} min left` : `${Math.round(minutes / 60)} hrs left`}
    </Badge>
  )
}

export function AdminAlerts() {
  const { notify } = useToast()
  const queue = useAsync<QueuedAlert[]>(() => adminOpsApi.alertQueue(), [])
  const alerts = useAsync<Alert[]>(() => alertsApi.list('resolved'), [])
  const [selected, setSelected] = useState<AlertDetail | null>(null)
  const [resolving, setResolving] = useState<number | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  if (queue.loading) return <LoadingScreen label="Loading alerts" />
  if (queue.error) return <ErrorState message={queue.error} onRetry={() => void queue.reload()} />

  const active = queue.data ?? []
  const resolved = alerts.data ?? []

  async function open(alertId: number) {
    try {
      setSelected(await alertsApi.get(alertId))
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'Could not open the alert.', 'error')
    }
  }

  async function act(alertId: number, action: 'acknowledge' | 'resolve', resolutionNote?: string) {
    setBusy(true)
    try {
      await (action === 'acknowledge'
        ? alertsApi.acknowledge(alertId)
        : alertsApi.resolve(alertId, resolutionNote ?? null))
      notify(action === 'acknowledge' ? 'Alert acknowledged.' : 'Alert resolved.', 'success')
      await Promise.all([queue.reload({ quiet: true }), alerts.reload({ quiet: true })])
      if (selected?.id === alertId) setSelected(await alertsApi.get(alertId))
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'Could not update the alert.', 'error')
    } finally {
      setBusy(false)
      setResolving(null)
      setNote('')
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
              onClick={() => setResolving(selected.id)}
            >
              Resolve
            </Button>
          </div>

          <p className="mt-4 text-caption text-text-secondary">Monitoring alert, not a medical diagnosis.</p>
        </Card>
      )}

      <section className="space-y-3">
        <h2 className="text-caption font-semibold uppercase tracking-wide text-text-secondary">
          Open — breached first, then soonest due
        </h2>
        {active.length === 0 ? (
          <EmptyState title="No open alerts" description="Nothing needs attention right now." />
        ) : (
          active.map((alert) => (
            <AlertCard key={alert.id} alert={alert}>
              <span className="mr-auto flex items-center gap-2">
                <span className="text-small text-text-secondary">{alert.patient_name}</span>
                {slaBadge(alert)}
              </span>
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
              <Button size="sm" disabled={busy} onClick={() => setResolving(alert.id)}>
                Resolve
              </Button>
            </AlertCard>
          ))
        )}
      </section>

      <Modal
        open={resolving !== null}
        onClose={() => setResolving(null)}
        title="Resolve this alert"
      >
        <div className="space-y-4">
          <p className="text-small text-text-secondary">
            What was done about it? The family sees this on their alerts page.
          </p>
          <Textarea
            label="Resolution note"
            hint="Optional, but it is the only record of what happened."
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={3}
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setResolving(null)}>
              Cancel
            </Button>
            <Button
              disabled={busy}
              onClick={() => resolving !== null && void act(resolving, 'resolve', note.trim())}
            >
              {busy ? 'Resolving…' : 'Resolve'}
            </Button>
          </div>
        </div>
      </Modal>

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
