import { api } from './client'
import type { PublicPlans, LeadSubmission } from '../types'

/**
 * The two endpoints the marketing site is allowed to call without a login.
 *
 * `client.ts` attaches a bearer token when one is stored, which is harmless
 * here — the server ignores it on both routes — and means a signed-in visitor
 * reading `/pricing` uses the same code path as a stranger.
 */
export const publicApi = {
  /** Prices come from the server so they cannot drift from `core/pricing.py`. */
  plans: (audience?: string) =>
    api.get<PublicPlans>(`/public/plans${audience ? `?audience=${audience}` : ''}`),

  /**
   * Submit an enquiry. Always resolves with the same message — a honeypot hit
   * and a real submission are indistinguishable from out here, on purpose.
   */
  submitLead: (payload: LeadSubmission) => api.post<{ message: string }>('/leads', payload),
}
