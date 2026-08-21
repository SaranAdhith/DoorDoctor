import { useSearchParams } from 'react-router-dom'

import { alertsApi } from '../../api/alerts'
import { AlertCard } from '../../components/alerts/AlertCard'
import { Card, EmptyState } from '../../components/common/Card'
import { ErrorBanner } from '../../components/common/ErrorBanner'
import { LoadingScreen } from '../../components/common/Loading'
import { useAsync } from '../../hooks/useAsync'
import { METRIC_LABELS, formatDateTime, formatNumber } from '../../lib/format'
import type { Alert } from '../../types'

export function FamilyAlerts() {
  const [searchParams] = useSearchParams()
  const highlightedId = Number(searchParams.get('alert')) || null

  const alerts = useAsync<Alert[]>(() => alertsApi.list(), [])
  const detail = useAsync(
    () => (highlightedId ? alertsApi.get(highlightedId) : Promise.resolve(null)),
    [highlightedId],
  )

  if (alerts.loading) return <LoadingScreen label="Loading alerts" />
  if (alerts.error) return <ErrorBanner message={alerts.error} onRetry={() => void alerts.reload()} />

  const items = alerts.data ?? []
  const active = items.filter((alert) => alert.status !== 'resolved')
  const history = items.filter((alert) => alert.status === 'resolved')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-navy-800">Alerts</h1>
        <p className="mt-1 text-sm text-slate-500">
          Monitoring alerts - not medical diagnoses. The care team is notified when one is raised.
        </p>
      </div>

      {detail.data && (
        <Card title="Alert detail">
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Detail label="Alert" value={detail.data.title} />
            <Detail label="Patient" value={detail.data.patient_name ?? '--'} />
            <Detail label="Detected" value={formatDateTime(detail.data.created_at)} />
            <Detail label="Recorded by" value={detail.data.caregiver_name ?? '--'} />
            <Detail label="Severity" value={detail.data.severity} className="capitalize" />
            <Detail label="Status" value={detail.data.status} className="capitalize" />
          </dl>

          <div className="mt-4 space-y-2">
            {detail.data.breached_parameters.map((breach) => (
              <p key={breach.metric} className="rounded-xl bg-slate-50 px-3 py-2 text-sm">
                <span className="font-semibold text-navy-800">
                  {METRIC_LABELS[breach.metric] ?? breach.metric}
                </span>{' '}
                reading{' '}
                <span className="font-semibold tabular-nums">
                  {formatNumber(breach.value)}
                  {breach.unit}
                </span>{' '}
                is {breach.direction} the configured threshold of{' '}
                <span className="font-semibold tabular-nums">
                  {formatNumber(breach.threshold)}
                  {breach.unit}
                </span>
                .
              </p>
            ))}
          </div>

          <p className="mt-4 rounded-xl bg-navy-50 px-3 py-2 text-xs font-medium text-navy-700">
            Monitoring alert - not a medical diagnosis. Your care coordinator reviews and resolves alerts.
          </p>
        </Card>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Active</h2>
        {active.length === 0 ? (
          <EmptyState title="No active alerts" description="Everything is within the configured range." />
        ) : (
          active.map((alert) => <AlertCard key={alert.id} alert={alert} />)
        )}
      </section>

      {history.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Resolved</h2>
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
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className={`mt-0.5 text-sm font-medium text-navy-800 ${className}`}>{value}</dd>
    </div>
  )
}
