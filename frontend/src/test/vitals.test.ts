import { describe, expect, it } from 'vitest'

import { bloodPressure, evaluateReading, thresholdText } from '../lib/vitals'
import type { Threshold, Vitals } from '../types'

const thresholds: Threshold[] = [
  { metric: 'systolic_bp', low_threshold: 90, high_threshold: 140, enabled: true },
  { metric: 'diastolic_bp', low_threshold: 60, high_threshold: 90, enabled: true },
  { metric: 'spo2', low_threshold: 94, high_threshold: 100, enabled: true },
  { metric: 'weight', low_threshold: 35, high_threshold: 120, enabled: false },
]

describe('evaluateReading', () => {
  it('marks a reading above the configured high threshold', () => {
    expect(evaluateReading('systolic_bp', 148, thresholds)).toBe('high')
  })

  it('marks a reading below the configured low threshold', () => {
    expect(evaluateReading('spo2', 91, thresholds)).toBe('low')
  })

  it('marks a reading inside the range as normal', () => {
    expect(evaluateReading('systolic_bp', 130, thresholds)).toBe('normal')
  })

  it('treats the boundary value as in range', () => {
    expect(evaluateReading('systolic_bp', 140, thresholds)).toBe('normal')
  })

  it('reports unknown for disabled or missing thresholds', () => {
    expect(evaluateReading('weight', 64, thresholds)).toBe('unknown')
    expect(evaluateReading('heart_rate', 82, thresholds)).toBe('unknown')
    expect(evaluateReading('systolic_bp', null, thresholds)).toBe('unknown')
  })
})

describe('thresholdText', () => {
  it('renders the configured range', () => {
    expect(thresholdText('systolic_bp', thresholds)).toBe('90 - 140')
  })

  it('returns null when monitoring is disabled', () => {
    expect(thresholdText('weight', thresholds)).toBeNull()
  })
})

describe('bloodPressure', () => {
  it('formats systolic over diastolic', () => {
    expect(bloodPressure({ systolic_bp: 148, diastolic_bp: 92 } as Vitals)).toBe('148/92')
  })

  it('handles a missing reading', () => {
    expect(bloodPressure(null)).toBe('--')
  })
})
