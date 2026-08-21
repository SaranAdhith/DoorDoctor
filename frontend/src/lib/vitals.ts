import type { Threshold, VitalMetric, Vitals } from '../types'

export type ReadingState = 'normal' | 'high' | 'low' | 'unknown'

/**
 * Mirror of the backend threshold comparison, used only to colour the UI.
 * The backend remains the single source of truth for alerts.
 */
export function evaluateReading(
  metric: VitalMetric,
  value: number | null | undefined,
  thresholds: Threshold[],
): ReadingState {
  if (value === null || value === undefined) return 'unknown'
  const threshold = thresholds.find((item) => item.metric === metric)
  if (!threshold || !threshold.enabled) return 'unknown'
  if (threshold.high_threshold !== null && value > threshold.high_threshold) return 'high'
  if (threshold.low_threshold !== null && value < threshold.low_threshold) return 'low'
  return 'normal'
}

export function readingStateLabel(state: ReadingState): string {
  switch (state) {
    case 'high':
      return 'Above range'
    case 'low':
      return 'Below range'
    case 'normal':
      return 'In range'
    default:
      return 'Not monitored'
  }
}

export function thresholdText(metric: VitalMetric, thresholds: Threshold[]): string | null {
  const threshold = thresholds.find((item) => item.metric === metric)
  if (!threshold || !threshold.enabled) return null
  const low = threshold.low_threshold
  const high = threshold.high_threshold
  if (low !== null && high !== null) return `${low} - ${high}`
  if (high !== null) return `up to ${high}`
  if (low !== null) return `from ${low}`
  return null
}

export const TREND_METRICS: { key: 'blood_pressure' | VitalMetric; label: string }[] = [
  { key: 'blood_pressure', label: 'Blood Pressure' },
  { key: 'spo2', label: 'SpO2' },
  { key: 'blood_glucose', label: 'Glucose' },
  { key: 'heart_rate', label: 'Heart Rate' },
  { key: 'temperature', label: 'Temperature' },
  { key: 'weight', label: 'Weight' },
]

export function bloodPressure(vitals: Vitals | null | undefined): string {
  if (!vitals) return '--'
  return `${Math.round(vitals.systolic_bp)}/${Math.round(vitals.diastolic_bp)}`
}
