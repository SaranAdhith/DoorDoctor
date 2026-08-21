import { visitsApi } from '../../api/visits'
import { useAuth } from '../../auth/AuthContext'
import { VisitCard } from '../../components/cards/VisitCard'
import { EmptyState } from '../../components/common/Card'
import { ErrorBanner } from '../../components/common/ErrorBanner'
import { LoadingScreen } from '../../components/common/Loading'
import { useAsync } from '../../hooks/useAsync'
import type { Visit } from '../../types'

const ACTION_LABELS: Record<string, string> = {
  scheduled: 'Start Visit',
  in_progress: 'Continue Visit',
  completed: 'View Visit',
  missed: 'View Visit',
  cancelled: 'View Visit',
}

export function NurseVisits() {
  const { user } = useAuth()
  const today = useAsync<Visit[]>(() => visitsApi.today(), [])
  const all = useAsync<Visit[]>(() => visitsApi.list(), [])

  if (today.loading) return <LoadingScreen label="Loading your visits" />
  if (today.error) return <ErrorBanner message={today.error} onRetry={() => void today.reload()} />

  const visits = today.data ?? []
  const open = visits.filter((visit) => visit.status !== 'completed')
  const completedToday = (all.data ?? []).filter((visit) => visit.status === 'completed').slice(0, 5)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-navy-800">Today's Visits</h1>
        <p className="mt-1 text-sm text-slate-500">
          {user?.name} · {open.length} open {open.length === 1 ? 'visit' : 'visits'}
        </p>
      </div>

      <section className="space-y-3">
        {open.length === 0 ? (
          <EmptyState
            title="No open visits"
            description="Assigned visits appear here as soon as an admin schedules them."
          />
        ) : (
          open.map((visit) => (
            <VisitCard
              key={visit.id}
              visit={visit}
              actionLabel={ACTION_LABELS[visit.status]}
              to={`/nurse/visits/${visit.id}`}
            />
          ))
        )}
      </section>

      {completedToday.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Recently completed</h2>
          {completedToday.map((visit) => (
            <VisitCard key={visit.id} visit={visit} actionLabel="View Visit" to={`/nurse/visits/${visit.id}`} />
          ))}
        </section>
      )}
    </div>
  )
}
