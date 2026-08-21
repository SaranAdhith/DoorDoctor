import { cn } from '../../lib/cn'
import { METRIC_UNITS, formatRelative } from '../../lib/format'
import { evaluateReading, readingStateLabel, thresholdText, type ReadingState } from '../../lib/vitals'
import type { Threshold, VitalMetric } from '../../types'

interface Props {
  label: string
  metric: VitalMetric
  value: string
  numericValue: number | null
  thresholds: Threshold[]
  recordedAt?: string | null
  /** Overrides the computed state (blood pressure combines two metrics). */
  stateOverride?: ReadingState
  unitOverride?: string
}

const STATE_STYLES: Record<ReadingState, { dot: string; text: string; ring: string }> = {
  normal: { dot: 'bg-status-good', text: 'text-status-good', ring: 'ring-border-subtle' },
  high: { dot: 'bg-status-critical', text: 'text-status-critical', ring: 'ring-status-critical-border' },
  low: { dot: 'bg-status-watch', text: 'text-status-watch', ring: 'ring-status-watch-border' },
  unknown: { dot: 'bg-border-strong', text: 'text-text-muted', ring: 'ring-border-subtle' },
}

export function VitalCard({
  label,
  metric,
  value,
  numericValue,
  thresholds,
  recordedAt,
  stateOverride,
  unitOverride,
}: Props) {
  const state = stateOverride ?? evaluateReading(metric, numericValue, thresholds)
  const styles = STATE_STYLES[state]
  const range = thresholdText(metric, thresholds)

  return (
    <article className={cn('rounded-2xl bg-surface-raised p-4 shadow-card ring-1', styles.ring)}>
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-caption font-semibold uppercase tracking-wide text-text-secondary">
          {label}
        </h3>
        <span className={cn('h-2.5 w-2.5 shrink-0 rounded-full', styles.dot)} aria-hidden="true" />
      </div>

      <p className="mt-2 flex items-baseline gap-1.5">
        <span className="tnum text-h1 font-bold text-text-primary">{value}</span>
        <span className="text-caption font-medium text-text-muted">
          {unitOverride ?? METRIC_UNITS[metric]}
        </span>
      </p>

      <p className={cn('mt-1 text-caption font-semibold', styles.text)}>{readingStateLabel(state)}</p>

      <p className="mt-2 border-t border-border-subtle pt-2 text-caption text-text-muted">
        {range ? `Range ${range}` : 'No threshold set'}
        {recordedAt ? ` · ${formatRelative(recordedAt)}` : ''}
      </p>
    </article>
  )
}
