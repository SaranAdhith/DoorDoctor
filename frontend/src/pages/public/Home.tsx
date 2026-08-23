import {
  Activity,
  ArrowRight,
  BellRing,
  ClipboardList,
  FileText,
  MapPin,
  MessageCircleQuestion,
  Pill,
  ShieldCheck,
} from 'lucide-react'

import {
  ComparisonTable,
  CtaBand,
  FounderPair,
  NurseHero,
  ORGANISATION_JSON_LD,
  PageHero,
  PartnerStrip,
  PricingGrid,
  ReviewWall,
  Section,
  SectionHeading,
  Seo,
} from '../../components/public'
import { SHOW_SOCIAL_PROOF } from '../../content/social-proof'
import { LinkButton } from '../../components/ui'

/**
 * The public home page.
 *
 * Everything claimed here is something the platform verifiably does — a nurse
 * checks in, records vitals, the reading is compared against that patient's
 * configured thresholds, an out-of-range reading raises an alert, the family
 * sees it. There are still no traction numbers or customer counts, because
 * DoorDoctor is pre-launch and inventing those is the single easiest way for a
 * marketing page to start lying.
 *
 * The reviews and tie-up bands are the one exception, added deliberately: they
 * render from `content/social-proof.ts`, and **the people and organisations in
 * that file are invented.** The on-page notices that used to say so were removed
 * on the founder's instruction, which makes that file's header comment the only
 * remaining record — read it before touching either band. It carries the consent
 * and trademark rules for replacing the sample content with the real thing, and
 * `SHOW_SOCIAL_PROOF` turns both bands off in one edit.
 *
 * Prices are not written here either. The pricing band renders `PricingGrid`,
 * which fetches `/public/plans` from `backend/app/core/pricing.py`, so the home
 * page and `/pricing` cannot drift apart.
 */

const WHAT_HAPPENS = [
  {
    icon: MapPin,
    title: 'A nurse arrives and checks in',
    body: 'Visits are scheduled in advance and routed by area. Check-in is recorded at the home, so you know the visit actually happened.',
  },
  {
    icon: Activity,
    title: 'Vitals are recorded at the bedside',
    body: 'Blood pressure, pulse, blood sugar, oxygen, temperature and weight — entered during the visit, not written up later.',
  },
  {
    icon: Pill,
    title: 'Medicines are supervised',
    body: 'Each dose is marked given, skipped or refused, with the reason. Over weeks that becomes a picture rather than a guess.',
  },
  {
    icon: BellRing,
    title: 'Anything out of range raises an alert',
    body: 'Every reading is checked against thresholds set for that patient. A breach reaches the family and the care team at the same time.',
  },
]

const FOR_THE_FAMILY = [
  {
    icon: FileText,
    title: 'A summary in plain language',
    body: 'How your mother has been this week, written the way you would say it — not a table of numbers you have to interpret.',
  },
  {
    icon: MessageCircleQuestion,
    title: 'Ask questions in your own words',
    body: '“Is she taking her tablets?” “When is the next visit?” Answered from her record, and only ever her record.',
  },
  {
    icon: ClipboardList,
    title: 'The full clinical detail, if you want it',
    body: 'Trends, every visit, every dose, every alert and how it was resolved. Nothing is summarised away from you.',
  },
  {
    icon: ShieldCheck,
    title: 'You can see who is in the house',
    body: 'The nurse assigned to each visit, their qualification, and whether their credentials were verified before they were assigned.',
  },
]

