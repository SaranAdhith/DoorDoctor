import { Link } from 'react-router-dom'

import { alertsApi } from '../../api/alerts'
import { adminApi } from '../../api/admin'
import { visitsApi } from '../../api/visits'
import { useAsync } from '../../hooks/useAsync'
import { formatRelative, formatTime } from '../../lib/format'
import { AlertStatusBadge, Card, EmptyState, ErrorState, LinkButton, LoadingScreen, SeverityBadge, StatTile, VisitStatusBadge } from '../../components/ui'

export function AdminDashboard() {
  const data = useAsync(async () => {
    const [summary, visits, alerts] = await Promise.all([
      adminApi.summary(),
      visitsApi.today(),
      alertsApi.list(),
    ])
    return { summary, visits, alerts }
  }, [])

  if (data.loading) return <LoadingScreen label="Loading operations" />
  if (data.error) return <ErrorState message={data.error} onRetry={() => void data.reload()} />
  if (!data.data) return null

  const { summary, visits, alerts } = data.data
  const activeAlerts = alerts.filter((alert) => alert.status !== 'resolved')

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-h1 font-bold text-text-primary">Operations Dashboard</h1>
          <p className="mt-1 text-small text-text-secondary">Care delivery across all DoorDoctor patients today.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <LinkButton to="/admin/visits" variant="accent">
            Schedule visit
          </LinkButton>
          <LinkButton to="/admin/alerts" variant="ghost">
            View alerts
          </LinkButton>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label="Total Patients" value={summary.patients} />
        <StatTile label="Active Nurses" value={summary.nurses} />
        <StatTile
          label="Today's Visits"
          value={summary.today_visits}
          hint={`${summary.completed_today} completed`}
        />
        <StatTile
          label="Active Alerts"
          value={summary.active_alerts}
          tone={summary.active_alerts > 0 ? 'critical' : 'good'}
          hint={summary.active_alerts > 0 ? 'Needs review' : 'All clear'}
        />
      </div>

      <Card
        title="Today's visits"
        action={
          <Link to="/admin/visits" className="text-caption font-semibold text-brand-600 hover:underline">
            Manage
          </Link>
        }
      >
        {visits.length === 0 ? (
          <EmptyState title="No visits scheduled for today" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[540px] text-small">
              <thead>
                <tr className="text-left text-caption uppercase tracking-wide text-text-secondary">
                  <th className="pb-2 pr-4 font-semibold">Time</th>
                  <th className="pb-2 pr-4 font-semibold">Patient</th>
                  <th className="pb-2 pr-4 font-semibold">Nurse</th>
                  <th className="pb-2 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visits.map((visit) => (
                  <tr key={visit.id}>
                    <td className="py-2.5 pr-4 font-medium tnum text-text-primary">
                      {formatTime(visit.scheduled_at)}
                    </td>
                    <td className="py-2.5 pr-4 text-text-primary">{visit.patient?.name ?? '--'}</td>
                    <td className="py-2.5 pr-4 text-text-primary">{visit.nurse?.name ?? 'Unassigned'}</td>
                    <td className="py-2.5">
                      <VisitStatusBadge status={visit.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card
        title="Active alerts"
        action={
          <Link to="/admin/alerts" className="text-caption font-semibold text-brand-600 hover:underline">
            Handle alerts
          </Link>
        }
      >
        {activeAlerts.length === 0 ? (
          <EmptyState title="No active alerts" description="Every recorded reading is within range." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-small">
              <thead>
                <tr className="text-left text-caption uppercase tracking-wide text-text-secondary">
                  <th className="pb-2 pr-4 font-semibold">Alert</th>
                  <th className="pb-2 pr-4 font-semibold">Severity</th>
                  <th className="pb-2 pr-4 font-semibold">Detected</th>
                  <th className="pb-2 pr-4 font-semibold">Status</th>
                  <th className="pb-2 font-semibold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {activeAlerts.map((alert) => (
                  <tr key={alert.id}>
                    <td className="py-2.5 pr-4 font-medium text-text-primary">{alert.title}</td>
                    <td className="py-2.5 pr-4">
                      <SeverityBadge severity={alert.severity} />
                    </td>
                    <td className="py-2.5 pr-4 text-text-secondary">{formatRelative(alert.created_at)}</td>
                    <td className="py-2.5 pr-4">
                      <AlertStatusBadge status={alert.status} />
                    </td>
                    <td className="py-2.5">
                      <Link
                        to="/admin/alerts"
                        className="text-caption font-semibold text-brand-600 hover:underline"
                      >
                        Review
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
