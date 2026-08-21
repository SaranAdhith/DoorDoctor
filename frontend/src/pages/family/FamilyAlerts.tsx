import { useSearchParams } from 'react-router-dom'

import { alertsApi } from '../../api/alerts'
import { AlertCard } from '../../components/alerts/AlertCard'
import { useAsync } from '../../hooks/useAsync'
import { METRIC_LABELS, formatDateTime, formatNumber } from '../../lib/format'
import type { Alert } from '../../types'
import { Card, EmptyState, ErrorState, LoadingScreen } from '../../components/ui'

export function FamilyAlerts() {
  const [searchParams] = useSearchParams()
  const highlightedId = Number(searchParams.get('alert')) || null

  const alerts = useAsync<Alert[]>(() => alertsApi.list(), [])
  const detail = useAsync(
    () => (highlightedId ? alertsApi.get(highlightedId) : Promise.resolve(null)),
    [highlightedId],
  )

  if (alerts.loading) return <LoadingScreen label="Loading alerts" />
  if (alerts.error) return <ErrorState message={alerts.error} onRetry={() => void alerts.reload()} />

  const items = alerts.data ?? []
  const active = items.filter((alert) => alert.status !== 'resolved')
  const history = items.filter((alert) => alert.status === 'resolved')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 font-bold text-text-primary">Alerts</h1>
        <p className="mt-1 text-small text-text-secondary">
          Monitoring alerts - not medical diagnoses. The care team is notified when one is raised.
        </p>
      </div>

      {detail.data && (
        <Card title="Alert detail">
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Detail label="Alert" value={detail.data.title} />
            <Detail label="Patient" value={detail.data.patient_name ?? '--'} />
            <Detail label="Detected" value={formatDateTime(detail.data.created_at)} />
            <Detail label="Recorded by" value={detail.data.nurse_name ?? '--'} />
            <Detail label="Severity" value={detail.data.severity} className="capitalize" />
            <Detail label="Status" value={detail.data.status} className="capitalize" />
          </dl>

          <div className="mt-4 space-y-2">
            {detail.data.breached_parameters.map((breach) => (
              <p key={breach.metric} className="rounded-xl bg-surface px-3 py-2 text-small">
                <span className="font-semibold text-text-primary">
                  {METRIC_LABELS[breach.metric] ?? breach.metric}
                </span>{' '}
                reading{' '}
                <span className="font-semibold tnum">
                  {formatNumber(breach.value)}
                  {breach.unit}
                </span>{' '}
                is {breach.direction} the configured threshold of{' '}
                <span className="font-semibold tnum">
                  {formatNumber(breach.threshold)}
                  {breach.unit}
                </span>
                .
              </p>
            ))}
          </div>

          <p className="mt-4 rounded-xl bg-navy-50 px-3 py-2 text-caption font-medium text-navy-700">
            Monitoring alert - not a medical diagnosis. Your DoorDoctor care team reviews and resolves alerts.
          </p>
        </Card>
      )}

      <section className="space-y-3">
        <h2 className="text-small font-semibold uppercase tracking-wide text-text-secondary">Active</h2>
        {active.length === 0 ? (
          <EmptyState title="No active alerts" description="Everything is within the configured range." />
        ) : (
          active.map((alert) => <AlertCard key={alert.id} alert={alert} />)
        )}
      </section>

      {history.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-small font-semibold uppercase tracking-wide text-text-secondary">Resolved</h2>
          {history.map((alert) => (
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
