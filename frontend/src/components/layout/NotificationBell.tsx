import { useEffect, useRef, useState } from 'react'

import { notificationsApi } from '../../api/notifications'
import { formatRelative } from '../../lib/format'
import type { Notification } from '../../types'

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
    const timer = setInterval(() => void load(), 30000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
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
        className="relative rounded-xl border border-slate-200 bg-white p-2.5 text-navy-700 hover:bg-slate-50"
        aria-label={`Notifications${unread.length ? `, ${unread.length} unread` : ''}`}
        aria-expanded={open}
      >
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 0 0-4-5.7V5a2 2 0 1 0-4 0v.3A6 6 0 0 0 6 11v3.2c0 .5-.2 1-.6 1.4L4 17h5m6 0a3 3 0 1 1-6 0m6 0H9"
          />
        </svg>
        {unread.length > 0 && (
          <span className="absolute -right-1 -top-1 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-critical-600 px-1 text-[11px] font-bold text-white">
            {unread.length}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 max-w-[calc(100vw-2rem)] animate-fade-in rounded-2xl border border-slate-200 bg-white p-2 shadow-lifted">
          <p className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Notifications
          </p>
          {notifications.length === 0 ? (
            <p className="px-3 py-6 text-center text-sm text-slate-500">Nothing to show yet.</p>
          ) : (
            <ul className="max-h-96 overflow-y-auto">
              {notifications.map((notification) => (
                <li key={notification.id}>
                  <button
                    type="button"
                    onClick={() => void markRead(notification)}
                    className={`w-full rounded-xl px-3 py-2.5 text-left hover:bg-slate-50 ${
                      notification.read ? '' : 'bg-brand-50/50'
                    }`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-navy-800">{notification.title}</span>
                      {!notification.read && <span className="h-2 w-2 rounded-full bg-brand-500" />}
                    </span>
                    <span className="mt-0.5 block text-xs text-slate-600">{notification.message}</span>
                    <span className="mt-1 block text-[11px] text-slate-400">
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
