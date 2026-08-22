import type { Plan, Quota } from '../types'

/**
 * Turning plan entitlements into English.
 *
 * Entitlements are data on the plan, so this reads keys rather than switching on
 * a tier name. A plan that gains an entitlement in a later phase gets a line
 * here and nowhere else; the pricing page and My Plan then agree by
 * construction.
 */

export interface EntitlementLine {
  label: string
  value: string
  /** False for an allowance of zero — rendered as a struck-through absence. */
  included: boolean
}

function countLine(limit: number | null | undefined, unit: string, per: string): EntitlementLine['value'] {
  if (limit === null) return 'Unlimited'
  if (!limit) return 'Not included'
  return `${limit} ${limit === 1 ? unit : `${unit}s`} per ${per}`
}

export function entitlementLines(plan: Plan): EntitlementLine[] {
  const e = plan.entitlements
  const lines: EntitlementLine[] = [
    {
      label: 'Home nurse visits',
      value: countLine(e.visits_per_month, 'visit', 'month'),
      included: e.visits_per_month === null || Boolean(e.visits_per_month),
    },
    {
      label: 'Doctor video consults',
      value: countLine(e.telemedicine_per_month, 'consult', 'month'),
      included: e.telemedicine_per_month === null || Boolean(e.telemedicine_per_month),
    },
    {
      label: 'Lab panels',
      value: countLine(e.lab_panels_per_year, 'panel', 'year'),
      included: e.lab_panels_per_year === null || Boolean(e.lab_panels_per_year),
    },
    {
      label: 'Care manager',
      value: e.care_manager
        ? `${e.care_manager === 'dedicated' ? 'Dedicated' : 'Shared'} · 1 to ${e.care_manager_ratio ?? '--'} families`
        : 'Not included',
      included: Boolean(e.care_manager),
    },
    {
      label: 'Health reports',
      value: e.report_cadence === 'weekly' ? 'Weekly and monthly' : 'Monthly',
      included: true,
    },
    {
      label: 'Family members',
      value: e.family_seats ? `${e.family_seats} logins` : 'Not included',
      included: Boolean(e.family_seats),
    },
    {
      label: 'Priority escalation',
      value: e.priority_escalation ? 'Included' : 'Not included',
      included: Boolean(e.priority_escalation),
    },
  ]
  return lines
}

/** `₹84 per resident per day` — the headline an organization plan is sold on. */
export function unitPriceLine(plan: Plan, formatMoney: (paise: number) => string): string | null {
  if (!plan.unit_paise || !plan.unit_label || !plan.unit_period) return null
  return `${formatMoney(plan.unit_paise)} per ${plan.unit_label} per ${plan.unit_period}`
}

/**
 * How close a meter is to its limit.
 *
 * `watch` at three quarters and `attention` when it is gone. Never `critical` —
 * a used-up visit allowance is a billing fact, and reserving the critical tone
 * for clinical states is what keeps it meaningful when a reading breaches.
 */
export function quotaTone(quota: Quota): 'good' | 'watch' | 'attention' | 'neutral' {
  if (quota.unlimited || quota.limit === null) return 'neutral'
  if (quota.limit === 0) return 'neutral'
  const ratio = quota.used / quota.limit
  if (ratio >= 1) return 'attention'
  if (ratio >= 0.75) return 'watch'
  return 'good'
}

export function quotaValueText(quota: Quota): string {
  if (quota.unlimited) return `${quota.used} used · unlimited`
  return `${quota.used} of ${quota.limit}`
}
