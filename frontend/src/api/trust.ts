/**
 * The trust, operations and privacy API surface (§4.10-4.18).
 *
 * One module, the same reasoning as `api/clinical.ts`: these endpoints are read
 * together. The nurse's day needs the worklist and the shift; the privacy page
 * needs holdings, consents and the audit trail; the admin's morning needs the
 * board, the queue and the zones.
 *
 * **No operational constant appears downstream of this file.** The geofence
 * radius, the quiet-hours window, the break-even band and the retention period
 * all arrive from the server, exactly as prices and clinical ranges do. The
 * frontend renders numbers; it does not know them.
 */

import type {
  Attachment,
  AuditEntry,
  CareCircleMember,
  ConsentRecord,
  DeliveryRecord,
  ErasureRequest,
  MedicationChange,
  MedicationLog,
  NotificationPreferences,
  NurseAdminRecord,
  NurseDay,
  NurseProfile,
  NurseRoster,
  OnboardingProgress,
  Outcomes,
  PillOrganiserFill,
  PrivacyOverview,
  QueuedAlert,
  ShiftCheckIn,
  VisitBoard,
  VisitBrief,
  VisitStatus,
  ZoneView,
} from '../types'
import { api, getToken, request } from './client'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export const nursesApi = {
  /** The family-facing profile, reached through the patient on purpose. */
  forPatient: (patientId: number) =>
    api.get<NurseProfile[]>(`/patients/${patientId}/nurses`),
  one: (patientId: number, nurseId: number) =>
    api.get<NurseProfile>(`/patients/${patientId}/nurses/${nurseId}`),

  list: () => api.get<NurseAdminRecord[]>('/nurses'),
  get: (nurseId: number) => api.get<NurseAdminRecord>(`/nurses/${nurseId}`),
  update: (nurseId: number, body: Record<string, unknown>) =>
    api.patch<NurseAdminRecord>(`/nurses/${nurseId}`, body),
  verifyCredential: (credentialId: number, note?: string) =>
    api.post(`/nurse-credentials/${credentialId}/verify`, { note: note ?? null }),
  rejectCredential: (credentialId: number, note?: string) =>
    api.post(`/nurse-credentials/${credentialId}/reject`, { note: note ?? null }),
}

export const careCircleApi = {
  list: (patientId: number) => api.get<CareCircleMember[]>(`/patients/${patientId}/care-circle`),
  add: (patientId: number, body: Record<string, unknown>) =>
    api.post<CareCircleMember>(`/patients/${patientId}/care-circle`, body),
  update: (memberId: number, body: Record<string, unknown>) =>
    api.patch<CareCircleMember>(`/care-circle/${memberId}`, body),
  remove: (memberId: number) => request<void>(`/care-circle/${memberId}`, { method: 'DELETE' }),
}

export const medicationDepthApi = {
  history: (patientId: number) =>
    api.get<MedicationChange[]>(`/patients/${patientId}/medication-history`),
  change: (medicationId: number, body: Record<string, unknown>) =>
    api.patch<MedicationChange | null>(`/medications/${medicationId}`, body),
  organiser: (patientId: number) =>
    api.get<PillOrganiserFill[]>(`/patients/${patientId}/pill-organiser`),
  recordFill: (patientId: number, body: Record<string, unknown>) =>
    api.post<PillOrganiserFill>(`/patients/${patientId}/pill-organiser`, body),

  /**
   * Upload a dose photo.
   *
   * Not routed through `api.post`, which sets `Content-Type: application/json`
   * and would break the multipart boundary. The browser sets that header itself
   * for `FormData`, so it must be left alone here.
   */
  async uploadPhoto(logId: number, file: File): Promise<MedicationLog> {
    const form = new FormData()
    form.append('file', file)
    const token = getToken()
    const response = await fetch(`${BASE_URL}/medications/logs/${logId}/photo`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      throw new Error(
        payload && typeof payload.detail === 'string'
          ? payload.detail
          : 'Could not upload that photo.',
      )
    }
    return payload as MedicationLog
  },
}

