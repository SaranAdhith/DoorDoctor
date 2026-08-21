import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'

/**
 * Thin structural wrappers rather than a data-grid abstraction. Screens keep
 * control of their columns; what this guarantees is that every table in the
 * product scrolls, aligns and reads the same way.
 */

export function TableWrap({ children, className }: { children: ReactNode; className?: string }) {
  // Wide tables scroll inside their own container so the page body never does.
  return <div className={cn('w-full overflow-x-auto', className)}>{children}</div>
}

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return <table className={cn('w-full min-w-[36rem] border-collapse text-left', className)}>{children}</table>
}

export function THead({ children }: { children: ReactNode }) {
  return <thead className="border-b border-border-subtle bg-surface">{children}</thead>
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-border-subtle">{children}</tbody>
}

export function TR({
  children,
  className,
  onClick,
}: {
  children: ReactNode
  className?: string
  onClick?: () => void
}) {
  return (
    <tr
      className={cn(onClick && 'cursor-pointer transition-colors hover:bg-surface', className)}
      onClick={onClick}
    >
      {children}
    </tr>
  )
}

export function TH({
  children,
  className,
  numeric = false,
}: {
  children: ReactNode
  className?: string
  numeric?: boolean
}) {
  return (
    <th
      scope="col"
      className={cn(
        'whitespace-nowrap px-4 py-3 text-caption font-semibold uppercase tracking-wide text-text-secondary',
        numeric && 'text-right',
        className,
      )}
    >
      {children}
    </th>
  )
}

export function TD({
  children,
  className,
  numeric = false,
}: {
  children: ReactNode
  className?: string
  numeric?: boolean
}) {
  return (
    <td
      className={cn(
        'px-4 py-3.5 text-small text-text-primary',
        numeric && 'tnum text-right',
        className,
      )}
    >
      {children}
    </td>
  )
}

/** Full-width row used to host an empty or error state inside a table body. */
export function TEmptyRow({ colSpan, children }: { colSpan: number; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-6">
        {children}
      </td>
    </tr>
  )
}
