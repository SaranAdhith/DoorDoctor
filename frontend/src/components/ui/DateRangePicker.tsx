import { cn } from '../../lib/cn'
import { Input } from './Input'

export interface DateRange {
  /** `YYYY-MM-DD`, or empty for an open end. */
  from: string
  to: string
}

export interface DateRangePickerProps {
  value: DateRange
  onChange: (range: DateRange) => void
  /** Announced as the purpose of the pair. */
  legend: string
  min?: string
  max?: string
  className?: string
}

/**
 * Two native date inputs bound as one range. Native rather than a custom
 * calendar so mobile gets the platform picker and keyboard entry keeps working.
 */
export function DateRangePicker({
  value,
  onChange,
  legend,
  min,
  max,
  className,
}: DateRangePickerProps) {
  // An end date before the start date is not expressible: each input bounds the other.
  return (
    <fieldset className={cn('w-full', className)}>
      <legend className="mb-2 text-small font-medium text-text-primary">{legend}</legend>
      <div className="grid gap-3 sm:grid-cols-2">
        <Input
          label="From"
          type="date"
          value={value.from}
          min={min}
          max={value.to || max}
          onChange={(event) => onChange({ ...value, from: event.target.value })}
        />
        <Input
          label="To"
          type="date"
          value={value.to}
          min={value.from || min}
          max={max}
          onChange={(event) => onChange({ ...value, to: event.target.value })}
        />
      </div>
    </fieldset>
  )
}
