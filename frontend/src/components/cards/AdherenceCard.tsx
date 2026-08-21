import type { Adherence } from '../../types'
import { Card, ProgressMeter } from '../ui'

function tone(percentage: number) {
  if (percentage >= 90) return 'good' as const
  if (percentage >= 75) return 'watch' as const
  return 'attention' as const
}

export function AdherenceCard({ adherence }: { adherence: Adherence }) {
  const hasData = adherence.percentage !== null
  const pct = adherence.percentage ?? 0

  return (
    <Card title="Medicines taken on time">
      <div className="flex items-end gap-4">
        {/* No data is shown as "No data", never 0% — that would imply missed doses. */}
        {hasData ? (
          <p className="tnum text-display font-bold text-text-primary">{pct}%</p>
        ) : (
          <p className="text-h1 font-semibold text-text-muted">No data</p>
        )}
        {hasData && (
          <p className="pb-1.5 text-caption text-text-secondary">
            {adherence.administered} of {adherence.total} logged doses
          </p>
        )}
      </div>

      {hasData && (
        <ProgressMeter
          className="mt-3"
          value={pct}
          tone={tone(pct)}
          label="Doses taken on time"
          valueText={`${pct}%`}
        />
      )}

      <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-xl bg-status-good-bg py-2">
          <dt className="text-caption font-semibold uppercase tracking-wide text-status-good">Taken</dt>
          <dd className="tnum text-h2 font-bold text-status-good">{adherence.administered}</dd>
        </div>
        <div className="rounded-xl bg-status-watch-bg py-2">
          <dt className="text-caption font-semibold uppercase tracking-wide text-status-watch">
            Skipped
          </dt>
          <dd className="tnum text-h2 font-bold text-status-watch">{adherence.skipped}</dd>
        </div>
        <div className="rounded-xl bg-status-critical-bg py-2">
          <dt className="text-caption font-semibold uppercase tracking-wide text-status-critical">
            Refused
          </dt>
          <dd className="tnum text-h2 font-bold text-status-critical">{adherence.refused}</dd>
        </div>
      </dl>
    </Card>
  )
}
