import type { Adherence, Dashboard, Medication, Patient, Threshold } from '../types'
import { api } from './client'

export const patientsApi = {
  list: () => api.get<Patient[]>('/patients'),
  get: (patientId: number) => api.get<Patient>(`/patients/${patientId}`),
  dashboard: (patientId: number) => api.get<Dashboard>(`/patients/${patientId}/dashboard`),
  medications: (patientId: number) => api.get<Medication[]>(`/patients/${patientId}/medications`),
  createMedication: (
    patientId: number,
    payload: { name: string; dosage: string; frequency: string; scheduled_time: string },
  ) => api.post<Medication>(`/patients/${patientId}/medications`, payload),
  adherence: (patientId: number) => api.get<Adherence>(`/patients/${patientId}/medication-adherence`),
  thresholds: (patientId: number) => api.get<Threshold[]>(`/patients/${patientId}/thresholds`),
  updateThresholds: (patientId: number, payload: Threshold[]) =>
    api.put<Threshold[]>(`/patients/${patientId}/thresholds`, payload),
}