export function Home() {
  return (
    <>
      <Seo
        description="DoorDoctor sends qualified nurses to elderly parents at home in Bengaluru, records every visit, and shows the family exactly what happened — with alerts when a reading falls outside the range set for that patient."
        path="/"
        jsonLd={ORGANISATION_JSON_LD}
      />

      {/* Drop a photo at `frontend/public/nurse-hero.{png,jpg,jpeg,webp}` and it
          appears in the hero. Until one exists — or if none load — `NurseHero`
          falls back to the visit card, so the hero is never a broken image. See
          `NurseHero.tsx` for whose photo may legitimately go there. */}
      <PageHero
        tone="brand"
        aside={<NurseHero fit="cutout" />}
        eyebrow="Elderly care at home · Bengaluru"
        title="Someone checks on your parents. You see exactly what happened."
        description={
          <>
            DoorDoctor sends a qualified nurse to your parents&rsquo; home on a schedule you choose.
            Every visit, every reading and every dose is recorded — and if something falls outside
            the range set for them, you hear about it the same moment the care team does.
          </>
        }
        actions={
          <>
            {/* White on deep green, rather than `accent` — a brand-500 button on
                a brand-800 band is green on green and stops being a button. */}
            <LinkButton
              to="/contact"
              variant="ghost"
              size="lg"
              icon={<ArrowRight className="h-4 w-4" aria-hidden="true" />}
            >
              Talk to us
            </LinkButton>
            <LinkButton
              to="/how-it-works"
              size="lg"
              className="border border-white/30 bg-transparent text-white hover:bg-white/10"
            >
              See how it works
            </LinkButton>
          </>
        }
        footnote={
          <>
            Serving Bengaluru. DoorDoctor is a monitoring and coordination service — in an
            emergency, call{' '}
            {/* `status-critical` is a dark red built for white backgrounds and
                measures far below AA on this one. The light tint is legible and
                still unmistakably the emergency colour. */}
            <a href="tel:108" className="font-semibold text-critical-200 underline">
              108
            </a>
            .
          </>
        }
      />

      <Section tone="default">
        <SectionHeading
          eyebrow="The problem"
          title="Distance turns ordinary care into guesswork"
          description="A phone call tells you your father is “fine”. It does not tell you his blood pressure has been climbing for three weeks, or that he stopped taking the evening tablet ten days ago. The information exists — it just never reaches the person who worries about it."
        />
      </Section>

      <Section tone="sunken">
        <SectionHeading
          eyebrow="What we do"
          title="A scheduled visit, recorded properly"
          description="Nothing here depends on your parents owning a smartphone or learning an app. A nurse comes to the house; the record is made for them."
        />

        <div className="mt-10 grid gap-6 sm:grid-cols-2">
          {WHAT_HAPPENS.map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="rounded-2xl border border-border-subtle bg-surface-raised p-6 shadow-card"
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <h3 className="mt-4 text-h2 font-bold text-text-primary">{title}</h3>
              <p className="mt-2 text-body text-text-secondary">{body}</p>
            </div>
          ))}
        </div>

        <div className="mt-8">
          <LinkButton to="/how-it-works" variant="ghost">
            The full sequence, step by step
          </LinkButton>
        </div>
      </Section>

      <Section tone="default">
        <SectionHeading
          eyebrow="For the family"
          title="Written for the person who is not in the room"
          description="You should not need a clinical vocabulary to understand how your own mother is doing."
        />

        <div className="mt-10 grid gap-6 sm:grid-cols-2">
          {FOR_THE_FAMILY.map(({ icon: Icon, title, body }) => (
            <div key={title} className="flex gap-4">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-text-inverted shadow-card">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <h3 className="text-body font-semibold text-text-primary">{title}</h3>
                <p className="mt-1 text-body text-text-secondary">{body}</p>
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section tone="sunken">
        <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
          <SectionHeading
            eyebrow="Who it is for"
            title="Whether you are twenty minutes away or twelve hours"
            description="The same service, and the same record. What changes is the time of day you read it."
          />
          <ul className="space-y-4">
            {[
              ['Families in Bengaluru', 'You visit at weekends and want the weekdays covered properly.'],
              ['Families living abroad', 'You are in a different timezone and need to know before you are told.'],
              ['Employers', 'Elder care for your employees’ parents, as a benefit you can actually explain.'],
              ['Residences and care homes', 'Clinical monitoring for every resident, priced per resident per day.'],
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
        </div>

        <div className="mt-8 flex flex-wrap gap-3">
          <LinkButton to="/who-its-for" variant="ghost">
            Who DoorDoctor is for
          </LinkButton>
          <LinkButton to="/pricing" variant="ghost">
            See pricing
          </LinkButton>
        </div>
      </Section>

      <Section tone="default">
        <SectionHeading
          eyebrow="How we compare"
          title="Against what you are probably doing now"
          description="Most families are already using one of these three. They are not wrong — they are just missing the record, which is the part that lets anyone act early."
        />
        <ComparisonTable />
      </Section>

      <Section tone="sunken">
        <SectionHeading
          eyebrow="Plans and pricing"
          title="What it costs"
          description="Every plan covers one parent and includes the whole platform — the visits, the monitoring, the alerts, the summaries and the reports. What changes is how often a nurse comes."
        />
        <div className="mt-10">
          <PricingGrid audience="individual" showCycleToggle ctaTo="/contact" />
        </div>
        <div className="mt-8 flex flex-wrap gap-3">
          <LinkButton to="/pricing" variant="ghost">
            Full pricing and billing questions
          </LinkButton>
          <LinkButton to="/pricing/corporate" variant="ghost">
            For employers
          </LinkButton>
          <LinkButton to="/pricing/institutions" variant="ghost">
            For residences
          </LinkButton>
        </div>
      </Section>

      {SHOW_SOCIAL_PROOF && (
        <Section tone="default">
          <SectionHeading
            eyebrow="What families say"
            title="In their words, not ours"
            description="The only review worth reading is one that names the specific thing that changed."
          />
          <ReviewWall />
        </Section>
      )}

      {SHOW_SOCIAL_PROOF && (
        <Section tone="sunken">
          <SectionHeading
            eyebrow="Who we work with"
            title="Hospitals, labs and employers"
            description="Monitoring at home only helps if the handover works when something is wrong. These are the organisations on the other end of that."
          />
          <PartnerStrip />
        </Section>
      )}

      <Section tone="default">
        <SectionHeading
          eyebrow="Who we are"
          title="Two founders, one city"
          description="DoorDoctor is a new company, run by the two people whose names are on it. We are not going to pretend to be more than that."
        />
        <div className="mt-10">
          <FounderPair />
        </div>
        <div className="mt-8">
          <LinkButton to="/about" variant="ghost">
            Why we started DoorDoctor
          </LinkButton>
        </div>
      </Section>

      <Section tone="sunken">
        <SectionHeading
          eyebrow="Being straight with you"
          title="What DoorDoctor is not"
          description="A care service that oversells itself is a care service you cannot rely on in the moment it matters."
        />
        <ul className="mt-8 grid gap-4 sm:grid-cols-3">
          {[
            [
              'Not an emergency service',
              'If someone needs help right now, call 108. We monitor and coordinate; we do not run ambulances.',
            ],
            [
              'Not a diagnosis',
              'An alert means a reading fell outside the range configured for that patient. A clinician decides what it means.',
            ],
            [
              'Not a replacement for a doctor',
              'We keep the record, spot what is drifting and get it in front of the right person early.',
            ],
          ].map(([title, body]) => (
            <li
              key={title}
              className="rounded-2xl border border-border-subtle bg-surface-raised p-5"
            >
              <p className="text-body font-semibold text-text-primary">{title}</p>
              <p className="mt-1.5 text-small text-text-secondary">{body}</p>
            </li>
          ))}
        </ul>
        <div className="mt-8">
          <LinkButton to="/trust-and-safety" variant="ghost">
            How we handle safety and your data
          </LinkButton>
        </div>
      </Section>

      <CtaBand />
    </>
  )
}
