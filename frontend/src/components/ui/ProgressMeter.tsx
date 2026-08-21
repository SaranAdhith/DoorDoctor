import { cn } from '../../lib/cn'

export type MeterTone = 'good' | 'watch' | 'attention' | 'critical' | 'neutral'

const FILL: Record<MeterTone, string> = {
  good: 'bg-status-good',
  watch: 'bg-status-watch',
  attention: 'bg-status-attention',
  critical: 'bg-status-critical',
  neutral: 'bg-navy-500',
}

export interface ProgressMeterProps {
  /** Current value, in the same unit as `max`. */
  value: number
  max?: number
  tone?: MeterTone
  /** Announced to assistive tech in place of a bare percentage. */
  label: string
  /** Renders the label and the formatted value above the track. */
  showLabel?: boolean
  valueText?: string
  className?: string
}

export function ProgressMeter({
  value,
  max = 100,
  tone = 'neutral',
  label,
  showLabel = false,
  valueText,
  className,
}: ProgressMeterProps) {
  const safeMax = max > 0 ? max : 1
  const pct = Math.max(0, Math.min(100, (value / safeMax) * 100))

  return (
    <div className={className}>
      {showLabel && (
        <div className="mb-1.5 flex items-baseline justify-between gap-3">
          <span className="text-small font-medium text-text-secondary">{label}</span>
          {valueText && <span className="tnum text-small font-semibold text-text-primary">{valueText}</span>}
        </div>
      )}
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-surface-sunken"
        role="meter"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={safeMax}
        aria-valuetext={valueText}
        aria-label={label}
      >
        <div
          className={cn('h-full rounded-full transition-all', FILL[tone])}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
