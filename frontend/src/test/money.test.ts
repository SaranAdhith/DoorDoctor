import { describe, expect, it } from 'vitest'

import { formatINR, formatINRCompact, formatPrice } from '../lib/money'

/**
 * The same cases the backend asserts in `test_billing.py`. If either side
 * changes how it groups digits, one of the two suites fails.
 */
describe('formatINR', () => {
  it.each([
    [0, '₹0'],
    [19_900, '₹199'],
    [350_000, '₹3,500'],
    [7_800_000, '₹78,000'],
    [12_345_678, '₹1,23,456.78'],
    [100_000_000, '₹10,00,000'],
  ])('formats %i paise as %s', (paise, expected) => {
    expect(formatINR(paise)).toBe(expected)
  })

  it('groups by lakh, not by thousand', () => {
    // The difference that matters: en-US would give ₹1,234,560.
    expect(formatINR(123_456_000)).toBe('₹12,34,560')
  })

  it('keeps the sign outside the symbol', () => {
    expect(formatINR(-350_000)).toBe('-₹3,500')
  })
})

describe('formatINRCompact', () => {
  it.each([
    [350_000, '₹3,500'],
    [17_600_000, '₹1.8L'],
    [211_200_000, '₹21.1L'],
    [1_000_000_000, '₹1Cr'], // ₹1,00,00,000
    [12_500_000_000, '₹12.5Cr'],
  ])('shortens %i paise to %s', (paise, expected) => {
    expect(formatINRCompact(paise)).toBe(expected)
  })
})

describe('formatPrice', () => {
  it('says what the price buys', () => {
    expect(formatPrice(350_000, 'monthly')).toBe('₹3,500/month')
    expect(formatPrice(3_500_000, 'annual')).toBe('₹35,000/year')
  })

  it('omits the suffix for an unknown cycle', () => {
    expect(formatPrice(49_900, 'one_off')).toBe('₹499')
  })
})
