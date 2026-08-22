import type {
  ForgotPasswordResponse,
  LoginResponse,
  ResetPasswordResponse,
  ResetTokenStatus,
  User,
} from '../types'
import { api } from './client'

export const authApi = {
  login: (email: string, password: string) =>
    api.post<LoginResponse>('/auth/login', { email, password }, { skipAuthRedirect: true }),
  me: () => api.get<User>('/auth/me'),

  // The reset endpoints are reached by someone who is, by definition, signed
  // out — a 401 from them must not trigger the global session-expiry handler.
  forgotPassword: (email: string) =>
    api.post<ForgotPasswordResponse>('/auth/forgot-password', { email }, { skipAuthRedirect: true }),
  resetPassword: (token: string, password: string) =>
    api.post<ResetPasswordResponse>(
      '/auth/reset-password',
      { token, password },
      { skipAuthRedirect: true },
    ),
  checkResetToken: (token: string) =>
    api.get<ResetTokenStatus>(`/auth/reset-token/${encodeURIComponent(token)}/valid`),
}
