import { METRIC_LABELS, formatNumber } from './format'
import type { BreachedParameter, VitalMetric } from '../types'

/**
 * Rendering a breached parameter, in one place.
 *
 * Since Phase 9 an alert can come from three sources and each describes its
 * finding differently — a threshold with a direction, a reference range, or a
 * ready-made sentence. Three screens render breaches, and all three previously
 * assumed the threshold shape and called `.toFixed()` on a `threshold` that a
 * lab result does not have. That crashed both alert screens to a blank page.
 *
 * One implementation, so a fourth alert source is one edit and not three.
 */

/** What to call the thing that was measured. */
export function breachLabel(breach: BreachedParameter): string {
  // A lab result brings its own label; a vital is looked up; anything else
  // falls back to its own code — ugly, but never wrong and never blank.
  return breach.label ?? METRIC_LABELS[breach.metric as VitalMetric] ?? breach.metric
}

/** The value with its unit. */
export function breachValue(breach: BreachedParameter): string {
  return `${formatNumber(breach.value)}${breach.unit ?? ''}`
}

/**
 * What the value was judged against, phrased for the reader.
 *
 * `clinical` is the admin's wording; the family gets the same facts without the
 * word "threshold", which Phase 6 put on the banned list.
 */
export function breachContext(
  breach: BreachedParameter,
  register: 'clinical' | 'plain' = 'clinical',
): string {
  const unit = breach.unit ?? ''

  if (breach.threshold !== undefined && breach.direction) {
    return register === 'clinical'
      ? `${breach.direction} configured threshold ${formatNumber(breach.threshold)}${unit}`
      : `${breach.direction} the expected range of ${formatNumber(breach.threshold)}${unit}`
  }

  // A range stays a range. Flattening it to a single bound would throw away
  // half of what a reader needs to check the flag themselves.
  if (breach.ref_low != null && breach.ref_high != null) {
    return `expected ${formatNumber(breach.ref_low)}–${formatNumber(breach.ref_high)}${unit}`
  }
  if (breach.ref_high != null) return `expected up to ${formatNumber(breach.ref_high)}${unit}`
  if (breach.ref_low != null) return `expected at least ${formatNumber(breach.ref_low)}${unit}`

  if (breach.reason) return breach.reason

  return ''
}
