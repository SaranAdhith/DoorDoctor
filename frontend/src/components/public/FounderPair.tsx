/**
 * Both founders, as an equal pair.
 *
 * This is one component rather than two cards on a page so that they cannot be
 * rendered apart, given different card sizes, or reordered by whoever edits the
 * page next. **Saran Adhith (Founder & CEO)** and **Darren D'Souza
 * (Co-Founder)** are always presented together, with equal billing — a locked
 * decision in `docs/build-log/STATE.md`, and the sort of thing a marketing page
 * breaks by accident.
 *
 * No photographs: there are none in the repo, and a stock portrait standing in
 * for a real person is a lie about a named individual. Initials instead.
 */

interface Founder {
  name: string
  role: string
  initials: string
  bio: string
}

export const FOUNDERS: readonly Founder[] = [
  {
    name: 'Saran Adhith',
    role: 'Founder & CEO',
    initials: 'SA',
    bio:
      'Started DoorDoctor after watching families try to coordinate a parent’s care over the ' +
      'phone from another city, with no record of what had actually happened at home.',
  },
  {
    name: "Darren D'Souza",
    role: 'Co-Founder',
    initials: 'DD',
    bio:
      'Works on how care is actually delivered on the ground — how visits are routed, what a ' +
      'nurse records at the bedside, and how quickly a reading outside the range reaches someone.',
  },
] as const

export function FounderPair() {
  return (
    <div className="grid gap-6 sm:grid-cols-2">
      {FOUNDERS.map((founder) => (
        <div
          key={founder.name}
          className="rounded-2xl border border-border-subtle bg-surface-raised p-6 shadow-card"
        >
          <div className="flex items-center gap-4">
            <span
              aria-hidden="true"
              className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-h2 font-bold text-text-inverted"
            >
              {founder.initials}
            </span>
            <div className="min-w-0">
              <p className="text-h2 font-bold text-text-primary">{founder.name}</p>
              <p className="text-small font-medium text-brand-700">{founder.role}</p>
            </div>
          </div>
          <p className="mt-4 text-body text-text-secondary">{founder.bio}</p>
        </div>
      ))}
    </div>
  )
}
