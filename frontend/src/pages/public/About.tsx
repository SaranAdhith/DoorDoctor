import {
  CtaBand,
  FounderPair,
  PageHero,
  Section,
  SectionHeading,
  Seo,
} from '../../components/public'

/**
 * About.
 *
 * DoorDoctor is pre-launch, and this is the page that most wants to invent a
 * founding date, a headcount, a customer number or an award. It states what is
 * true — two founders, one city, a service being built — and nothing else. The
 * founders are rendered by `FounderPair`, which exists so they cannot be split
 * up or given unequal billing by a later edit.
 */

const PRINCIPLES = [
  {
    title: 'The family is the reader',
    body: 'Every summary, alert and report is written for the person who is not a clinician and is not in the room. If a sentence needs a medical dictionary, it is our sentence that is wrong.',
  },
  {
    title: 'A record, or it did not happen',
    body: 'Visits are checked in on site. Readings are entered at the bedside. Doses are logged as given, skipped or refused. Care that is not recorded is care nobody can act on later.',
  },
  {
    title: 'Escalation is a person, not a colour',
    body: 'An alert is not finished when it turns red on a screen. It is finished when somebody has worked it and written down what they did.',
  },
  {
    title: 'Say the limits out loud',
    body: 'We are not an emergency service, we do not diagnose, and we do not change anybody’s medication. A service that blurs those lines is dangerous in exactly the moment it matters.',
  },
]

export function About() {
  return (
    <>
      <Seo
        title="About us"
        description="DoorDoctor is an elderly home-care service being built in Bengaluru by Saran Adhith and Darren D'Souza."
        path="/about"
      />

      <PageHero
        eyebrow="About us"
        title="Built in Bengaluru, for families who cannot be in two places"
        description="DoorDoctor is a new company. We are building a home-visit nursing service where what happens at the bedside actually reaches the family — because the version of that which exists today mostly does not."
      />

      <Section tone="default">
        <SectionHeading
          eyebrow="Why we started"
          title="The information was always there. It just never travelled."
          description="Somebody visits an elderly parent. They notice something. It gets mentioned on a phone call, or it does not. Weeks later a family is making a serious decision on the basis of half-remembered fragments. That is not a shortage of care — it is a shortage of record-keeping, and it is a solvable problem."
        />
      </Section>

      <Section tone="sunken">
        <SectionHeading
          eyebrow="The founders"
          title="Two of us"
          description="DoorDoctor is founded and run by two people. We are not going to pretend to be more than that."
        />
        <div className="mt-10">
          <FounderPair />
        </div>
      </Section>

      <Section tone="default">
        <SectionHeading eyebrow="How we work" title="Four things we have decided not to compromise on" />
        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {PRINCIPLES.map((item) => (
            <div
              key={item.title}
              className="rounded-2xl border border-border-subtle bg-surface p-6"
            >
              <h3 className="text-body font-semibold text-text-primary">{item.title}</h3>
              <p className="mt-2 text-body text-text-secondary">{item.body}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section tone="sunken" narrow>
        <SectionHeading
          eyebrow="Where we are"
          title="Early, and saying so"
          description="DoorDoctor is at the beginning. We are not going to put invented customer numbers, borrowed testimonials or partner logos on this site to look further along than we are — where our home page shows review and tie-up cards, they are marked as placeholders for exactly that reason. If you are considering us, you are considering an early company — you should weigh that, and you should ask us hard questions when we speak."
        />
      </Section>

      <CtaBand
        title="Ask us anything"
        description="Including the awkward questions. We would rather answer them now than have you find out later."
      />
    </>
  )
}
