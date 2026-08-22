/**
 * Small authenticated API client.
 *
 * Everything that talks to the backend goes through here so token handling and
 * error shaping live in exactly one place.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
const TOKEN_KEY = 'doordoctor.token'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

/** Subscribers are notified when the API rejects the stored token. */
const unauthorizedHandlers = new Set<() => void>()

export function onUnauthorized(handler: () => void): () => void {
  unauthorizedHandlers.add(handler)
  return () => unauthorizedHandlers.delete(handler)
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  /** Skip the global 401 handler (used by the login screen). */
  skipAuthRedirect?: boolean
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, skipAuthRedirect = false } = options
  const token = getToken()

  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the DoorDoctor API. Is the backend running?')
  }

  if (response.status === 401 && !skipAuthRedirect) {
    clearToken()
    unauthorizedHandlers.forEach((handler) => handler())
  }

  if (response.status === 204) return undefined as T

  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    const detail =
      payload && typeof payload.detail === 'string'
        ? payload.detail
        : `Request failed (${response.status}).`
    throw new ApiError(response.status, detail)
  }

  return payload as T
}

/**
 * Fetch a binary response (an invoice PDF) with the bearer token attached.
 *
 * A plain `<a href>` to the endpoint would arrive unauthenticated and 401, so
 * the file is fetched, turned into a blob and opened from an object URL.
 */
export async function requestBlob(path: string): Promise<Blob> {
  const token = getToken()
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, { headers })
  } catch {
    throw new ApiError(0, 'Cannot reach the DoorDoctor API. Is the backend running?')
  }

  if (response.status === 401) {
    clearToken()
    unauthorizedHandlers.forEach((handler) => handler())
  }

  if (!response.ok) {
    // The error body is JSON even though the success body is not.
    const payload = await response.json().catch(() => null)
    const detail =
      payload && typeof payload.detail === 'string'
        ? payload.detail
        : `Request failed (${response.status}).`
    throw new ApiError(response.status, detail)
  }

  return response.blob()
}

export const api = {
  get: <T,>(path: string, options: RequestOptions = {}) => request<T>(path, options),
  post: <T,>(path: string, body?: unknown, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: 'POST', body }),
  put: <T,>(path: string, body?: unknown) => request<T>(path, { method: 'PUT', body }),
}
