import { CtaBand, PageHero, Section, SectionHeading, Seo } from '../../components/public'
import { LinkButton } from '../../components/ui'

/**
 * The mechanism, in order. This is the page that answers "is this a real
 * operation or a landing page?", so it describes the actual sequence the
 * platform implements — including what happens when a reading breaches, which
 * is the part most services leave vague.
 */

const GETTING_STARTED = [
  {
    title: 'You tell us who needs care',
    body: 'A short conversation: who your parents are, where they live, what conditions they are managing, and what worries you most.',
  },
  {
    title: 'We set up their record',
    body: 'Conditions, current medicines, and the monitoring ranges for their readings. Those ranges are theirs — a blood pressure that is normal for one 80-year-old is not normal for another.',
  },
  {
    title: 'You choose a visit schedule',
    body: 'How often a nurse comes, and roughly when. We route visits by area so the same small group of nurses covers their neighbourhood.',
  },
  {
    title: 'You get an account',
    body: 'You sign in and see everything from the first visit onwards. Other family members can be added.',
  },
]

const A_VISIT = [
  {
    step: '1',
    title: 'The nurse checks in at the home',
    body: 'Check-in is recorded on site at the start of the visit, so a visit that did not happen cannot be written up as though it did.',
  },
  {
    step: '2',
    title: 'Vitals are recorded at the bedside',
    body: 'Blood pressure, pulse, blood sugar, oxygen saturation, temperature and weight — entered during the visit, attached to that visit.',
  },
  {
    step: '3',
    title: 'Each reading is checked against that patient’s range',
    body: 'This happens as the reading is entered. There is no review queue and no end-of-week batch.',
  },
  {
    step: '4',
    title: 'Medicines are supervised and logged',
    body: 'Every scheduled dose is marked given, skipped or refused. A skipped dose carries the reason it was skipped.',
  },
  {
    step: '5',
    title: 'The nurse writes up the visit',
    body: 'A short note on how your parent seemed — appetite, sleep, mobility, mood. The things a number does not capture.',
  },
]

const WHEN_SOMETHING_IS_WRONG = [
  {
    title: 'An alert is raised automatically',
    body: 'Not by someone noticing later. The moment a reading falls outside the configured range, the platform raises it and records which measurement breached and by how much.',
  },
  {
    title: 'The family and the care team are notified together',
    body: 'You are not told after it has been handled. You see it when our admins see it.',
  },
  {
    title: 'An admin works it and resolves it',
    body: 'Someone contacts the nurse or the family, decides what needs to happen, and closes the alert with a note saying what was done.',
  },
  {
    title: 'It stays visible afterwards',
    body: 'Resolved alerts do not disappear. What happened, when, and who handled it stays on the record.',
  },
]

export function HowItWorks() {
  return (
    <>
      <Seo
        title="How it works"
        description="How a DoorDoctor visit works, start to finish: onboarding, nurse check-in, recorded vitals, medication supervision, threshold alerts, and how an alert is escalated and resolved."
        path="/how-it-works"
      />

      <PageHero
        eyebrow="How it works"
        title="From the first phone call to a resolved alert"
        description="This is the whole sequence. It is worth reading before you decide, because the difference between elder-care services is almost entirely in what happens after somebody notices something."
      />

      <Section tone="default">
        <SectionHeading eyebrow="Getting started" title="Setting up takes one conversation" />
        <ol className="mt-10 grid gap-6 md:grid-cols-2">
          {GETTING_STARTED.map((item, index) => (
            <li
              key={item.title}
              className="rounded-2xl border border-border-subtle bg-surface p-6"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-navy-800 text-small font-bold text-text-inverted">
                {index + 1}
              </span>
              <h3 className="mt-4 text-body font-semibold text-text-primary">{item.title}</h3>
              <p className="mt-1.5 text-body text-text-secondary">{item.body}</p>
            </li>
          ))}
        </ol>
      </Section>

      <Section tone="sunken">
        <SectionHeading
          eyebrow="A visit"
          title="What happens in the house"
          description="Every visit follows the same order, so the record is comparable week to week."
        />
        <ol className="mt-10 space-y-4">
          {A_VISIT.map((item) => (
            <li
              key={item.step}
              className="flex gap-5 rounded-2xl border border-border-subtle bg-surface-raised p-5 shadow-card sm:p-6"
            >
              <span
                aria-hidden="true"
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-500 text-body font-bold text-text-inverted"
              >
                {item.step}
              </span>
              <div className="min-w-0">
                <h3 className="text-body font-semibold text-text-primary">{item.title}</h3>
                <p className="mt-1 text-body text-text-secondary">{item.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </Section>

      <Section tone="default">
        <SectionHeading
          eyebrow="When a reading is out of range"
          title="The part that actually matters"
          description="Anyone can take a blood pressure. The question is what happens in the next hour."
        />
        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {WHEN_SOMETHING_IS_WRONG.map((item) => (
            <div key={item.title} className="rounded-2xl border border-border-subtle bg-surface p-6">
              <h3 className="text-body font-semibold text-text-primary">{item.title}</h3>
              <p className="mt-2 text-body text-text-secondary">{item.body}</p>
            </div>
          ))}
        </div>

        <p className="mt-8 rounded-xl border border-status-critical-border bg-status-critical-bg px-4 py-3.5 text-small font-medium text-status-critical">
          An alert means a reading fell outside the range configured for that patient. It is not a
          diagnosis. If someone needs medical help immediately, call{' '}
          <a href="tel:108" className="font-bold underline">
            108
          </a>{' '}
          — DoorDoctor is a monitoring service, not an emergency service.
        </p>
      </Section>

      <Section tone="sunken">
        <SectionHeading
          eyebrow="Between visits"
          title="What you see when nothing is wrong"
          description="Most weeks nothing is wrong, and that is worth being able to see too."
        />
        <ul className="mt-8 space-y-3">
          {[
            ['A plain-language summary', 'How your parent has been over the last week, month or quarter, written in ordinary English.'],
            ['Weekly and monthly reports', 'Generated automatically and downloadable as a PDF, so you can forward one to a doctor.'],
            ['Trends, not snapshots', 'Charts of every recorded reading, so a slow drift is visible before it becomes an alert.'],
            ['An assistant you can ask', 'Questions in your own words about your own parent’s record — and only theirs.'],
          ].map(([title, body]) => (
            <li
              key={title}
              className="rounded-xl border border-border-subtle bg-surface-raised px-5 py-4"
            >
              <p className="text-body font-semibold text-text-primary">{title}</p>
              <p className="mt-1 text-small text-text-secondary">{body}</p>
            </li>
          ))}
        </ul>
        <div className="mt-8 flex flex-wrap gap-3">
          <LinkButton to="/trust-and-safety" variant="ghost">
            Trust and safety
          </LinkButton>
          <LinkButton to="/faq" variant="ghost">
            Common questions
          </LinkButton>
        </div>
      </Section>

      <CtaBand />
    </>
  )
}
