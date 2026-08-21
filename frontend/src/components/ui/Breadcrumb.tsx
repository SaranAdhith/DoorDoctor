import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'

import { cn } from '../../lib/cn'

export interface Crumb {
  label: string
  /** Omit on the final crumb — the current page is not a link. */
  to?: string
}

export function Breadcrumb({ items, className }: { items: Crumb[]; className?: string }) {
  return (
    <nav aria-label="Breadcrumb" className={cn('min-w-0', className)}>
      <ol className="flex flex-wrap items-center gap-1 text-small text-text-secondary">
        {items.map((item, index) => {
          const last = index === items.length - 1
          return (
            <li key={`${item.label}-${index}`} className="flex items-center gap-1">
              {index > 0 && (
                <ChevronRight className="h-3.5 w-3.5 shrink-0 text-text-muted" aria-hidden="true" />
              )}
              {item.to && !last ? (
                <Link to={item.to} className="rounded-sm hover:text-text-primary hover:underline">
                  {item.label}
                </Link>
              ) : (
                <span className={cn(last && 'font-medium text-text-primary')} aria-current={last ? 'page' : undefined}>
                  {item.label}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
