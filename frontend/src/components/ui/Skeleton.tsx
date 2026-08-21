import type { CSSProperties } from 'react'

import { cn } from '../../lib/cn'

export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-surface-sunken', className)}
      style={style}
      aria-hidden="true"
    />
  )
}

/** Placeholder for a card whose content is still loading. */
export function SkeletonCard({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div
      className={cn('rounded-2xl border border-border-subtle bg-surface-raised p-5 shadow-card', className)}
      aria-hidden="true"
    >
      <Skeleton className="mb-4 h-3 w-24" />
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton key={index} className="mb-2.5 h-3" style={{ width: `${90 - index * 15}%` }} />
      ))}
    </div>
  )
}

/** Placeholder rows for a table that is still loading. */
export function SkeletonRows({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <tr key={rowIndex} aria-hidden="true">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <td key={colIndex} className="px-4 py-3.5">
              <Skeleton className={cn('h-3', colIndex === 0 ? 'w-32' : 'w-20')} />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}
