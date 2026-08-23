import { Phone } from 'lucide-react'
import { useEffect, useState } from 'react'

import { escalationsApi } from '../../api/clinical'
import type { EmergencyBlock as EmergencyBlockData } from '../../types'

/**
 * The permanent "In an emergency, call 108" block (§4.9).
 *
 * Rendered on **every** clinical screen. One component, because the number and
 * the ladder are recorded and the same three rungs already appear in the
 * assistant's emergency intent — eight hand-written copies would drift, and the
 * one that drifted would be the one somebody read at the worst moment.
 *
 * The wording is **served**, not written here. `core/clinical.py` owns it.
 *
 * The fallback below is not a placeholder for missing content: if the API is
 * unreachable, a screen that renders no emergency number at all is worse than
 * one that renders the number and nothing else. 108 is the one string in this
 * codebase that is worth duplicating, and this is the only duplicate.
 */
const FALLBACK: EmergencyBlockData = {
  number: '108',
  title: 'In an emergency, call 108',
  body:
    'DoorDoctor monitors and coordinates care. It is not an emergency service. If something is ' +
    'seriously wrong right now, call 108 for an ambulance first, then tell the assigned nurse ' +
    'or the DoorDoctor team.',
  ladder: [],
}

export function EmergencyBlock({ compact = false }: { compact?: boolean }) {
  const [data, setData] = useState<EmergencyBlockData>(FALLBACK)

  useEffect(() => {
    let active = true
    escalationsApi
      .emergency()
      .then((served) => {
        if (active) setData(served)
      })
      .catch(() => {
        /* keep the fallback — see the note above */
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <aside
      // `role="note"` rather than `alert`: this is standing guidance, and an
      // assertive live region announced on every clinical page load would make
      // a screen reader unusable.
      role="note"
      aria-label={data.title}
      className="rounded-xl border border-status-critical/30 bg-status-critical/5 p-4"
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-status-critical/10 text-status-critical"
        >
          <Phone size={18} />
        </span>
        <div className="min-w-0">
          <p className="text-small font-semibold text-status-critical">{data.title}</p>
          {!compact && (
            <>
              <p className="mt-1 text-caption leading-relaxed text-text-muted">{data.body}</p>
              {data.ladder.length > 0 && (
                <ol className="mt-2 space-y-0.5 text-caption text-text-muted">
                  {data.ladder.map((rung, index) => (
                    <li key={rung}>
                      <span className="font-medium text-text-secondary">{index + 1}.</span> {rung}
                    </li>
                  ))}
                </ol>
              )}
            </>
          )}
        </div>
      </div>
    </aside>
  )
}
