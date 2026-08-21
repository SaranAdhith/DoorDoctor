import { NavLink } from 'react-router-dom'

import { cn } from '../../lib/cn'
import type { Role } from '../../types'
import { primaryNavItems } from './navigation'

/**
 * Mobile-only navigation for the role's primary destinations. Hidden from
 * ≥768px, where the sidebar takes over.
 */
export function BottomTabs({ role }: { role: Role }) {
  const items = primaryNavItems(role)
  if (items.length < 2) return null

  return (
    <nav
      aria-label="Primary"
      className="sticky bottom-0 z-header border-t border-border-subtle bg-surface-raised md:hidden"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      <ul className="flex">
        {items.map((item) => (
          <li key={item.to} className="flex-1">
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex min-h-control flex-col items-center justify-center gap-1 py-2 text-caption font-semibold transition-colors',
                  isActive ? 'text-brand-600' : 'text-text-muted hover:text-text-primary',
                )
              }
            >
              <item.icon className="h-5 w-5" aria-hidden="true" />
              <span className="truncate px-1">{item.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
