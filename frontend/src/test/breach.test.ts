import { describe, expect, it } from 'vitest'

import { breachContext, breachLabel, breachValue } from '../lib/breach'
import type { BreachedParameter } from '../types'

/**
 * Phase 9 gave alerts three sources, and each describes its finding
 * differently. Three screens render breaches and all three assumed the
 * threshold shape — an abnormal lab result crashed both alert screens to a
 * blank page, because a lab result has a reference range and no `threshold` to
 * call `.toFixed()` on.
 *
 * These tests pin every shape the backend actually emits. If a fourth alert
 * source is added, this file is where it declares itself.
 */

const THRESHOLD: BreachedParameter = {
  metric: 'systolic_bp',
  value: 148,
  threshold: 140,
  direction: 'above',
  unit: ' mmHg',
}

const LAB: BreachedParameter = {
  metric: 'fasting_glucose',
  label: 'Fasting blood sugar',
  value: 185,
  unit: 'mg/dL',
  ref_low: 70,
  ref_high: 110,
  flag: 'high',
}

const WEARABLE: BreachedParameter = {
  metric: 'spo2',
  value: 87,
  reason: 'oxygen level 87%, below 90%',
  source: 'device',
}

describe('breach rendering', () => {
  it('renders a threshold-engine breach with its bound and direction', () => {
    expect(breachLabel(THRESHOLD)).toBe('Systolic BP')
    expect(breachValue(THRESHOLD)).toBe('148 mmHg')
    expect(breachContext(THRESHOLD)).toContain('above configured threshold 140')
  })

  it('renders a lab result as a range, not as a single bound', () => {
    // Flattening a range to one number throws away half of what a reader needs
    // to check the flag themselves.
    expect(breachLabel(LAB)).toBe('Fasting blood sugar')
    expect(breachValue(LAB)).toBe('185mg/dL')
    expect(breachContext(LAB)).toBe('expected 70–110mg/dL')
  })

  it('renders a wearable breach using the sentence it arrived with', () => {
    expect(breachValue(WEARABLE)).toBe('87')
    expect(breachContext(WEARABLE)).toBe('oxygen level 87%, below 90%')
  })

  it('never reads a field the shape does not have', () => {
    // The exact crash: `.toFixed()` on an undefined threshold.
    for (const breach of [THRESHOLD, LAB, WEARABLE]) {
      expect(() => breachContext(breach)).not.toThrow()
      expect(() => breachLabel(breach)).not.toThrow()
      expect(() => breachValue(breach)).not.toThrow()
    }
  })

  it('survives a breach carrying nothing but a value', () => {
    const bare: BreachedParameter = { metric: 'unknown_thing', value: 5 }
    expect(breachLabel(bare)).toBe('unknown_thing')
    expect(breachValue(bare)).toBe('5')
    expect(breachContext(bare)).toBe('')
  })

  it('handles a one-sided reference range', () => {
    expect(breachContext({ ...LAB, ref_low: null })).toBe('expected up to 110mg/dL')
    expect(breachContext({ ...LAB, ref_high: null })).toBe('expected at least 70mg/dL')
  })

  it('avoids the word "threshold" in the family register', () => {
    // Phase 6 banned it, and the family alert detail is a family-facing surface.
    const plain = breachContext(THRESHOLD, 'plain')
    expect(plain).not.toContain('threshold')
    expect(plain).toContain('140')
  })

  it('keeps the clinical register for admins, who are clinical staff', () => {
    expect(breachContext(THRESHOLD, 'clinical')).toContain('threshold')
  })
})
