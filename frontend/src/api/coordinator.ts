import type { Caregiver, CoordinatorSummary } from '../types'
import { api } from './client'

export const coordinatorApi = {
  summary: () => api.get<CoordinatorSummary>('/coordinator/summary'),
  caregivers: () => api.get<Caregiver[]>('/caregivers'),
}
