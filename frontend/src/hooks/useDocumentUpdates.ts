import { useEffect, useState } from 'react'

import { api } from '../api/client'

/**
 * Unseen document updates — the number on the Documents menu item (Phase 12).
 *
 * One poller for the whole app however many components show the badge (the
 * sidebar and the mobile bottom bar both do), the same 30 s cadence as the
 * notification bell. Opening a Documents page calls `markDocumentsSeen()`,
 * which clears the count everywhere at once.
 */

const POLL_MS = 30_000
let count = 0
let timer: ReturnType<typeof setInterval> | null = null
const listeners = new Set<(value: number) => void>()

function publish(value: number) {
  count = value
  listeners.forEach((listener) => listener(value))
}

async function refresh() {
  try {
    const { count: unseen } = await api.get<{ count: number }>('/documents/notifications/unseen')
    publish(unseen)
  } catch {
    // A failed poll keeps the last number; the menu must not flicker to zero.
  }
}

export function refreshDocumentUpdates(): void {
  void refresh()
}

export async function markDocumentsSeen(): Promise<void> {
  try {
    await api.post('/documents/notifications/seen')
    publish(0)
  } catch {
    // Nothing to do: the next poll shows the true count.
  }
}

export function useDocumentUpdates(enabled = true): number {
  const [value, setValue] = useState(count)

  useEffect(() => {
    if (!enabled) return
    listeners.add(setValue)
    if (listeners.size === 1) {
      void refresh()
      timer = setInterval(() => void refresh(), POLL_MS)
    }
    return () => {
      listeners.delete(setValue)
      if (listeners.size === 0 && timer) {
        clearInterval(timer)
        timer = null
      }
    }
  }, [enabled])

  return enabled ? value : 0
}
