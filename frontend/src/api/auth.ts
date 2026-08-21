import type { LoginResponse, User } from '../types'
import { api } from './client'

export const authApi = {
  login: (email: string, password: string) =>
    api.post<LoginResponse>('/auth/login', { email, password }, { skipAuthRedirect: true }),
  me: () => api.get<User>('/auth/me'),
}
