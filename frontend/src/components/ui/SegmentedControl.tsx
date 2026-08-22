import { useRef, type KeyboardEvent } from 'react'

import { cn } from '../../lib/cn'

export interface Segment<T extends string> {
  value: T
  label: string
}

export interface SegmentedControlProps<T extends string> {
  legend: string
  value: T
  options: ReadonlyArray<Segment<T>>
  onChange: (value: T) => void
  /** Visually hides the legend but keeps it announced. */
  hideLegend?: boolean
  className?: string
}

/**
 * A one-of-N picker rendered as adjacent segments.
 *
 * It is a radio group, so it behaves like one: a single tab stop, arrow keys to
 * move between segments, Home/End to jump. Three tabbable buttons with
 * `role="radio"` would announce correctly and then not respond to the keys a
 * screen reader user presses next.
 */
export function SegmentedControl<T extends string>({
  legend,
  value,
  options,
  onChange,
  hideLegend = false,
  className,
}: SegmentedControlProps<T>) {
  const buttons = useRef<Array<HTMLButtonElement | null>>([])

  function move(currentIndex: number, delta: number) {
    const next = (currentIndex + delta + options.length) % options.length
    onChange(options[next].value)
    buttons.current[next]?.focus()
  }

  function selectAt(index: number) {
    onChange(options[index].value)
    buttons.current[index]?.focus()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    switch (event.key) {
      case 'ArrowRight':
      case 'ArrowDown':
        event.preventDefault()
        move(index, 1)
        break
      case 'ArrowLeft':
      case 'ArrowUp':
        event.preventDefault()
        move(index, -1)
        break
      case 'Home':
        event.preventDefault()
        selectAt(0)
        break
      case 'End':
        event.preventDefault()
        selectAt(options.length - 1)
        break
    }
  }

  return (
    <fieldset className={cn('w-full', className)}>
      <legend className={cn('mb-2 text-small font-medium text-text-primary', hideLegend && 'sr-only')}>
        {legend}
      </legend>

      <div className="flex gap-1 rounded-xl bg-surface-sunken p-1" role="radiogroup" aria-label={legend}>
        {options.map((option, index) => {
          const active = option.value === value
          return (
            <button
              key={option.value}
              ref={(node) => {
                buttons.current[index] = node
              }}
              type="button"
              role="radio"
              aria-checked={active}
              // Roving tabindex: the group is one stop, arrows move inside it.
              tabIndex={active ? 0 : -1}
              onClick={() => onChange(option.value)}
              onKeyDown={(event) => handleKeyDown(event, index)}
              className={cn(
                'min-h-control flex-1 rounded-lg px-3 text-small font-semibold transition-colors',
                active
                  ? 'bg-surface-raised text-text-primary shadow-card'
                  : 'text-text-secondary hover:text-text-primary',
              )}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
