import { NavLink } from 'react-router-dom'
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'

import { cn } from '../../lib/cn'
import type { Role } from '../../types'
import { Logo } from './Logo'
import { NAV_BY_ROLE } from './navigation'

interface Props {
  role: Role
  collapsed: boolean
  onToggle: () => void
  /** Called after navigating, so the mobile drawer can close itself. */
  onNavigate?: () => void
}

export function Sidebar({ role, collapsed, onToggle, onNavigate }: Props) {
  const sections = NAV_BY_ROLE[role]

  return (
    <div className="flex h-full flex-col border-r border-border-subtle bg-surface-raised">
      <div
        className={cn(
          'flex h-16 shrink-0 items-center gap-2 border-b border-border-subtle',
          collapsed ? 'justify-center px-2' : 'justify-between px-4',
        )}
      >
        {/*
          The strapline is dropped here even when expanded: at 256px it competes
          with the collapse control and wraps.
        */}
        {collapsed ? <Logo variant="mark" /> : <Logo showStrapline={false} />}
        <button
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
          aria-pressed={!collapsed}
          className={cn(
            'hidden h-9 w-9 shrink-0 items-center justify-center rounded-md',
            'text-text-muted hover:bg-surface hover:text-text-primary',
            // Collapsed, the mark owns the header row; the toggle moves under it.
            collapsed ? 'lg:hidden' : 'lg:flex',
          )}
        >
          <PanelLeftClose className="h-4 w-4" />
        </button>
      </div>

      {collapsed && (
        <button
          type="button"
          onClick={onToggle}
          aria-label="Expand navigation"
          aria-pressed={false}
          className="mx-auto mt-2 hidden h-9 w-9 items-center justify-center rounded-md text-text-muted hover:bg-surface hover:text-text-primary lg:flex"
        >
          <PanelLeftOpen className="h-4 w-4" />
        </button>
      )}

      <nav aria-label="Primary" className="flex-1 overflow-y-auto px-2 py-4">
        {sections.map((section, index) => (
          <div key={section.title ?? `group-${index}`} className={index > 0 ? 'mt-6' : undefined}>
            {section.title && !collapsed && (
              <h2 className="mb-2 px-3 text-caption font-semibold uppercase tracking-wide text-text-muted">
                {section.title}
              </h2>
            )}
            {/* A collapsed sidebar keeps the grouping as a hairline rule. */}
            {section.title && collapsed && index > 0 && (
              <div className="mx-2 mb-3 border-t border-border-subtle" aria-hidden="true" />
            )}

            <ul className="space-y-1">
              {section.items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    onClick={onNavigate}
                    title={collapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      cn(
                        'flex min-h-control items-center gap-3 rounded-xl text-small font-semibold transition-colors',
                        collapsed ? 'justify-center px-2' : 'px-3',
                        isActive
                          ? 'bg-navy-50 text-text-primary'
                          : 'text-text-secondary hover:bg-surface hover:text-text-primary',
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <item.icon
                          className={cn('h-4.5 w-4.5 shrink-0', isActive && 'text-brand-600')}
                          aria-hidden="true"
                        />
                        {collapsed ? <span className="sr-only">{item.label}</span> : item.label}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
    </div>
  )
}
