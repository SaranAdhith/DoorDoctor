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
  /** Facts a person put in the record; 0 until the document is verified. */
  facts_in_record: number
  /** Admin only. */
  error?: string | null
  attempts?: number
  pages_needing_manual_entry?: number[]
  facts_total?: number
  facts_pending?: number
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
  /** Admins: every fact. Others: decided facts of a verified document only. */
  facts: ExtractedFact[]
}

export interface DocumentUploadOptions {
  title?: string
  docType?: DocumentType
}

// --- Stage 2: facts and verification -----------------------------------------

export type FactKind =
  | 'lab_value'
  | 'vital_sign'
  | 'medication'
  | 'diagnosis'
  | 'allergy'
  | 'instruction'
  | 'other'

export type FactStatus = 'proposed' | 'confirmed' | 'edited' | 'rejected' | 'added'

export type FactSource = 'table' | 'llm' | 'manual'

export interface ExtractedFact {
  id: number
  page_no: number | null
  kind: FactKind
  label: string
  value_text: string
  value_num: number | null
  unit: string
  ref_low: number | null
  ref_high: number | null
  /** `null` when there's no number or no range to compare it with. */
  out_of_range: boolean | null
  observed_on: string | null
  status: FactStatus
  /** Admin only. */
  source?: FactSource
  source_quote?: string
  original?: Partial<Record<'kind' | 'label' | 'value_text' | 'unit', string>> & {
    value_num?: number | null
    ref_low?: number | null
    ref_high?: number | null
  } | null
  reviewed_at?: string | null
}

export interface FactFields {
  kind?: FactKind
  label?: string
  value_text?: string
  value_num?: number | null
  unit?: string
  ref_low?: number | null
  ref_high?: number | null
  observed_on?: string | null
  page_no?: number | null
}

export type FactAction = 'confirm' | 'edit' | 'reject' | 'reopen'
