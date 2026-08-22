import {
  LeadForm,
  PageHero,
  PricingGrid,
  Section,
  SectionHeading,
  Seo,
} from '../../components/public'

/**
 * Institutional pricing.
 *
 * The bands are sold on a per-resident-per-day rate with a monthly price
 * alongside it, and both come from the server — `PlanCard` renders
 * `unit_paise`/`unit_period` through `lib/plan.unitPriceLine`, so the headline
 * rate and the monthly figure cannot disagree with each other or with an
 * invoice.
 */

const WHAT_CHANGES = [
  {
    title: 'The record survives the shift change',
    body: 'Handovers are verbal and staff rotate. A resident’s readings, their ranges and their medication history stay in one place regardless of who was on duty when.',
  },
  {
    title: 'The same thresholds for every resident',
    body: 'Each resident gets ranges configured for them, and every reading is checked against them as it is entered — not reviewed at the end of a shift.',
  },
  {
    title: 'Escalation has a named owner',
    body: 'An out-of-range reading raises an alert that stays open until someone resolves it and records what they did. Nothing closes because a shift ended.',
  },
  {
    title: 'Families can be given visibility',
    body: 'The relatives of your residents are usually the hardest people to keep informed. This is the part that answers them without adding a phone call to somebody’s shift.',
  },
]

export function PricingInstitutions() {
  return (
    <>
      <Seo
        title="Pricing for residences and care homes"
        description="DoorDoctor for residences and care homes: clinical monitoring, threshold alerts and a durable record for every resident, priced per resident per day."
        path="/pricing/institutions"
      />

      <PageHero
        eyebrow="For residences and care homes"
        title="Clinical monitoring for every resident"
        description="Priced per resident per day, in bands. What you get is a consistent clinical record and a threshold-alerting layer that does not depend on who is on shift."
      />

      <Section tone="default">
        <SectionHeading
          eyebrow="Pricing"
          title="Three bands, quoted per resident per day"
          description="The monthly figure is what you are invoiced; the daily rate is how to compare it against what a bed already costs you."
        />
        <div className="mt-10">
          <PricingGrid
            audience="institution"
            ctaTo="/pricing/institutions#enquire"
            ctaLabel="Arrange a site visit"
          />
        </div>
        <p className="mt-8 text-small text-text-secondary">
          More residents than the largest band covers? Tell us the number and we will quote for it.
        </p>
      </Section>

      <Section tone="sunken">
        <SectionHeading eyebrow="What changes for you" title="What a monitoring layer adds" />
        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {WHAT_CHANGES.map((item) => (
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
          eyebrow="Being clear"
          title="This sits alongside your staff, not instead of them"
          description="We are not proposing to replace your care team. DoorDoctor supplies the clinical monitoring, the escalation path and the record; your staff continue to run the residence. If what you need is agency staffing, we are the wrong supplier and we would rather say so at the first meeting."
        />
      </Section>

      <Section tone="sunken" id="enquire">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,32rem)] lg:items-start">
          <SectionHeading
            eyebrow="Talk to us"
            title="Arrange a site visit"
            description="Tell us how many residents you have and where you are. We will come and look before quoting anything — a residence is not something to price over email."
          />
          <LeadForm
            defaultKind="institution"
            title="Enquire about a residence"
            description="We will reply within one working day."
            submitLabel="Arrange a site visit"
          />
        </div>
      </Section>
    </>
  )
}
