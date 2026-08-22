import { api } from './client'
import type { Lead, LeadStatus, LeadSummary } from '../types'

/**
 * The admin side of lead capture. Submission lives in `api/public.ts` because
 * that half needs no authentication and this half is admin-only.
 */
export const leadsApi = {
  list: (params: { status?: LeadStatus; kind?: string } = {}) => {
    const query = new URLSearchParams()
    if (params.status) query.set('status', params.status)
    if (params.kind) query.set('kind', params.kind)
    const suffix = query.toString()
    return api.get<Lead[]>(`/leads${suffix ? `?${suffix}` : ''}`)
  },

  summary: () => api.get<LeadSummary>('/leads/summary'),

  /** Both fields optional: a note can be added without moving the status. */
  update: (leadId: number, changes: { status?: LeadStatus; admin_note?: string }) =>
    api.patch<Lead>(`/leads/${leadId}`, changes),
}
