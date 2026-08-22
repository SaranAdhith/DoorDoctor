import { useState } from 'react'

import { publicApi } from '../../api/public'
import { useAsync } from '../../hooks/useAsync'
import { cn } from '../../lib/cn'
import { formatINR } from '../../lib/money'
import type { PublicPlans } from '../../types'
import { ErrorState, SegmentedControl, SkeletonCard } from '../ui'
import { PlanCard } from './PlanCard'

/**
 * The pricing table, fetched rather than typed.
 *
 * Every pricing page uses this one component with a different `audience`, so
 * there is exactly one place that knows how to turn the server's price list
 * into cards. It owns its own loading, error and retry states because a
 * marketing page is still a page that loads data, and Phase 2's rule — skeleton,
 * empty, error-with-retry on every list — does not stop applying because the
 * page is trying to sell something.
 */

type Cycle = 'monthly' | 'annual'

const CYCLES: ReadonlyArray<{ value: Cycle; label: string }> = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'annual', label: 'Annual' },
]

interface Props {
  audience: 'individual' | 'corporate' | 'institution'
  /** Only shown when the audience actually has an annual price to switch to. */
  showCycleToggle?: boolean
  ctaTo?: string
  ctaLabel?: string
  columns?: 2 | 3
}

export function PricingGrid({
  audience,
  showCycleToggle = false,
  ctaTo,
  ctaLabel,
  columns = 3,
}: Props) {
  const [cycle, setCycle] = useState<Cycle>('monthly')
  const { data, loading, error, reload } = useAsync<PublicPlans>(
    () => publicApi.plans(audience),
    [audience],
  )

  const grid = cn('grid gap-6', columns === 2 ? 'md:grid-cols-2' : 'md:grid-cols-2 lg:grid-cols-3')

  if (loading) {
    return (
      <div className={grid}>
        {Array.from({ length: columns }).map((_, index) => (
          <SkeletonCard key={index} lines={8} />
        ))}
      </div>
    )
  }

  if (error || !data) {
    return (
      <ErrorState
        message={error ?? 'Our price list could not be loaded just now.'}
        onRetry={() => void reload()}
      />
    )
  }

  // Every plan in the payload is already filtered to this audience by the server.
  const plans = data.plans
  const anyAnnual = plans.some((plan) => plan.annual_paise !== null)

  return (
    <div>
      {showCycleToggle && anyAnnual && (
        <div className="mb-8 flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:gap-4">
          <SegmentedControl
            legend="Billing period"
            hideLegend
            value={cycle}
            options={CYCLES}
            onChange={setCycle}
          />
          <p className="text-small text-status-good">
            Pay annually and {data.annual_months_free} months are free.
          </p>
        </div>
      )}

      <div className={grid}>
        {plans.map((plan) => (
          <PlanCard
            key={plan.code}
            plan={plan}
            cycle={cycle}
            annualMonthsFree={data.annual_months_free}
            ctaTo={ctaTo}
            ctaLabel={ctaLabel}
          />
        ))}
      </div>

      {audience === 'individual' && data.add_ons.length > 0 && (
        <div className="mt-10 rounded-2xl border border-border-subtle bg-surface p-6">
          <h3 className="text-h2 font-bold text-text-primary">Add these to any plan</h3>
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {data.add_ons.map((addOn) => (
              <li
                key={addOn.code}
                className="flex items-baseline justify-between gap-4 rounded-xl border border-border-subtle bg-surface-raised px-4 py-3"
              >
                <span className="text-body font-medium text-text-primary">{addOn.name}</span>
                <span className="tnum shrink-0 text-body font-semibold text-text-primary">
                  {formatINR(addOn.price_paise)}{' '}
                  <span className="text-small font-normal text-text-secondary">{addOn.unit}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
