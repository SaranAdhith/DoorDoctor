/**
 * The clinical API surface (§4.2-4.9).
 *
 * One module rather than seven, because these endpoints are consumed together —
 * the family Care page reads the safety score, the care team and the screening
 * status in one render, and the admin escalation queue reads escalations,
 * hospital bookings and tasks. Splitting them would mean seven imports on every
 * clinical screen and no separation worth having.
 *
 * **No clinical constant appears in this file or anywhere downstream of it.**
 * Reference ranges, safety weights, SLA budgets, the PHQ-2 wording and the
 * emergency ladder all arrive from the server. That is the same rule Phase 8
 * applied to prices: the frontend renders the numbers, it does not know them.
 */

import type {
  CareInteraction,
  CareManager,
  CareTeam,
  Consult,
  ConsultAllowance,
  Device,
  DeviceReading,
  EmergencyBlock,
  Escalation,
  FollowUpTask,
  HospitalBooking,
  HospitalBookingStatus,
  LabOrder,
  LabPanel,
  RegisteredDevice,
  SafetyHistoryPoint,
  SafetyScore,
  Screening,
  ScreeningInstrument,
  ScreeningStatus,
  TaskSummary,
} from '../types'
import { api } from './client'

export const safetyApi = {
  get: (patientId: number) => api.get<SafetyScore>(`/patients/${patientId}/safety-score`),
  history: (patientId: number) =>
    api.get<SafetyHistoryPoint[]>(`/patients/${patientId}/safety-score/history`),
  recalculate: (patientId: number) =>
    api.post<SafetyScore>(`/patients/${patientId}/safety-score/recalculate`),
}

export const labsApi = {
  panels: () => api.get<LabPanel[]>('/lab-panels'),
  list: (patientId: number) => api.get<LabOrder[]>(`/patients/${patientId}/lab-orders`),
  order: (patientId: number, panelCode: string, notes?: string) =>
    api.post<LabOrder>(`/patients/${patientId}/lab-orders`, {
      panel_code: panelCode,
      notes: notes ?? null,
    }),
  awaitingResults: () => api.get<LabOrder[]>('/lab-orders/awaiting-results'),
  collect: (orderId: number) => api.post<LabOrder>(`/lab-orders/${orderId}/collect`),
  recordResults: (orderId: number, values: Record<string, number>) =>
    api.post<LabOrder>(`/lab-orders/${orderId}/results`, { values }),
  cancel: (orderId: number) => api.post<LabOrder>(`/lab-orders/${orderId}/cancel`),
}

export const consultsApi = {
  allowance: (patientId: number) =>
    api.get<ConsultAllowance>(`/patients/${patientId}/consults/allowance`),
  list: (patientId: number) => api.get<Consult[]>(`/patients/${patientId}/consults`),
  book: (patientId: number, scheduledFor: string, reason: string) =>
    api.post<Consult>(`/patients/${patientId}/consults`, {
      scheduled_for: scheduledFor,
      reason,
    }),
  cancel: (consultId: number, reason?: string) =>
    api.post<Consult>(`/consults/${consultId}/cancel`, { reason: reason ?? null }),
  upcoming: () => api.get<Consult[]>('/consults/upcoming'),
  complete: (consultId: number, summary?: string) =>
    api.post<Consult>(`/consults/${consultId}/complete`, { summary: summary ?? null }),
}

export const careApi = {
  managers: () => api.get<CareManager[]>('/care-managers'),
  team: (patientId: number) => api.get<CareTeam>(`/patients/${patientId}/care-team`),
  /** Omit the manager to let the server pick the least-loaded one of the kind
   *  the patient's plan grants. */
  assign: (patientId: number, careManagerId?: number) =>
    api.post<CareTeam['assignment']>(`/patients/${patientId}/care-team`, {
      care_manager_id: careManagerId ?? null,
    }),
  logInteraction: (
    patientId: number,
    body: { channel: string; subject: string; note?: string; minutes?: number | null },
  ) => api.post<CareInteraction>(`/patients/${patientId}/care-interactions`, body),
}

export const screeningsApi = {
  instrument: () => api.get<ScreeningInstrument>('/screenings/instruments/phq2'),
  list: (patientId: number) => api.get<Screening[]>(`/patients/${patientId}/screenings`),
  status: (patientId: number) =>
    api.get<ScreeningStatus>(`/patients/${patientId}/screenings/status`),
  record: (patientId: number, answers: number[], visitId?: number | null) =>
    api.post<Screening>(`/patients/${patientId}/screenings`, {
      answers,
      visit_id: visitId ?? null,
    }),
}

export const devicesApi = {
  list: (patientId: number) => api.get<Device[]>(`/patients/${patientId}/devices`),
  readings: (patientId: number) =>
    api.get<DeviceReading[]>(`/patients/${patientId}/device-readings`),
  /** The response carries the plaintext key once; it cannot be read back. */
  register: (patientId: number, body: { kind: string; label: string; serial: string }) =>
    api.post<RegisteredDevice>(`/patients/${patientId}/devices`, body),
  rotateKey: (deviceId: number) => api.post<RegisteredDevice>(`/devices/${deviceId}/rotate-key`),
  deactivate: (deviceId: number) => api.post<Device>(`/devices/${deviceId}/deactivate`),
}

export const escalationsApi = {
  emergency: () => api.get<EmergencyBlock>('/emergency'),
  list: (status?: string) =>
    api.get<Escalation[]>(`/escalations${status ? `?status=${status}` : ''}`),
  forPatient: (patientId: number) => api.get<Escalation[]>(`/patients/${patientId}/escalations`),
  get: (eventId: number) => api.get<Escalation>(`/escalations/${eventId}`),
  acknowledge: (eventId: number) => api.post<Escalation>(`/escalations/${eventId}/acknowledge`),
  resolve: (eventId: number, note?: string) =>
    api.post<Escalation>(`/escalations/${eventId}/resolve`, { note: note ?? null }),
  addStep: (eventId: number, body: { channel: string; target: string; detail: string }) =>
    api.post<Escalation>(`/escalations/${eventId}/steps`, body),
}

export const hospitalApi = {
  queue: (status?: string) =>
    api.get<HospitalBooking[]>(`/hospital-bookings${status ? `?status=${status}` : ''}`),
  forPatient: (patientId: number) =>
    api.get<HospitalBooking[]>(`/patients/${patientId}/hospital-bookings`),
  request: (
    patientId: number,
    body: {
      hospital_name: string
      reason: string
      department?: string | null
      ambulance_required?: boolean
    },
  ) => api.post<HospitalBooking>(`/patients/${patientId}/hospital-bookings`, body),
  update: (
    bookingId: number,
    body: { status?: HospitalBookingStatus; confirmation_detail?: string; notes?: string },
  ) => api.patch<HospitalBooking>(`/hospital-bookings/${bookingId}`, body),
}

export const tasksApi = {
  list: (status?: string) => api.get<FollowUpTask[]>(`/tasks${status ? `?status=${status}` : ''}`),
  summary: () => api.get<TaskSummary>('/tasks/summary'),
  complete: (taskId: number, note?: string) =>
    api.post<FollowUpTask>(`/tasks/${taskId}/complete`, { note: note ?? null }),
}
