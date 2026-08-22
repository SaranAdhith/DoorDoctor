import { Clock, MapPin, Phone } from 'lucide-react'

import { LeadForm, PageHero, Section, SectionHeading, Seo } from '../../components/public'

/**
 * Contact.
 *
 * The form is `LeadForm`, which posts to the only unauthenticated write endpoint
 * in the product. The emergency notice sits above it deliberately: someone whose
 * parent is in trouble right now should be told to call 108 *before* they start
 * filling in a form that will be answered tomorrow.
 */

const FACTS = [
  {
    icon: MapPin,
    title: 'Where we operate',
    body: 'Bengaluru. If your parents are elsewhere, tell us where — we will say honestly whether we can help.',
  },
  {
    icon: Clock,
    title: 'When we reply',
    body: 'Within one working day. If you are abroad, tell us your timezone and we will call at a sensible hour for you.',
  },
  {
    icon: Phone,
    title: 'What happens next',
    body: 'A conversation, not a sales call. Who needs care, where they live, what worries you, and whether we are the right fit.',
  },
]

export function Contact() {
  return (
    <>
      <Seo
        title="Contact"
        description="Get in touch with DoorDoctor about home nursing and monitoring for elderly parents in Bengaluru. We reply within one working day."
        path="/contact"
      />

      <PageHero
        eyebrow="Contact"
        title="Tell us who needs looking after"
        description="One conversation is enough for us both to work out whether this is right for your family. There is no obligation and we will not chase you with automated calls."
      />

      <Section tone="default">
        <p className="mb-10 rounded-xl border border-status-critical-border bg-status-critical-bg px-4 py-3.5 text-small font-medium text-status-critical">
          If someone needs medical help right now, do not use this form — call{' '}
          <a href="tel:108" className="font-bold underline">
            108
          </a>{' '}
          immediately. DoorDoctor is a monitoring service, not an emergency service, and this form is
          answered within one working day.
        </p>

        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,34rem)] lg:items-start">
          <div>
            <SectionHeading
              eyebrow="Before you write"
              title="What is useful to include"
              description="None of it is required, but it saves a round trip."
            />

            <ul className="mt-8 space-y-3">
              {[
                'Who needs care, and roughly how old they are',
                'Which area of Bengaluru they live in',
                'What they are managing — blood pressure, diabetes, mobility, memory',
                'Whether anyone is with them during the day',
                'What worries you most right now',
              ].map((item) => (
                <li key={item} className="flex gap-2.5 text-body text-text-secondary">
                  <span
                    className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500"
                    aria-hidden="true"
                  />
                  {item}
                </li>
              ))}
            </ul>

            <div className="mt-10 grid gap-6 sm:grid-cols-3 lg:grid-cols-1">
              {FACTS.map(({ icon: Icon, title, body }) => (
                <div key={title} className="flex gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-sunken text-text-secondary">
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-small font-semibold text-text-primary">{title}</p>
                    <p className="mt-0.5 text-small text-text-secondary">{body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <LeadForm />
        </div>
      </Section>
    </>
  )
}
