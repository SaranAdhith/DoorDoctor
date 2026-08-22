import {
  LeadForm,
  PageHero,
  PricingGrid,
  Section,
  SectionHeading,
  Seo,
} from '../../components/public'

/**
 * Corporate pricing. Same `PricingGrid`, different audience — the price comes
 * from the server exactly as it does on the family page.
 */

const WHY = [
  {
    title: 'It is the interruption nobody schedules',
    body: 'An employee managing a parent’s care is doing it during the working day, because that is when clinics answer the phone. It is not absenteeism and it does not show up as any measurable thing — it just quietly costs afternoons.',
  },
  {
    title: 'It is concrete in a way most benefits are not',
    body: '“A qualified nurse visits your parents and you can see what happened” is a sentence an employee can repeat at home. Most wellness benefits do not survive that test.',
  },
  {
    title: 'It applies to people you are trying to keep',
    body: 'The employees whose parents need care are usually the ones fifteen years into their careers. This is the population a benefit budget is most worth spending on.',
  },
]

const HOW = [
  ['You enrol employees', 'Billed per enrolled employee, per month. Enrolment moves as your team moves.'],
  ['Each enrolled employee gets the service', 'Their parent gets scheduled nurse visits, monitoring and alerts, exactly as an individual subscriber would.'],
  ['The employee owns the record', 'You are the payer, not the recipient. Their parents’ clinical record belongs to them, and you never see it.'],
  ['You get one invoice', 'A single monthly invoice for the enrolled headcount, downloadable as a PDF.'],
]

export function PricingCorporate() {
  return (
    <>
      <Seo
        title="Elder care as an employee benefit"
        description="DoorDoctor for employers: scheduled home nurse visits and monitoring for your employees' parents, priced per enrolled employee per month."
        path="/pricing/corporate"
      />

      <PageHero
        eyebrow="For employers"
        title="Elder care as an employee benefit"
        description="Your employees are coordinating their parents’ care from their desks. This is the benefit that takes that off them — priced per enrolled employee, with one invoice and no clinical data flowing back to you."
      />

      <Section tone="default">
        <SectionHeading
          eyebrow="Pricing"
          title="Per enrolled employee, per month"
          description="Enrolment is monthly, so it moves with your headcount rather than a fixed annual commitment."
        />
        <div className="mt-10">
          <PricingGrid
            audience="corporate"
            columns={2}
            ctaTo="/pricing/corporate#enquire"
            ctaLabel="Request a proposal"
          />
        </div>
      </Section>

      <Section tone="sunken">
        <SectionHeading eyebrow="Why this benefit" title="What it is actually buying" />
        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {WHY.map((item) => (
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
          eyebrow="How it works"
          title="Four things to know before you propose it internally"
        />
        <dl className="mt-8 divide-y divide-border-subtle border-y border-border-subtle">
          {HOW.map(([title, body]) => (
            <div key={title} className="grid gap-1 py-5 sm:grid-cols-[16rem_minmax(0,1fr)] sm:gap-6">
              <dt className="text-body font-semibold text-text-primary">{title}</dt>
              <dd className="text-body text-text-secondary">{body}</dd>
            </div>
          ))}
        </dl>

        <p className="mt-8 rounded-xl border border-border-subtle bg-surface px-5 py-4 text-body text-text-secondary">
          <span className="font-semibold text-text-primary">On privacy, to be unambiguous:</span> an
          employer is the payer and nothing more. You will never see an employee&rsquo;s parent&rsquo;s
          readings, visits, alerts or reports. Your invoice tells you how many people are enrolled,
          and that is all it tells you.
        </p>
      </Section>

      <Section tone="sunken" id="enquire">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,32rem)] lg:items-start">
          <SectionHeading
            eyebrow="Talk to us"
            title="Ask for a proposal"
            description="Tell us roughly how many employees you would enrol and where they are based. We will come back with a written proposal you can take to your benefits committee."
          />
          <LeadForm
            defaultKind="corporate"
            title="Request a corporate proposal"
            description="We will reply within one working day."
            submitLabel="Request a proposal"
          />
        </div>
      </Section>
    </>
  )
}
