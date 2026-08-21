import { useEffect, useRef, useState } from 'react'
import { ChevronDown, LogOut } from 'lucide-react'

import { useAuth } from '../../auth/AuthContext'
import { cn } from '../../lib/cn'
import { Avatar } from '../ui'
import { ROLE_LABELS } from './navigation'

export function AccountMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [])

  if (!user) return null

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="true"
        className={cn(
          'flex min-h-control items-center gap-2.5 rounded-xl border border-border-subtle bg-surface-raised px-2 py-1.5',
          'hover:bg-surface',
        )}
      >
        <Avatar name={user.name} size="sm" />
        <span className="hidden text-left sm:block">
          <span className="block text-small font-semibold text-text-primary">{user.name}</span>
          <span className="block text-caption text-text-muted">{ROLE_LABELS[user.role]}</span>
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
      </button>

      {open && (
        <div className="absolute right-0 z-overlay mt-2 w-56 animate-fade-in rounded-2xl border border-border-subtle bg-surface-raised p-2 shadow-raised">
          <div className="border-b border-border-subtle px-3 pb-2.5 pt-1.5 sm:hidden">
            <p className="text-small font-semibold text-text-primary">{user.name}</p>
            <p className="text-caption text-text-muted">{ROLE_LABELS[user.role]}</p>
          </div>
          <p className="truncate px-3 py-2 text-caption text-text-muted">{user.email}</p>
          <button
            type="button"
            onClick={logout}
            className="flex w-full min-h-control items-center gap-2.5 rounded-xl px-3 text-small font-semibold text-text-primary hover:bg-surface"
          >
            <LogOut className="h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
