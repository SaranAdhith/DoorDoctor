/**
 * Phase 12 — the intelligence layers.
 *
 * Kept out of `types/index.ts` so the layers stay a separable surface on the
 * frontend too: nothing that predates Phase 12 imports from this file.
 */

export type DocumentStatus =
  | 'uploaded'
  | 'extracting'
  | 'extracted'
  | 'needs_manual'
  | 'verified'
  | 'rejected'
  | 'failed'

export type DocumentType =
  | 'lab_report'
  | 'prescription'
  | 'discharge_summary'
  | 'imaging_report'
  | 'other'
  | 'unknown'

export type PageMethod = 'text_layer' | 'ocr' | 'none'

export interface DocumentFile {
  /** Relative to the API base. Fetched with the bearer token, never linked to. */
  url: string
  content_type: string
  size_bytes: number
}

export interface MedicalDocument {
  id: number
  patient_id: number
  visit_id: number | null
  title: string
  doc_type: DocumentType
  document_date: string | null
  status: DocumentStatus
  /** Family-readable, written by the server. */
  status_label: string
  page_count: number | null
  uploader_role: 'family' | 'nurse' | 'admin'
  uploaded_by_name: string | null
  uploaded_by_me: boolean
  created_at: string
  extracted_at: string | null
  verified_at: string | null
  file: DocumentFile | null
  can_delete: boolean
  /** Admin only. */
  error?: string | null
  attempts?: number
  pages_needing_manual_entry?: number[]
}

export interface DocumentPageText {
  page_no: number
  method: PageMethod
  engine: string | null
  char_count: number
  elapsed_ms: number | null
  text: string
}

/** `pages` is present for admins only — unverified machine text goes nowhere else. */
export interface MedicalDocumentDetail extends MedicalDocument {
  pages?: DocumentPageText[]
}

export interface DocumentUploadOptions {
  title?: string
  docType?: DocumentType
}
