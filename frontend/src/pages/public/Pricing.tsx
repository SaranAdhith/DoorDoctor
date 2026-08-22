import {
  CtaBand,
  FaqList,
  PageHero,
  PricingGrid,
  Section,
  SectionHeading,
  Seo,
  faqJsonLd,
  type FaqItem,
} from '../../components/public'
import { LinkButton } from '../../components/ui'

/**
 * Family pricing.
 *
 * **No price is written on this page.** Every number comes from `PricingGrid`,
 * which fetches `/public/plans`, which serialises `backend/app/core/pricing.py`.
 * If you find yourself typing a rupee figure into this file, that is the bug.
 */

const PRICING_FAQ: FaqItem[] = [
  {
    question: 'Is there a joining fee or a lock-in?',
    answer:
      'No joining fee, and no lock-in on the monthly plans. You can change plan or cancel from inside your account; a cancellation takes effect at the end of the period you have already paid for.',
  },
  {
    question: 'What does paying annually save?',
    answer:
      'Paying for a year up front costs ten months rather than twelve, so two months are free. The plans and everything in them are otherwise identical.',
  },
  {
    question: 'Can I change plan later?',
    answer:
      'Yes, at any time. Moving up takes effect immediately and the unused part of your current month is credited against the change, so you are never billed twice for the same days.',
  },
  {
    question: 'What if my parents need more visits one month?',
    answer:
      'Talk to us. Care is not evenly spaced — a bad fortnight after a hospital discharge is normal — and we would rather adjust the plan than have you ration visits.',
  },
  {
    question: 'Do you cover both my parents?',
    answer:
      'Each plan covers one person. If both your parents need care, tell us when you enquire and we will price it properly rather than making you buy two full plans by default.',
  },
  {
    question: 'How do I pay?',
    answer:
      'You will be invoiced for each billing period, and every invoice is downloadable as a PDF from your account. Any credits you have earned — from a referral, or from the loyalty reward at twelve paid months — are applied to your next invoice automatically.',
  },
]

export function Pricing() {
  return (
    <>
      <Seo
        title="Pricing for families"
        description="DoorDoctor plans for families in Bengaluru: scheduled home nurse visits, recorded vitals, medication supervision and threshold alerts. Monthly or annual, no lock-in."
        path="/pricing"
        jsonLd={faqJsonLd(PRICING_FAQ)}
      />

      <PageHero
        eyebrow="Pricing"
        title="One price, everything included"
        description="Every plan covers one parent and includes the whole platform — the visits, the monitoring, the alerts, the summaries and the reports. What changes between plans is how often a nurse comes and how much clinical support sits behind it."
        footnote="Prices are per month for one person. No joining fee. Cancel at the end of any paid period."
      />

      <Section tone="default">
        <PricingGrid audience="individual" showCycleToggle ctaTo="/contact" />
      </Section>

      <Section tone="sunken">
        <SectionHeading
          eyebrow="Included on every plan"
          title="The platform is not the upsell"
          description="These are on the smallest plan and every plan above it. We do not think a family should pay extra to be able to see their own parent's record."
        />
        <ul className="mt-8 grid gap-3 sm:grid-cols-2">
          {[
            'A plain-language summary of how they have been',
            'Threshold alerts on every recorded reading',
            'The full clinical record: trends, visits, doses, alerts',
            'Health reports as downloadable PDFs',
            'Ask questions in your own words and get answers from their record',
            'Nurse credentials visible before the visit',
            'Logins for other family members',
            'Invoices you can download at any time',
          ].map((item) => (
            <li
              key={item}
              className="rounded-xl border border-border-subtle bg-surface-raised px-4 py-3 text-body text-text-secondary"
            >
              {item}
            </li>
          ))}
        </ul>
      </Section>

      <Section tone="default">
        <SectionHeading
          eyebrow="Organisations"
          title="Buying for more than one household?"
          description="Employers and residences are priced differently, because the unit is not a family."
        />
        <div className="mt-8 flex flex-wrap gap-3">
          <LinkButton to="/pricing/corporate" variant="ghost">
            Elder care as an employee benefit
          </LinkButton>
          <LinkButton to="/pricing/institutions" variant="ghost">
            Residences and care homes
          </LinkButton>
        </div>
      </Section>

      <Section tone="sunken">
        <SectionHeading eyebrow="Questions" title="About pricing and billing" />
        <div className="mt-8">
          <FaqList items={PRICING_FAQ} idPrefix="pricing-faq" />
        </div>
        <div className="mt-8">
          <LinkButton to="/faq" variant="ghost">
            All frequently asked questions
          </LinkButton>
        </div>
      </Section>

      <CtaBand
        title="Not sure which plan fits?"
        description="Tell us how your parents are doing and we will tell you which plan we would actually recommend — including the smaller one, if that is the honest answer."
      />
    </>
  )
}
