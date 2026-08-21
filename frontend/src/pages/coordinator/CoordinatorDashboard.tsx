import { Link } from 'react-router-dom'

import { alertsApi } from '../../api/alerts'
import { coordinatorApi } from '../../api/coordinator'
import { visitsApi } from '../../api/visits'
import { StatCard } from '../../components/cards/StatCard'
import { AlertStatusBadge, SeverityBadge, VisitStatusBadge } from '../../components/common/Badge'
import { Card, EmptyState } from '../../components/common/Card'
import { ErrorBanner } from '../../components/common/ErrorBanner'
import { LoadingScreen } from '../../components/common/Loading'
import { useAsync } from '../../hooks/useAsync'
import { formatRelative, formatTime } from '../../lib/format'

export function CoordinatorDashboard() {
  const data = useAsync(async () => {
    const [summary, visits, alerts] = await Promise.all([
      coordinatorApi.summary(),
      visitsApi.today(),
      alertsApi.list(),
    ])
    return { summary, visits, alerts }
  }, [])

  if (data.loading) return <LoadingScreen label="Loading operations" />
  if (data.error) return <ErrorBanner message={data.error} onRetry={() => void data.reload()} />
  if (!data.data) return null

  const { summary, visits, alerts } = data.data
  const activeAlerts = alerts.filter((alert) => alert.status !== 'resolved')

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-navy-800">Operations Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">Care delivery across all DoorDoctor patients today.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/coordinator/visits" className="btn-accent">
            Schedule visit
          </Link>
          <Link to="/coordinator/alerts" className="btn-ghost">
            View alerts
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Total Patients" value={summary.patients} />
        <StatCard label="Active Caregivers" value={summary.caregivers} />
        <StatCard
          label="Today's Visits"
          value={summary.today_visits}
          hint={`${summary.completed_today} completed`}
        />
        <StatCard
          label="Active Alerts"
          value={summary.active_alerts}
          tone={summary.active_alerts > 0 ? 'critical' : 'success'}
          hint={summary.active_alerts > 0 ? 'Needs review' : 'All clear'}
        />
      </div>

      <Card
        title="Today's visits"
        action={
          <Link to="/coordinator/visits" className="text-xs font-semibold text-brand-600 hover:underline">
            Manage
          </Link>
        }
      >
        {visits.length === 0 ? (
          <EmptyState title="No visits scheduled for today" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[540px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="pb-2 pr-4 font-semibold">Time</th>
                  <th className="pb-2 pr-4 font-semibold">Patient</th>
                  <th className="pb-2 pr-4 font-semibold">Caregiver</th>
                  <th className="pb-2 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visits.map((visit) => (
                  <tr key={visit.id}>
                    <td className="py-2.5 pr-4 font-medium tabular-nums text-navy-800">
                      {formatTime(visit.scheduled_at)}
                    </td>
                    <td className="py-2.5 pr-4 text-slate-700">{visit.patient?.name ?? '--'}</td>
                    <td className="py-2.5 pr-4 text-slate-700">{visit.caregiver?.name ?? 'Unassigned'}</td>
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
          <Link to="/coordinator/alerts" className="text-xs font-semibold text-brand-600 hover:underline">
            Handle alerts
          </Link>
        }
      >
        {activeAlerts.length === 0 ? (
          <EmptyState title="No active alerts" description="Every recorded reading is within range." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
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
                    <td className="py-2.5 pr-4 font-medium text-navy-800">{alert.title}</td>
                    <td className="py-2.5 pr-4">
                      <SeverityBadge severity={alert.severity} />
                    </td>
                    <td className="py-2.5 pr-4 text-slate-600">{formatRelative(alert.created_at)}</td>
                    <td className="py-2.5 pr-4">
                      <AlertStatusBadge status={alert.status} />
                    </td>
                    <td className="py-2.5">
                      <Link
                        to="/coordinator/alerts"
                        className="text-xs font-semibold text-brand-600 hover:underline"
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
