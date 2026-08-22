import { Check, Minus } from 'lucide-react'

import { cn } from '../../lib/cn'
import { formatINR } from '../../lib/money'
import { entitlementLines, unitPriceLine } from '../../lib/plan'
import type { Plan } from '../../types'
import { LinkButton } from '../ui'

/**
 * One plan, priced from the server.
 *
 * **Every number on this card comes out of `plan`.** Nothing here is typed as a
 * literal, because `backend/app/core/pricing.py` is the only place a price is
 * written down and a marketing page that restates one is the first thing to go
 * stale. The "Recommended" treatment reads `plan.recommended` rather than
 * comparing against a plan code, for the same reason `lib/plan.ts` reads
 * entitlement keys rather than switching on a tier name.
 */

interface Props {
  plan: Plan
  cycle: 'monthly' | 'annual'
  /** How many months an annual price gives away, from the same payload. */
  annualMonthsFree: number
  /** Where "Get started" goes. Pricing pages point it at their own enquiry form. */
  ctaTo?: string
  ctaLabel?: string
}

export function PlanCard({
  plan,
  cycle,
  annualMonthsFree,
  ctaTo = '/contact',
  ctaLabel = 'Get started',
}: Props) {
  const annual = cycle === 'annual' && plan.annual_paise !== null
  const price = annual ? plan.annual_paise! : plan.monthly_paise
  const perUnit = unitPriceLine(plan, formatINR)
  const lines = entitlementLines(plan)

  return (
    <div
      className={cn(
        'relative flex flex-col rounded-2xl border bg-surface-raised p-6',
        plan.recommended
          ? 'border-brand-500 shadow-raised ring-1 ring-brand-500'
          : 'border-border-subtle shadow-card',
      )}
    >
      {plan.recommended && (
        <span className="absolute -top-3 left-6 rounded-full bg-brand-500 px-3 py-1 text-caption font-bold uppercase tracking-wide text-text-inverted">
          Recommended
        </span>
      )}

      <h3 className="text-h2 font-bold text-text-primary">{plan.name}</h3>
      <p className="mt-1.5 min-h-[2.5rem] text-small text-text-secondary">{plan.tagline}</p>

      <p className="mt-5 flex items-baseline gap-1.5">
        <span className="tnum text-display font-bold tracking-tight text-text-primary">
          {formatINR(price)}
        </span>
        <span className="text-small text-text-secondary">{annual ? '/year' : '/month'}</span>
      </p>

      {/* The headline an organization plan is actually sold on. */}
      {perUnit && <p className="mt-1 text-small font-medium text-brand-700">{perUnit}</p>}

      {annual ? (
        <p className="mt-1 text-small text-status-good">
          {annualMonthsFree} months free compared with paying monthly
        </p>
      ) : (
        plan.annual_paise !== null && (
          <p className="mt-1 text-small text-text-muted">
            {formatINR(plan.annual_paise)}/year if you pay annually
          </p>
        )
      )}

      {plan.unit_included !== null && plan.unit_label && (
        <p className="mt-3 text-small text-text-secondary">
          Covers up to{' '}
          <span className="font-semibold text-text-primary">
            {plan.unit_included} {plan.unit_label}
            {plan.unit_included === 1 ? '' : 's'}
          </span>
          .
        </p>
      )}

      <ul className="mt-6 flex-1 space-y-2.5 border-t border-border-subtle pt-6">
        {lines.map((line) => (
          <li key={line.label} className="flex items-start gap-2.5">
            {line.included ? (
              <Check
                className="mt-0.5 h-4 w-4 shrink-0 text-status-good"
                aria-hidden="true"
              />
            ) : (
              <Minus className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
            )}
            <span className="text-small">
              <span className={cn(line.included ? 'text-text-primary' : 'text-text-muted')}>
                {line.label}
              </span>
              <span className="block text-caption text-text-secondary">{line.value}</span>
            </span>
          </li>
        ))}
      </ul>

      <LinkButton
        to={ctaTo}
        variant={plan.recommended ? 'accent' : 'ghost'}
        fullWidth
        className="mt-6"
      >
        {ctaLabel}
      </LinkButton>
    </div>
  )
}
