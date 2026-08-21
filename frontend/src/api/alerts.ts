import type { Alert, AlertDetail } from '../types'
import { api } from './client'

export const alertsApi = {
  list: (status?: string) => api.get<Alert[]>(`/alerts${status ? `?status=${status}` : ''}`),
  get: (alertId: number) => api.get<AlertDetail>(`/alerts/${alertId}`),
  acknowledge: (alertId: number) => api.post<Alert>(`/alerts/${alertId}/acknowledge`),
  resolve: (alertId: number) => api.post<Alert>(`/alerts/${alertId}/resolve`),
}
