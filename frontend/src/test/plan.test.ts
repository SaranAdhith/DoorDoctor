import { describe, expect, it } from 'vitest'

import { entitlementLines, quotaTone, quotaValueText, unitPriceLine } from '../lib/plan'
import { formatINR } from '../lib/money'
import type { Plan, Quota } from '../types'

function plan(entitlements: Plan['entitlements'], extra: Partial<Plan> = {}): Plan {
  return {
    id: 1,
    code: 'care_plus',
    name: 'Care Plus',
    audience: 'individual',
    tagline: '',
    monthly_paise: 350_000,
    annual_paise: 3_500_000,
    recommended: true,
    unit_label: null,
    unit_included: null,
    unit_paise: null,
    unit_period: null,
    entitlements,
    ...extra,
  }
}

function quota(over: Partial<Quota> = {}): Quota {
  return {
    quota: 'visits',
    label: 'Home nurse visits',
    period: 'month',
    limit: 8,
    used: 2,
    remaining: 6,
    unlimited: false,
    period_start: '2026-08-17T09:00:00',
    period_end: '2026-09-17T09:00:00',
    ...over,
  }
}

describe('entitlementLines', () => {
  it('reads the plan data rather than the tier name', () => {
    const lines = entitlementLines(
      plan({ visits_per_month: 8, telemedicine_per_month: 1, lab_panels_per_year: 2 }),
    )
    const byLabel = Object.fromEntries(lines.map((line) => [line.label, line.value]))

    expect(byLabel['Home nurse visits']).toBe('8 visits per month')
    expect(byLabel['Doctor video consults']).toBe('1 consult per month')
    expect(byLabel['Lab panels']).toBe('2 panels per year')
  })

  it('treats null as unlimited, not as none', () => {
    const lines = entitlementLines(plan({ visits_per_month: null }))
    const visits = lines.find((line) => line.label === 'Home nurse visits')

    expect(visits?.value).toBe('Unlimited')
    expect(visits?.included).toBe(true)
  })

  it('marks a zero allowance as not included', () => {
    const lines = entitlementLines(plan({ telemedicine_per_month: 0 }))
    const consults = lines.find((line) => line.label === 'Doctor video consults')

    expect(consults?.value).toBe('Not included')
    expect(consults?.included).toBe(false)
  })

  it('describes the care manager with its ratio', () => {
    const dedicated = entitlementLines(
      plan({ care_manager: 'dedicated', care_manager_ratio: 10 }),
    ).find((line) => line.label === 'Care manager')
    const shared = entitlementLines(plan({ care_manager: 'shared', care_manager_ratio: 20 })).find(
      (line) => line.label === 'Care manager',
    )

    expect(dedicated?.value).toBe('Dedicated · 1 to 10 families')
    expect(shared?.value).toBe('Shared · 1 to 20 families')
  })

  it('singularises a count of one', () => {
    const lines = entitlementLines(plan({ visits_per_month: 1 }))
    expect(lines[0].value).toBe('1 visit per month')
  })
})

describe('unitPriceLine', () => {
  it('states the headline an organization plan is sold on', () => {
    const institutional = plan(
      {},
      { unit_label: 'resident', unit_period: 'day', unit_paise: 8_400 },
    )
    expect(unitPriceLine(institutional, formatINR)).toBe('₹84 per resident per day')
  })

  it('is absent for an individual plan', () => {
    expect(unitPriceLine(plan({}), formatINR)).toBeNull()
  })
})

describe('quotaTone', () => {
  it('warns at three quarters and flags an exhausted allowance', () => {
    expect(quotaTone(quota({ used: 2, limit: 8 }))).toBe('good')
    expect(quotaTone(quota({ used: 6, limit: 8 }))).toBe('watch')
    expect(quotaTone(quota({ used: 8, limit: 8 }))).toBe('attention')
  })

  it('never returns critical — that tone belongs to clinical states', () => {
    const tones = [0, 4, 8, 20].map((used) => quotaTone(quota({ used, limit: 8 })))
    expect(tones).not.toContain('critical')
  })

  it('stays neutral when there is no limit to approach', () => {
    expect(quotaTone(quota({ unlimited: true, limit: null }))).toBe('neutral')
  })
})

describe('quotaValueText', () => {
  it('reads as a fraction of the allowance', () => {
    expect(quotaValueText(quota({ used: 2, limit: 8 }))).toBe('2 of 8')
  })

  it('says what unlimited means', () => {
    expect(quotaValueText(quota({ used: 5, unlimited: true, limit: null }))).toBe('5 used · unlimited')
  })
})
