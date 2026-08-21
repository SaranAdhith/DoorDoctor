import { useState } from 'react'

import { alertsApi } from '../../api/alerts'
import { ApiError } from '../../api/client'
import { AlertCard } from '../../components/alerts/AlertCard'
import { Card, EmptyState } from '../../components/common/Card'
import { ErrorBanner } from '../../components/common/ErrorBanner'
import { LoadingScreen } from '../../components/common/Loading'
import { useToast } from '../../components/common/Toast'
import { useAsync } from '../../hooks/useAsync'
import { METRIC_LABELS, formatDateTime, formatNumber } from '../../lib/format'
import type { Alert, AlertDetail } from '../../types'

export function CoordinatorAlerts() {
  const { notify } = useToast()
  const alerts = useAsync<Alert[]>(() => alertsApi.list(), [])
  const [selected, setSelected] = useState<AlertDetail | null>(null)
  const [busy, setBusy] = useState(false)

  if (alerts.loading) return <LoadingScreen label="Loading alerts" />
  if (alerts.error) return <ErrorBanner message={alerts.error} onRetry={() => void alerts.reload()} />

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
        <h1 className="text-2xl font-bold text-navy-800">Alerts</h1>
        <p className="mt-1 text-sm text-slate-500">
          Threshold events raised during caregiver visits. Acknowledge, then resolve once handled.
        </p>
      </div>

      {selected && (
        <Card title="Alert detail" action={
          <button type="button" onClick={() => setSelected(null)} className="text-xs font-semibold text-slate-500 hover:underline">
            Close
          </button>
        }>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Detail label="Patient" value={selected.patient_name ?? '--'} />
            <Detail label="Recorded by" value={selected.caregiver_name ?? '--'} />
            <Detail label="Detected" value={formatDateTime(selected.created_at)} />
            <Detail label="Status" value={selected.status} className="capitalize" />
          </dl>

          <p className="mt-4 text-sm text-slate-600">{selected.message}</p>

          <ul className="mt-3 space-y-1.5">
            {selected.breached_parameters.map((breach) => (
              <li
                key={breach.metric}
                className="flex flex-wrap items-baseline justify-between gap-x-3 rounded-xl bg-slate-50 px-3 py-2 text-sm"
              >
                <span className="font-medium text-navy-800">
                  {METRIC_LABELS[breach.metric] ?? breach.metric}
                </span>
                <span className="tabular-nums text-slate-600">
                  Reading{' '}
                  <span className="font-semibold text-navy-800">
                    {formatNumber(breach.value)}
                    {breach.unit}
                  </span>{' '}
                  · configured threshold {formatNumber(breach.threshold)}
                  {breach.unit}
                </span>
              </li>
            ))}
          </ul>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-ghost"
              disabled={busy || selected.status !== 'active'}
              onClick={() => void act(selected.id, 'acknowledge')}
            >
              Acknowledge
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={busy || selected.status === 'resolved'}
              onClick={() => void act(selected.id, 'resolve')}
            >
              Resolve
            </button>
          </div>

          <p className="mt-4 text-xs text-slate-500">Monitoring alert - not a medical diagnosis.</p>
        </Card>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Active</h2>
        {active.length === 0 ? (
          <EmptyState title="No active alerts" description="Nothing needs attention right now." />
        ) : (
          active.map((alert) => (
            <AlertCard key={alert.id} alert={alert}>
              <button type="button" className="btn-ghost py-2 text-xs" onClick={() => void open(alert.id)}>
                View details
              </button>
              <button
                type="button"
                className="btn-ghost py-2 text-xs"
                disabled={busy || alert.status !== 'active'}
                onClick={() => void act(alert.id, 'acknowledge')}
              >
                Acknowledge
              </button>
              <button
                type="button"
                className="btn-primary py-2 text-xs"
                disabled={busy}
                onClick={() => void act(alert.id, 'resolve')}
              >
                Resolve
              </button>
            </AlertCard>
          ))
        )}
      </section>

      {resolved.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Resolved</h2>
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
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className={`mt-0.5 text-sm font-medium text-navy-800 ${className}`}>{value}</dd>
    </div>
  )
}
