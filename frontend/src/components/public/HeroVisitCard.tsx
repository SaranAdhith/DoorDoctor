import { BellRing, Check, ShieldCheck } from 'lucide-react'

/**
 * The card beside the home page headline.
 *
 * An illustration of the product, not a screenshot of it and not anybody's
 * record — the numbers are made up and chosen to tell the whole story in one
 * glance: a visit happened, a nurse whose credentials were checked did it,
 * these readings were taken, one of them was outside this patient's range, and
 * the family already knows.
 *
 * It is deliberately not wired to the API. A hero that fetches is a hero that
 * can render empty, spin, or fail in front of someone who has been on the site
 * for four seconds.
 */

const VITALS = [
  { label: 'Blood pressure', value: '128/82', unit: 'mmHg', out: false },
  { label: 'Pulse', value: '74', unit: 'bpm', out: false },
  { label: 'SpO₂', value: '97', unit: '%', out: false },
  { label: 'Blood sugar', value: '168', unit: 'mg/dL', out: true },
]

export function HeroVisitCard() {
  return (
    <div className="rounded-2xl border border-white/15 bg-surface-raised p-5 shadow-raised">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-caption font-semibold uppercase tracking-[0.12em] text-brand-700">
            Today&rsquo;s visit
          </p>
          <p className="mt-0.5 text-body font-bold text-text-primary">Completed 9:40 AM</p>
        </div>
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-status-good-bg text-status-good">
          <Check className="h-5 w-5" aria-hidden="true" />
        </span>
      </div>

      <div className="mt-4 flex items-center gap-3 rounded-xl bg-surface p-3">
        <span
          aria-hidden="true"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-small font-bold text-text-inverted"
        >
          SK
        </span>
        <div className="min-w-0">
          <p className="truncate text-small font-semibold text-text-primary">Sunitha K.</p>
          <p className="flex items-center gap-1 text-caption text-status-good">
            <ShieldCheck className="h-3 w-3" aria-hidden="true" />
            RN · credentials verified
          </p>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-2">
        {VITALS.map((vital) => (
          <div
            key={vital.label}
            className={
              vital.out
                ? 'rounded-xl border border-status-watch-border bg-status-watch-bg px-3 py-2'
                : 'rounded-xl border border-border-subtle px-3 py-2'
            }
          >
            <dt className="truncate text-caption text-text-muted">{vital.label}</dt>
            <dd
              className={
                vital.out
                  ? 'tnum text-body font-bold text-status-watch'
                  : 'tnum text-body font-bold text-text-primary'
              }
            >
              {vital.value}{' '}
              <span className="text-caption font-medium text-text-muted">{vital.unit}</span>
            </dd>
          </div>
        ))}
      </dl>

      <div className="mt-4 flex items-start gap-2.5 rounded-xl border border-status-watch-border bg-status-watch-bg px-3 py-2.5">
        <BellRing className="mt-0.5 h-4 w-4 shrink-0 text-status-watch" aria-hidden="true" />
        <p className="text-caption text-status-watch">
          <span className="font-semibold">Above the range set for this patient.</span> Family and
          care team notified 9:41 AM.
        </p>
      </div>
    </div>
  )
}