/**
 * Fetch an uploaded file as an object URL.
 *
 * Uploads are never served statically, so an `<img src>` pointing at the API
 * would arrive without the bearer token and 401. The bytes are fetched, turned
 * into a blob and rendered from an object URL — the same shape `requestBlob`
 * uses for invoice PDFs.
 */
export async function attachmentObjectUrl(attachment: Attachment): Promise<string> {
  const token = getToken()
  const response = await fetch(`${BASE_URL}${attachment.url}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) throw new Error('Could not load that photo.')
  return URL.createObjectURL(await response.blob())
}

export const privacyApi = {
  overview: (patientId: number) => api.get<PrivacyOverview>(`/privacy/patients/${patientId}`),
  setConsent: (kind: string, granted: boolean, patientId: number) =>
    api.post<ConsentRecord>('/privacy/consents', { kind, granted, patient_id: patientId }),
  exportRecord: (patientId: number) =>
    api.get<Record<string, unknown>>(`/privacy/patients/${patientId}/export`),
  requestErasure: (patientId: number, reason: string | null) =>
    api.post<ErasureRequest>('/privacy/erasure-requests', {
      patient_id: patientId,
      reason,
    }),

  queue: (status?: string) =>
    api.get<ErasureRequest[]>(`/erasure-requests${status ? `?status=${status}` : ''}`),
  execute: (requestId: number, note: string | null) =>
    api.post<ErasureRequest>(`/erasure-requests/${requestId}/execute`, { note }),
  decline: (requestId: number, note: string) =>
    api.post<ErasureRequest>(`/erasure-requests/${requestId}/decline`, { note }),
  audit: (patientId?: number) =>
    api.get<AuditEntry[]>(`/audit${patientId ? `?patient_id=${patientId}` : ''}`),
}

export const notificationsApi = {
  preferences: () => api.get<NotificationPreferences>('/notifications/preferences'),
  savePreferences: (body: Record<string, unknown>) =>
    api.put<NotificationPreferences>('/notifications/preferences', body),
  deliveryLog: () => api.get<DeliveryRecord[]>('/notifications/delivery-log'),
}

export const nurseOpsApi = {
  myDay: () => api.get<NurseDay>('/nurse/my-day'),
  roster: (days = 7) => api.get<NurseRoster>(`/nurse/roster?days=${days}`),
  brief: (visitId: number) => api.get<VisitBrief>(`/visits/${visitId}/brief`),
  startShift: (body: Record<string, unknown>) =>
    api.post<ShiftCheckIn>('/nurse/shift/checkin', body),
  endShift: () => api.post<ShiftCheckIn>('/nurse/shift/checkout'),
}

export interface BoardFilters {
  from?: string
  to?: string
  status?: VisitStatus | ''
  nurseId?: number | null
  zone?: string
  unassigned?: boolean
  page?: number
  pageSize?: number
}

export const adminOpsApi = {
  board: (filters: BoardFilters = {}) => {
    const params = new URLSearchParams()
    if (filters.from) params.set('from', filters.from)
    if (filters.to) params.set('to', filters.to)
    if (filters.status) params.set('status', filters.status)
    if (filters.nurseId) params.set('nurse_id', String(filters.nurseId))
    if (filters.zone) params.set('zone', filters.zone)
    if (filters.unassigned) params.set('unassigned', 'true')
    params.set('page', String(filters.page ?? 1))
    params.set('page_size', String(filters.pageSize ?? 25))
    return api.get<VisitBoard>(`/admin/visit-board?${params.toString()}`)
  },
  alertQueue: (includeResolved = false) =>
    api.get<QueuedAlert[]>(`/admin/alert-queue?include_resolved=${includeResolved}`),
  outcomes: (days = 30) => api.get<Outcomes>(`/admin/outcomes?days=${days}`),
  zones: () => api.get<ZoneView>('/admin/zones'),
  shifts: () => api.get<ShiftCheckIn[]>('/admin/shifts'),
}

export const onboardingApi = {
  progress: (patientId: number) =>
    api.get<OnboardingProgress>(`/onboarding/patients/${patientId}`),
  acknowledge: (patientId: number, step: string) =>
    api.post<OnboardingProgress>(`/onboarding/patients/${patientId}/steps/${step}`),
}
