import type { Alert, AlertDetail } from '../types'
import { api } from './client'

export const alertsApi = {
  list: (status?: string) => api.get<Alert[]>(`/alerts${status ? `?status=${status}` : ''}`),
  get: (alertId: number) => api.get<AlertDetail>(`/alerts/${alertId}`),
  acknowledge: (alertId: number) => api.post<Alert>(`/alerts/${alertId}/acknowledge`),
  /** §8 journey 3: the admin resolves it *with a note*. */
  resolve: (alertId: number, note?: string | null) =>
    api.post<Alert>(`/alerts/${alertId}/resolve`, { note: note ?? null }),
}
