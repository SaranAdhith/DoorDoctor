import type { Nurse, AdminSummary } from '../types'
import { api } from './client'

export const adminApi = {
  summary: () => api.get<AdminSummary>('/admin/summary'),
  nurses: () => api.get<Nurse[]>('/nurses'),
}
