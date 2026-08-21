import { useEffect, useRef, useState } from 'react'
import { Bell } from 'lucide-react'

import { notificationsApi } from '../../api/notifications'
import { cn } from '../../lib/cn'
import { formatRelative } from '../../lib/format'
import type { Notification } from '../../types'

const POLL_MS = 30000

export function NotificationBell() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  async function load() {
    try {
      setNotifications(await notificationsApi.list())
    } catch {
      /* the bell is non-critical - stay quiet if it cannot load */
    }
  }

  useEffect(() => {
    void load()
    // Lightweight polling stands in for the production WebSocket channel.
    const timer = setInterval(() => void load(), POLL_MS)
    return () => clearInterval(timer)
  }, [])

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

  const unread = notifications.filter((item) => !item.read)

  async function markRead(notification: Notification) {
    if (notification.read) return
    try {
      const updated = await notificationsApi.markRead(notification.id)
      setNotifications((current) => current.map((item) => (item.id === updated.id ? updated : item)))
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-border-subtle bg-surface-raised text-text-secondary hover:bg-surface hover:text-text-primary"
        aria-label={`Notifications${unread.length ? `, ${unread.length} unread` : ''}`}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <Bell className="h-5 w-5" aria-hidden="true" />
        {unread.length > 0 && (
          <span className="tnum absolute -right-1 -top-1 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-critical-600 px-1 text-caption font-bold text-text-inverted">
            {unread.length}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-overlay mt-2 w-80 max-w-[calc(100vw-2rem)] animate-fade-in rounded-2xl border border-border-subtle bg-surface-raised p-2 shadow-raised">
          <p className="px-3 py-2 text-caption font-semibold uppercase tracking-wide text-text-secondary">
            Notifications
          </p>
          {notifications.length === 0 ? (
            <p className="px-3 py-6 text-center text-small text-text-secondary">Nothing to show yet.</p>
          ) : (
            <ul className="max-h-96 overflow-y-auto">
              {notifications.map((notification) => (
                <li key={notification.id}>
                  <button
                    type="button"
                    onClick={() => void markRead(notification)}
                    className={cn(
                      'w-full rounded-xl px-3 py-2.5 text-left hover:bg-surface',
                      !notification.read && 'bg-brand-50/50',
                    )}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="text-small font-semibold text-text-primary">
                        {notification.title}
                      </span>
                      {!notification.read && (
                        <span
                          className="h-2 w-2 shrink-0 rounded-full bg-brand-500"
                          aria-label="Unread"
                        />
                      )}
                    </span>
                    <span className="mt-0.5 block text-caption text-text-secondary">
                      {notification.message}
                    </span>
                    <span className="mt-1 block text-caption text-text-muted">
                      {formatRelative(notification.created_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
