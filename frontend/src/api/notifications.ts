import type { Notification } from '../types'
import { api } from './client'

export const notificationsApi = {
  list: () => api.get<Notification[]>('/notifications'),
  markRead: (notificationId: number) => api.post<Notification>(`/notifications/${notificationId}/read`),
}
