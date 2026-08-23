import { Eye, KeyRound, Lock, Siren, Stethoscope, UserCheck } from 'lucide-react'

import { CtaBand, PageHero, Section, SectionHeading, Seo } from '../../components/public'
import { LinkButton } from '../../components/ui'

/**
 * Trust and safety.
 *
 * Every claim on this page describes something the platform does. There are no
 * certifications, accreditations or compliance badges here, because DoorDoctor
 * holds none yet and a badge is the easiest lie on a healthcare website.
 */

const SAFETY = [
  {
    icon: UserCheck,
    title: 'Nurses are verified before they are assigned',
    body: 'A nurse’s qualification is recorded and their credentials are checked before they are given a patient. You can see who is assigned to each visit and what they are qualified as.',
  },
  {
    icon: Stethoscope,
    title: 'Ranges are set per patient by clinical staff',
    body: 'Monitoring thresholds are not a global default applied to everybody. They are configured for each patient and reviewed by qualified clinical staff.',
  },
  {
    icon: Siren,
    title: 'An alert is not closed until someone has worked it',
    body: 'A breach raises an alert that reaches the family and the care team together. It stays open until an admin resolves it with a note describing what was done.',
  },
  {
    icon: Eye,
    title: 'Visits are checked in on site',
    body: 'A visit is recorded as starting when the nurse checks in at the home, so the record reflects what happened rather than what was scheduled.',
  },
]

const DATA = [
  {
    icon: Lock,
    title: 'Access is by role, and it is enforced on the server',
    body: 'A family member can reach their own relative’s record and nothing else. A nurse reaches only the patients they are assigned to visit. These checks are applied on every request, not hidden in the interface.',
  },
  {
    icon: KeyRound,
    title: 'Passwords and reset links are stored hashed',
    body: 'Your password is never stored in a form we can read, and a password-reset link is stored only as a hash. Reset links expire after thirty minutes and work once.',
  },
]

const NOT_CLAIMING = [
  'We hold no healthcare accreditation or certification, and you will not find a badge on this site suggesting otherwise.',
  'We have not been independently audited. When that changes we will say so, with the name of who did it and when.',
  'We are early, so we have no outcomes data yet — no claim that our patients do better, because we cannot show you the numbers behind one. When we can, we will publish the method alongside the result.',
  'No payment gateway is integrated in the current build, so no card details are collected or stored anywhere in our systems.',
]

export function TrustAndSafety() {
  return (
    <>
      <Seo
        title="Trust and safety"
        description="How DoorDoctor verifies nurses, sets patient-specific monitoring thresholds, escalates alerts, and protects the clinical record — and what we do not claim."
        path="/trust-and-safety"
      />

      <PageHero
        eyebrow="Trust and safety"
        title="What we do, how we protect it, and what we do not claim"
        description="You are considering letting a stranger into your parents’ home and putting their health record in somebody’s database. Both of those deserve a straight answer."
      />

      <Section tone="default">
        <SectionHeading eyebrow="Clinical safety" title="How care is kept safe" />
        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {SAFETY.map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="rounded-2xl border border-border-subtle bg-surface-raised p-6 shadow-card"
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <h3 className="mt-4 text-body font-semibold text-text-primary">{title}</h3>
              <p className="mt-2 text-body text-text-secondary">{body}</p>
            </div>
          ))}
        </div>

        <p className="mt-8 rounded-xl border border-status-critical-border bg-status-critical-bg px-4 py-3.5 text-small font-medium text-status-critical">
          DoorDoctor is a monitoring and coordination service, not an emergency service. Alerts
          indicate readings outside the thresholds configured for a patient and are not medical
          diagnoses. In an emergency, call{' '}
          <a href="tel:108" className="font-bold underline">
            108
          </a>
          .
        </p>
      </Section>

      <Section tone="sunken">
        <SectionHeading
          eyebrow="Your data"
          title="Who can see your parent’s record"
          description="The short answer: you, the nurses assigned to their visits, and the DoorDoctor care team that works their alerts."
        />
        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {DATA.map(({ icon: Icon, title, body }) => (
            <div key={title} className="flex gap-4">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-navy-800 text-text-inverted">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <h3 className="text-body font-semibold text-text-primary">{title}</h3>
                <p className="mt-1 text-body text-text-secondary">{body}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-8">
          <LinkButton to="/privacy" variant="ghost">
            Read the privacy policy
          </LinkButton>
        </div>
      </Section>

      <Section tone="default">
        <SectionHeading
          eyebrow="What we are not claiming"
          title="The things a healthcare website usually implies"
          description="It is easy to put a shield icon next to a word and let a reader assume the rest. Here is what we are explicitly not saying."
        />
        <ul className="mt-8 space-y-3">
          {NOT_CLAIMING.map((item) => (
            <li
              key={item}
              className="rounded-xl border border-border-subtle bg-surface px-5 py-4 text-body text-text-secondary"
            >
              {item}
            </li>
          ))}
        </ul>
      </Section>

      <CtaBand
        title="Still have a concern?"
        description="Ask it before you sign up. If we cannot answer it properly, that is worth knowing."
      />
    </>
  )
}
