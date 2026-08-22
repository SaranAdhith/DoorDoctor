import type {
  Invoice,
  Plan,
  PlanAudience,
  ReferralSummary,
  RevenueSummary,
  Subscription,
} from '../types'
import { api, requestBlob } from './client'

export const plansApi = {
  list: (audience?: PlanAudience) =>
    api.get<Plan[]>(audience ? `/plans?audience=${audience}` : '/plans'),
}

export const subscriptionsApi = {
  mine: () => api.get<Subscription>('/subscriptions/me'),
  all: () => api.get<Subscription[]>('/subscriptions'),
  changePlan: (id: number, planCode: string, billingCycle?: string) =>
    api.post<Subscription>(`/subscriptions/${id}/change-plan`, {
      plan_code: planCode,
      billing_cycle: billingCycle ?? null,
    }),
  cancel: (id: number, reason?: string) =>
    api.post<Subscription>(`/subscriptions/${id}/cancel`, {
      immediate: false,
      reason: reason ?? null,
    }),
  resume: (id: number) => api.post<Subscription>(`/subscriptions/${id}/resume`),
}

export const invoicesApi = {
  list: () => api.get<Invoice[]>('/invoices'),
  get: (id: number) => api.get<Invoice>(`/invoices/${id}`),
  pdf: (id: number) => requestBlob(`/invoices/${id}/pdf`),
  pay: (id: number) => api.post<Invoice>(`/invoices/${id}/pay`),
}

export const referralsApi = {
  mine: () => api.get<ReferralSummary>('/referrals/me'),
  invite: (email: string) =>
    api.post<{ message: string; summary: ReferralSummary }>('/referrals/invite', { email }),
}

export const revenueApi = {
  summary: () => api.get<RevenueSummary>('/admin/revenue'),
}

/**
 * Opens an invoice PDF in a new tab.
 *
 * The blob URL is revoked on a delay rather than immediately — Safari has not
 * finished reading it when `open()` returns, and revoking straight away gives
 * the user a blank tab.
 */
export async function openInvoicePdf(id: number): Promise<void> {
  const blob = await invoicesApi.pdf(id)
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank', 'noopener')
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
}
