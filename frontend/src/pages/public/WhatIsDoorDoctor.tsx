import { CtaBand, PageHero, Section, SectionHeading, Seo } from '../../components/public'
import { LinkButton } from '../../components/ui'

/**
 * The explainer page. Deliberately plain: someone reading this is deciding
 * whether the service is real, and the fastest way to answer that is to describe
 * the mechanism rather than the benefit.
 */

const INCLUDED = [
  {
    title: 'Scheduled home visits by a qualified nurse',
    body: 'An RN or ANM comes to the house on the cadence your plan covers. Visits are routed by area, so the same small group of nurses covers your parents’ neighbourhood.',
  },
  {
    title: 'Vitals recorded during the visit',
    body: 'Blood pressure, pulse, blood sugar, oxygen saturation, temperature and weight, entered at the bedside and timestamped to the visit they belong to.',
  },
  {
    title: 'Medication supervision',
    body: 'Each prescribed dose is marked as given, skipped or refused, with a reason. Adherence stops being something anyone has to estimate.',
  },
  {
    title: 'Threshold monitoring on every reading',
    body: 'Each patient has their own configured ranges. Every reading is checked against them the moment it is entered — not reviewed at the end of the week.',
  },
  {
    title: 'Alerts that reach people, not a dashboard',
    body: 'A breach notifies the family and the DoorDoctor care team together, and stays open until an admin resolves it.',
  },
  {
    title: 'A record the family can actually read',
    body: 'A plain-language summary, weekly and monthly reports as PDFs, and the full clinical detail underneath for anyone who wants it.',
  },
]

const NOT_INCLUDED = [
  ['Emergency response', 'DoorDoctor is not an ambulance service. In an emergency, call 108.'],
  ['Diagnosis or prescription', 'Our nurses record and escalate. They do not diagnose, and they do not change anyone’s medication.'],
  ['Round-the-clock presence', 'This is scheduled visiting care, not a live-in attendant. If you need someone in the house continuously, we are not the right fit.'],
  ['Hospital treatment', 'We coordinate and hand over. The treatment itself happens where it should.'],
]

export function WhatIsDoorDoctor() {
  return (
    <>
      <Seo
        title="What is DoorDoctor"
        description="DoorDoctor is a home-visit nursing and monitoring service for elderly parents in Bengaluru: scheduled visits, recorded vitals, supervised medication and threshold alerts the family sees."
        path="/what-is-doordoctor"
      />

      <PageHero
        eyebrow="What is DoorDoctor"
        title="Home nursing for elderly parents, with a record their family can see"
        description="Most elder care fails quietly. Someone visits, something is noticed, and it never reaches the person who could act on it. DoorDoctor exists to close that gap — the visit is scheduled, what happened is recorded, and anything unusual is escalated the same day."
      />

      <Section tone="default">
        <SectionHeading
          eyebrow="In one paragraph"
          title="A nurse visits. The visit is recorded. You see it."
          description="A qualified nurse arrives at your parents’ home on a schedule, checks in on site, records their vitals, supervises their medicines, and writes up the visit. Each reading is compared against the range set for that patient. If something is outside it, an alert is raised — visible to you and to our care team at the same moment — and it stays open until someone has dealt with it and said what they did."
        />
      </Section>

      <Section tone="sunken">
        <SectionHeading eyebrow="What is included" title="What you actually get" />
        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {INCLUDED.map((item) => (
            <div
              key={item.title}
              className="rounded-2xl border border-border-subtle bg-surface-raised p-6 shadow-card"
            >
              <h3 className="text-body font-semibold text-text-primary">{item.title}</h3>
              <p className="mt-2 text-body text-text-secondary">{item.body}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section tone="default">
        <SectionHeading
          eyebrow="What is not included"
          title="The limits, stated up front"
          description="You should know these before you sign up, not afterwards."
        />
        <dl className="mt-8 divide-y divide-border-subtle border-y border-border-subtle">
          {NOT_INCLUDED.map(([title, body]) => (
            <div key={title} className="grid gap-1 py-5 sm:grid-cols-[14rem_minmax(0,1fr)] sm:gap-6">
              <dt className="text-body font-semibold text-text-primary">{title}</dt>
              <dd className="text-body text-text-secondary">{body}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section tone="sunken">
        <SectionHeading
          eyebrow="Why a nurse and not a device"
          title="A wearable tells you a number. A nurse tells you what the house looks like."
          description="Devices are useful and we use them where they help. But a monitor cannot notice that the tablets in the organiser have not moved, that your father is unsteady standing up, or that nobody has been cooking. Someone has to be in the room."
        />
        <div className="mt-8 flex flex-wrap gap-3">
          <LinkButton to="/how-it-works" variant="ghost">
            How a visit works
          </LinkButton>
          <LinkButton to="/pricing" variant="ghost">
            See pricing
          </LinkButton>
        </div>
      </Section>

      <CtaBand />
    </>
  )
}
