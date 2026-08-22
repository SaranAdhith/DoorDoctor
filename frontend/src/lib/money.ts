/**
 * Money formatting.
 *
 * Every amount crossing the API is an integer count of **paise**, so `350000`
 * is ₹3,500. Nothing in the client divides by 100 by hand — it goes through
 * here, and the unit is in the field name (`*_paise`) on the way in.
 *
 * This mirrors `format_inr` in `backend/app/services/billing_service.py`, which
 * exists separately because invoice PDFs are rendered server-side and cannot ask
 * the browser to format anything. Both are asserted against the same cases, so
 * the two cannot drift apart unnoticed.
 */

/** `en-IN` groups by lakh — ₹1,23,456 — which is what an Indian invoice shows. */
const INR = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })

export function formatINR(paise: number): string {
  const sign = paise < 0 ? '-' : ''
  return `${sign}₹${INR.format(Math.abs(paise) / 100)}`
}

const LAKH = 100_00_000 // ₹1,00,000 in paise
const CRORE = 100_00_00_000 // ₹1,00,00,000 in paise

/**
 * Shortened for dashboard tiles, where the exact rupee is noise: ₹21.1L, ₹1.2Cr.
 * Never use this on an invoice — a bill has to state the amount it is for.
 */
export function formatINRCompact(paise: number): string {
  const magnitude = Math.abs(paise)
  const sign = paise < 0 ? '-' : ''
  if (magnitude >= CRORE) return `${sign}₹${trim(magnitude / CRORE)}Cr`
  if (magnitude >= LAKH) return `${sign}₹${trim(magnitude / LAKH)}L`
  return formatINR(paise)
}

function trim(value: number): string {
  return value.toFixed(1).replace(/\.0$/, '')
}

/** Paise as a plain rupee number, for arithmetic the UI has to do itself. */
export function toRupees(paise: number): number {
  return paise / 100
}

const CYCLE_SUFFIX: Record<string, string> = { monthly: '/month', annual: '/year' }

/** `₹3,500/month`. The suffix says what the price buys. */
export function formatPrice(paise: number, cycle: string): string {
  return `${formatINR(paise)}${CYCLE_SUFFIX[cycle] ?? ''}`
}
