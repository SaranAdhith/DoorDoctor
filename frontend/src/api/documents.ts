/**
 * Uploaded medical documents (Phase 12, Layer 1).
 *
 * Uploads are multipart and so bypass `api.post`, which sets a JSON
 * `Content-Type` and would break the boundary — the same reason as the dose
 * photo upload in `api/trust.ts`. The browser sets that header itself.
 */

import { ApiError, api, getToken, request } from './client'
import type {
  DocumentFile,
  DocumentStatus,
  DocumentUploadOptions,
  MedicalDocument,
  MedicalDocumentDetail,
} from '../types/intelligence'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

async function postMultipart<T>(path: string, form: FormData): Promise<T> {
  const token = getToken()
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the DoorDoctor API. Is the backend running?')
  }
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(
      response.status,
      payload && typeof payload.detail === 'string' ? payload.detail : 'Could not upload that document.',
    )
  }
  return payload as T
}

function uploadForm(file: File, options: DocumentUploadOptions): FormData {
  const form = new FormData()
  form.append('file', file)
  if (options.title?.trim()) form.append('title', options.title.trim())
  if (options.docType) form.append('doc_type', options.docType)
  return form
}

export const documentsApi = {
  list: (patientId: number) => api.get<MedicalDocument[]>(`/patients/${patientId}/documents`),
  get: (documentId: number) => api.get<MedicalDocumentDetail>(`/documents/${documentId}`),
  upload: (patientId: number, file: File, options: DocumentUploadOptions = {}) =>
    postMultipart<MedicalDocument>(`/patients/${patientId}/documents`, uploadForm(file, options)),
  uploadDuringVisit: (visitId: number, file: File, options: DocumentUploadOptions = {}) =>
    postMultipart<MedicalDocument>(`/visits/${visitId}/documents`, uploadForm(file, options)),
  remove: (documentId: number) => request<void>(`/documents/${documentId}`, { method: 'DELETE' }),
  reprocess: (documentId: number) => api.post<MedicalDocument>(`/documents/${documentId}/reprocess`),
  adminList: (status?: DocumentStatus) =>
    api.get<MedicalDocument[]>(`/admin/documents${status ? `?status=${status}` : ''}`),
}

/** Open the stored file in a new tab, fetched with the bearer token. */
export async function openDocumentFile(file: DocumentFile): Promise<void> {
  const token = getToken()
  // Opened synchronously so a popup blocker sees it as the user's click.
  const tab = window.open('', '_blank')
  try {
    const response = await fetch(`${BASE_URL}${file.url}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) throw new Error('Could not open that document.')
    const url = URL.createObjectURL(await response.blob())
    if (tab) tab.location.href = url
    else window.location.assign(url)
    // Long enough for the tab to load it; the blob is not needed afterwards.
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (error) {
    tab?.close()
    throw error
  }
}
