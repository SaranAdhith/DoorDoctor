import { Clock, FileText, MessageCircleQuestion, Users } from 'lucide-react'

import {
  LeadForm,
  PageHero,
  Section,
  SectionHeading,
  Seo,
} from '../../components/public'
import { LinkButton } from '../../components/ui'

/**
 * For families abroad.
 *
 * Not a separate product and not a separate price list — the same service, and
 * this page says so rather than implying an "NRI plan" exists. What is genuinely
 * different is the timezone, the inability to drop in, and the fact that parents
 * abroad-proof their own bad news.
 */

const WHAT_IS_DIFFERENT = [
  {
    icon: Clock,
    title: 'You read it on your clock, not theirs',
    body: 'The record is there whenever you open it. You are not waiting for a convenient hour in India to find out how last week went.',
  },
  {
    icon: MessageCircleQuestion,
    title: 'You can ask instead of interrogating',
    body: 'Asking your mother directly gets you “everything is fine”. Asking the record gets you what her readings actually did.',
  },
  {
    icon: FileText,
    title: 'Reports you can forward',
    body: 'Weekly and monthly reports as PDFs — the thing to send a doctor, or a sibling who is asking how things are going.',
  },
  {
    icon: Users,
    title: 'Siblings can share the account',
    body: 'More than one family member can sign in, so coordinating with a brother in another country stops being a chain of forwarded messages.',
  },
]

const HONEST = [
  [
    'We cannot be there in an emergency',
    'If something is happening right now, someone in India has to call 108. Please have a local contact — a relative, a neighbour, a building manager — and give us their number.',
  ],
  [
    'We visit on a schedule',
    'This is scheduled visiting care. A nurse is not in the house continuously and we will not pretend otherwise.',
  ],
  [
    'Your parents have to agree to it',
    'A nurse can only visit someone who wants to be visited. In our experience the conversation goes better when it is framed as “so I stop worrying” rather than “because you cannot manage”.',
  ],
]

export function Nri() {
  return (
    <>
      <Seo
        title="For NRI families"
        description="DoorDoctor for Indians living abroad: scheduled nurse visits to your parents in Bengaluru, with a record and alerts you can read from any timezone."
        path="/nri"
      />

      <PageHero
        eyebrow="For families living abroad"
        title="Your parents will not tell you when something is wrong"
        description="Not out of stubbornness — out of consideration. They know there is nothing you can do from that far away, so they say they are fine. DoorDoctor puts a qualified nurse in the house on a schedule, and puts what actually happened in front of you."
        footnote="Same service, same pricing as any family plan. What changes is that you can read it at 7am in New Jersey."
      />

      <Section tone="default">
        <SectionHeading
          eyebrow="The distance problem"
          title="The gap is not care. It is information."
          description="There are good nurses and good doctors in Bengaluru. What there usually is not, is a way for you to know what any of them found — so you end up making decisions about your parents’ health from a summary of a summary, weeks late."
        />
      </Section>

      <Section tone="sunken">
        <SectionHeading eyebrow="What changes" title="What is different when you are abroad" />
        <div className="mt-10 grid gap-6 sm:grid-cols-2">
          {WHAT_IS_DIFFERENT.map(({ icon: Icon, title, body }) => (
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
        <div className="mt-8 flex flex-wrap gap-3">
          <LinkButton to="/pricing" variant="ghost">
            See pricing
          </LinkButton>
          <LinkButton to="/how-it-works" variant="ghost">
            How a visit works
          </LinkButton>
        </div>
      </Section>

      <Section tone="default">
        <SectionHeading
          eyebrow="Before you sign up"
          title="Three things we would rather you heard from us"
        />
        <dl className="mt-8 divide-y divide-border-subtle border-y border-border-subtle">
          {HONEST.map(([title, body]) => (
            <div key={title} className="grid gap-1 py-5 sm:grid-cols-[16rem_minmax(0,1fr)] sm:gap-6">
              <dt className="text-body font-semibold text-text-primary">{title}</dt>
              <dd className="text-body text-text-secondary">{body}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section tone="sunken" id="enquire">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,32rem)] lg:items-start">
          <SectionHeading
            eyebrow="Talk to us"
            title="Tell us where they are"
            description="Give us the area of Bengaluru your parents live in and roughly what they are managing. Tell us your timezone too, and we will call at an hour that works for you rather than for us."
          />
          <LeadForm
            defaultKind="nri"
            title="Enquire from abroad"
            description="Include your timezone and we will call at a reasonable hour for you."
          />
        </div>
      </Section>
    </>
  )
}
