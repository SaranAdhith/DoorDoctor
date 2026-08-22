import { Building2, Globe2, Home, Users } from 'lucide-react'

import { CtaBand, PageHero, Section, SectionHeading, Seo } from '../../components/public'
import { LinkButton } from '../../components/ui'

/**
 * Four audiences, each with what changes for them. The "not the right fit"
 * section is deliberate: a service that claims to suit everybody suits nobody,
 * and telling someone early costs one enquiry instead of one bad month.
 */

const AUDIENCES = [
  {
    icon: Home,
    eyebrow: 'Families in Bengaluru',
    title: 'You are nearby, but not there on weekdays',
    body: 'You see your parents at the weekend and everything seems fine. What you cannot see is the five days in between — whether the evening tablet was taken, whether the blood pressure has been creeping up since the last time anyone checked.',
    points: [
      'A nurse covers the weekdays you cannot',
      'You see each visit the day it happens',
      'A drifting reading reaches you before it becomes an incident',
    ],
    to: '/pricing',
    cta: 'See family pricing',
  },
  {
    icon: Globe2,
    eyebrow: 'NRI families',
    title: 'You are in another timezone and hear about things late',
    body: 'The hardest part of being abroad is not the distance. It is that your parents will not tell you when something is wrong, because they do not want you to worry from that far away.',
    points: [
      'A record you can read at your own hour, not theirs',
      'Alerts reach you at the same moment they reach our care team',
      'Reports you can forward to a doctor or a sibling',
    ],
    to: '/nri',
    cta: 'For families living abroad',
  },
  {
    icon: Building2,
    eyebrow: 'Employers',
    title: 'Your employees are managing their parents from their desks',
    body: 'Eldercare is the interruption nobody puts in a calendar. It is a phone call at 11am and an afternoon lost, repeatedly, for years. As a benefit it is unusually concrete: it buys back attention.',
    points: [
      'Priced per enrolled employee, per month',
      'Enrolled employees get the same service and the same visibility',
      'A benefit an employee can describe to their family in one sentence',
    ],
    to: '/pricing/corporate',
    cta: 'Corporate pricing',
  },
  {
    icon: Users,
    eyebrow: 'Residences and care homes',
    title: 'You have residents and no consistent clinical record',
    body: 'Staff change, shifts change, and the handover is verbal. A monitoring layer that survives a shift change is worth more than another logbook.',
    points: [
      'Priced per resident per day',
      'The same threshold monitoring across every resident',
      'Records that outlast whoever was on duty',
    ],
    to: '/pricing/institutions',
    cta: 'Institutional pricing',
  },
]

const NOT_A_FIT = [
  'Someone who needs a live-in attendant or continuous supervision — this is scheduled visiting care.',
  'A medical emergency happening right now. Call 108.',
  'Anyone needing hospital-level treatment at home, such as ventilation or IV therapy.',
  'Families outside our current service area. We are in Bengaluru; tell us where you are and we will say honestly whether we can help.',
]

export function WhoItsFor() {
  return (
    <>
      <Seo
        title="Who it's for"
        description="DoorDoctor serves families in Bengaluru, NRI families with parents in India, employers offering elder care as a benefit, and residences needing consistent clinical monitoring."
        path="/who-its-for"
      />

      <PageHero
        eyebrow="Who it's for"
        title="Four situations, one service"
        description="What we do does not change between these. What changes is why it matters to you — and, for organisations, how it is priced."
      />

      <Section tone="default">
        <div className="grid gap-6 lg:grid-cols-2">
          {AUDIENCES.map(({ icon: Icon, eyebrow, title, body, points, to, cta }) => (
            <div
              key={eyebrow}
              className="flex flex-col rounded-2xl border border-border-subtle bg-surface-raised p-6 shadow-card sm:p-7"
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <p className="mt-4 text-caption font-semibold uppercase tracking-[0.14em] text-brand-700">
                {eyebrow}
              </p>
              <h2 className="mt-1.5 text-h2 font-bold text-text-primary">{title}</h2>
              <p className="mt-3 text-body text-text-secondary">{body}</p>
              <ul className="mt-4 flex-1 space-y-2">
                {points.map((point) => (
                  <li key={point} className="flex gap-2.5 text-small text-text-secondary">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" aria-hidden="true" />
                    {point}
                  </li>
                ))}
              </ul>
              <LinkButton to={to} variant="ghost" className="mt-6 self-start">
                {cta}
              </LinkButton>
            </div>
          ))}
        </div>
      </Section>

      <Section tone="sunken">
        <SectionHeading
          eyebrow="Being honest"
          title="When we are not the right fit"
          description="We would rather tell you now than take a month of your money finding out together."
        />
        <ul className="mt-8 space-y-3">
          {NOT_A_FIT.map((item) => (
            <li
              key={item}
              className="rounded-xl border border-border-subtle bg-surface-raised px-5 py-4 text-body text-text-secondary"
            >
              {item}
            </li>
          ))}
        </ul>
      </Section>

      <CtaBand />
    </>
  )
}
