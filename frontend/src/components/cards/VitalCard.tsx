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
  normal: { dot: 'bg-brand-500', text: 'text-brand-700', ring: 'ring-slate-200/80' },
  high: { dot: 'bg-critical-500', text: 'text-critical-700', ring: 'ring-critical-200' },
  low: { dot: 'bg-warning-500', text: 'text-warning-700', ring: 'ring-warning-200' },
  unknown: { dot: 'bg-slate-300', text: 'text-slate-500', ring: 'ring-slate-200/80' },
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
    <article className={`rounded-2xl bg-white p-4 shadow-card ring-1 ${styles.ring}`}>
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</h3>
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${styles.dot}`} aria-hidden="true" />
      </div>

      <p className="mt-2 flex items-baseline gap-1.5">
        <span className="text-2xl font-bold tabular-nums text-navy-800">{value}</span>
        <span className="text-xs font-medium text-slate-500">{unitOverride ?? METRIC_UNITS[metric]}</span>
      </p>

      <p className={`mt-1 text-xs font-semibold ${styles.text}`}>{readingStateLabel(state)}</p>

      <p className="mt-2 border-t border-slate-100 pt-2 text-[11px] text-slate-400">
        {range ? `Range ${range}` : 'No threshold set'}
        {recordedAt ? ` · ${formatRelative(recordedAt)}` : ''}
      </p>
    </article>
  )
}
