import type {
  MedicationLog,
  MedicationLogStatus,
  Visit,
  VisitDetail,
  VitalsRecordResult,
  VitalsSubmission,
} from '../types'
import { api } from './client'

export const visitsApi = {
  list: (status?: string) => api.get<Visit[]>(`/visits${status ? `?status=${status}` : ''}`),
  today: () => api.get<Visit[]>('/visits/today'),
  get: (visitId: number) => api.get<VisitDetail>(`/visits/${visitId}`),
  create: (payload: { patient_id: number; nurse_id?: number | null; scheduled_at: string }) =>
    api.post<Visit>('/visits', payload),
  assign: (visitId: number, nurseId: number) =>
    api.post<Visit>(`/visits/${visitId}/assign`, { nurse_id: nurseId }),
  checkIn: (visitId: number, location?: { lat: number; lng: number }) =>
    api.post<Visit>(`/visits/${visitId}/checkin`, location ?? {}),
  checkOut: (visitId: number) => api.post<Visit>(`/visits/${visitId}/checkout`),
  saveNotes: (visitId: number, notes: string) => api.post<Visit>(`/visits/${visitId}/notes`, { notes }),
  recordVitals: (visitId: number, payload: VitalsSubmission) =>
    api.post<VitalsRecordResult>(`/visits/${visitId}/vitals`, payload),
  logMedication: (
    visitId: number,
    payload: { medication_id: number; status: MedicationLogStatus; reason?: string | null },
  ) => api.post<MedicationLog>(`/visits/${visitId}/medication-logs`, payload),
  complete: (visitId: number) => api.post<Visit>(`/visits/${visitId}/complete`),
}
