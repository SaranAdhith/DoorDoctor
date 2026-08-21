import { useId, type ReactNode } from 'react'

import { cn } from '../../lib/cn'

export interface TabItem<T extends string> {
  value: T
  label: ReactNode
  /** Trailing count, e.g. the number of rows behind the tab. */
  count?: number
}

export interface TabsProps<T extends string> {
  items: ReadonlyArray<TabItem<T>>
  value: T
  onChange: (value: T) => void
  /** Announced as the purpose of the tab list. */
  label: string
  /** `segmented` is a compact pill group; `underline` is a page-level tab bar. */
  variant?: 'underline' | 'segmented'
  className?: string
}

export function Tabs<T extends string>({
  items,
  value,
  onChange,
  label,
  variant = 'underline',
  className,
}: TabsProps<T>) {
  const id = useId()

  // Left/Right arrows move between tabs, per the WAI-ARIA tabs pattern.
  function handleKeyDown(event: React.KeyboardEvent, index: number) {
    const delta = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (delta === 0) return
    event.preventDefault()
    const next = items[(index + delta + items.length) % items.length]
    onChange(next.value)
    document.getElementById(`${id}-${next.value}`)?.focus()
  }

  if (variant === 'segmented') {
    return (
      <div
        role="tablist"
        aria-label={label}
        className={cn(
          'flex max-w-full gap-1 overflow-x-auto rounded-xl bg-surface-sunken p-1',
          className,
        )}
      >
        {items.map((item, index) => {
          const selected = item.value === value
          return (
            <button
              key={item.value}
              id={`${id}-${item.value}`}
              role="tab"
              type="button"
              aria-selected={selected}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(item.value)}
              onKeyDown={(event) => handleKeyDown(event, index)}
              className={cn(
                'min-h-[2.25rem] shrink-0 whitespace-nowrap rounded-lg px-3.5 text-small font-semibold transition-colors',
                selected
                  ? 'bg-surface-raised text-text-primary shadow-card'
                  : 'text-text-secondary hover:text-text-primary',
              )}
            >
              {item.label}
              {item.count !== undefined && <span className="tnum ml-1.5 opacity-60">{item.count}</span>}
            </button>
          )
        })}
      </div>
    )
  }

  return (
    <div
      role="tablist"
      aria-label={label}
      className={cn('flex gap-1 overflow-x-auto border-b border-border-subtle', className)}
    >
      {items.map((item, index) => {
        const selected = item.value === value
        return (
          <button
            key={item.value}
            id={`${id}-${item.value}`}
            role="tab"
            type="button"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.value)}
            onKeyDown={(event) => handleKeyDown(event, index)}
            className={cn(
              'whitespace-nowrap border-b-2 px-3.5 py-2.5 text-small font-semibold transition-colors',
              selected
                ? 'border-brand-500 text-text-primary'
                : 'border-transparent text-text-secondary hover:text-text-primary',
            )}
          >
            {item.label}
            {item.count !== undefined && <span className="tnum ml-1.5 opacity-60">{item.count}</span>}
          </button>
        )
      })}
    </div>
  )
}
