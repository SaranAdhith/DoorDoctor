import { FileText, Upload } from 'lucide-react'
import { useRef, useState, type ReactNode } from 'react'

import { openDocumentFile } from '../../api/documents'
import { formatDateTime } from '../../lib/format'
import type {
  DocumentStatus,
  DocumentType,
  DocumentUploadOptions,
  MedicalDocument,
} from '../../types/intelligence'
import { Badge, Button, Input, Select, useToast, type BadgeTone } from '../ui'

/**
 * Phase 12 — shared pieces for uploaded documents.
 *
 * Status wording comes from the server (`status_label`), so the family, nurse
 * and admin screens never disagree about what "waiting" means.
 */

export const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  lab_report: 'Lab report',
  prescription: 'Prescription',
  discharge_summary: 'Discharge summary',
  imaging_report: 'Scan or X-ray report',
  other: 'Other',
  unknown: 'Not specified',
}

/** `neutral | info` only: a document's progress is chrome, not a clinical reading. */
const STATUS_TONES: Record<DocumentStatus, BadgeTone> = {
  uploaded: 'neutral',
  extracting: 'info',
  extracted: 'info',
  needs_manual: 'info',
  verified: 'neutral',
  rejected: 'neutral',
  failed: 'neutral',
}

export function DocumentStatusBadge({
  document,
  showCode = false,
}: {
  document: MedicalDocument
  /** Staff screens show the pipeline state as well as the plain label. */
  showCode?: boolean
}) {
  return (
    <Badge tone={STATUS_TONES[document.status]}>
      {showCode ? `${document.status_label} · ${document.status.replace('_', ' ')}` : document.status_label}
    </Badge>
  )
}

export function DocumentUploadForm({
  onUpload,
  allowedTypes,
  capture = false,
  disabled = false,
}: {
  onUpload: (file: File, options: DocumentUploadOptions) => Promise<void>
  allowedTypes?: DocumentType[]
  /** On a phone, open the camera directly — used during a nurse's visit. */
  capture?: boolean
  disabled?: boolean
}) {
  const { notify } = useToast()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [docType, setDocType] = useState<DocumentType>('unknown')
  const [busy, setBusy] = useState(false)

  const types = allowedTypes ?? (Object.keys(DOCUMENT_TYPE_LABELS) as DocumentType[])

  async function submit() {
    if (!file) return
    setBusy(true)
    try {
      await onUpload(file, { title, docType })
      setFile(null)
      setTitle('')
      setDocType('unknown')
      if (inputRef.current) inputRef.current.value = ''
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not upload that document.', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,image/jpeg,image/png,image/webp"
          {...(capture ? { capture: 'environment' as const } : {})}
          className="sr-only"
          id="document-file"
          disabled={disabled || busy}
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <Button
          variant="ghost"
          onClick={() => inputRef.current?.click()}
          disabled={disabled || busy}
        >
          <Upload className="h-4 w-4" aria-hidden />
          {file ? 'Choose a different file' : capture ? 'Take a photo or choose a file' : 'Choose a PDF or photo'}
        </Button>
        {file && (
          <span className="min-w-0 truncate text-small text-text-secondary" title={file.name}>
            {file.name}
          </span>
        )}
      </div>

      {file && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Select
            label="What is it?"
            value={docType}
            onChange={(event) => setDocType(event.target.value as DocumentType)}
          >
            {types.map((type) => (
              <option key={type} value={type}>
                {DOCUMENT_TYPE_LABELS[type]}
              </option>
            ))}
          </Select>
          <Input
            label="Name (optional)"
            value={title}
            maxLength={120}
            placeholder={file.name}
            onChange={(event) => setTitle(event.target.value)}
          />
        </div>
      )}

      {file && (
        <Button onClick={() => void submit()} disabled={busy || disabled}>
          {busy ? 'Uploading…' : 'Upload'}
        </Button>
      )}
      <p className="text-caption text-text-muted">
        PDF or a photo (JPEG, PNG or WEBP), up to 15 MB. Photos are stored without their location
        data.
      </p>
    </div>
  )
}

export function DocumentRow({
  document,
  showCode = false,
  actions,
  onOpen,
}: {
  document: MedicalDocument
  showCode?: boolean
  actions?: ReactNode
  /** Staff screens open a detail view; others open the file itself. */
  onOpen?: () => void
}) {
  const { notify } = useToast()

  async function openFile() {
    if (!document.file) return
    try {
      await openDocumentFile(document.file)
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not open that document.', 'error')
    }
  }

  return (
    <li className="flex flex-wrap items-start justify-between gap-3 py-3">
      <div className="flex min-w-0 items-start gap-3">
        <FileText className="mt-0.5 h-5 w-5 shrink-0 text-text-muted" aria-hidden />
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => (onOpen ? onOpen() : void openFile())}
            className="block max-w-full truncate text-left text-body font-medium text-text-primary hover:underline"
          >
            {document.title}
          </button>
          <p className="text-caption text-text-secondary">
            {DOCUMENT_TYPE_LABELS[document.doc_type]} · {formatDateTime(document.created_at)}
            {document.uploaded_by_name ? ` · added by ${document.uploaded_by_me ? 'you' : document.uploaded_by_name}` : ''}
            {document.page_count ? ` · ${document.page_count} page${document.page_count > 1 ? 's' : ''}` : ''}
          </p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <DocumentStatusBadge document={document} showCode={showCode} />
        {actions}
      </div>
    </li>
  )
}
