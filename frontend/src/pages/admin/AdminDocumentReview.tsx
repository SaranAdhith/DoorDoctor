import { ArrowLeft, FileText, Plus, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { documentObjectUrl, documentsApi, openDocumentFile } from '../../api/documents'
import { DOCUMENT_TYPE_LABELS, DocumentStatusBadge } from '../../components/documents'
import { FactForm, FactRow } from '../../components/documents/FactReview'
import { OcrText } from '../../components/documents/OcrText'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Input,
  LoadingScreen,
  Modal,
  Select,
  Textarea,
  useToast,
} from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import { formatDateTime } from '../../lib/format'
import type {
  DocumentType,
  FactAction,
  FactFields,
  MedicalDocumentDetail,
  PageMethod,
} from '../../types/intelligence'

/**
 * Reviewing one document (Phase 12, Stage 2).
 *
 * The page on the left, what software read from it on the right. Nothing on the
 * right is part of the patient's record until an admin confirms, corrects or
 * adds it, and the document can't be verified while any fact still waits for a
 * decision — the button says how many.
 */

const METHOD_LABELS: Record<PageMethod, string> = {
  text_layer: 'Text from the PDF (exact)',
  ocr: 'Read by OCR (check against the page)',
  none: 'Not readable — enter facts by hand',
}

function OriginalPreview({ document }: { document: MedicalDocumentDetail }) {
  const [url, setUrl] = useState<string | null>(null)
  const isImage = document.file?.content_type.startsWith('image/') ?? false

  useEffect(() => {
    let revoke: string | null = null
    if (document.file && isImage) {
      documentObjectUrl(document.file)
        .then((objectUrl) => {
          revoke = objectUrl
          setUrl(objectUrl)
        })
        .catch(() => setUrl(null))
    }
    return () => {
      if (revoke) URL.revokeObjectURL(revoke)
    }
  }, [document.file?.url, isImage])

  if (!document.file) return null
  if (isImage && url) {
    return (
      <img
        src={url}
        alt={`Uploaded page: ${document.title}`}
        className="max-h-[70vh] w-full rounded-md object-contain ring-1 ring-border-subtle"
      />
    )
  }
  return (
    <p className="text-small text-text-secondary">
      {isImage ? 'Loading the page…' : 'PDF documents open in a new tab.'}
    </p>
  )
}

export function AdminDocumentReview() {
  const { documentId } = useParams()
  const id = Number(documentId)
  const navigate = useNavigate()
  const { notify } = useToast()

  const doc = useAsync<MedicalDocumentDetail>(() => documentsApi.get(id), [id])
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [docType, setDocType] = useState<DocumentType | ''>('')
  const [docDate, setDocDate] = useState('')

  const document = doc.data
  useEffect(() => {
    if (document) {
      setDocType(document.doc_type)
      setDocDate(document.document_date ?? '')
    }
  }, [document?.id])

  async function guarded(action: () => Promise<unknown>, success?: string) {
    setBusy(true)
    try {
      await action()
      if (success) notify(success, 'success')
      await doc.reload({ quiet: true })
    } catch (error) {
      notify(error instanceof Error ? error.message : 'That did not work.', 'error')
    } finally {
      setBusy(false)
    }
  }

  async function decide(factId: number, action: FactAction, changes?: FactFields) {
    try {
      await documentsApi.decideFact(id, factId, action, changes)
      await doc.reload({ quiet: true })
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not save that decision.', 'error')
      throw error
    }
  }

  if (doc.loading) return <LoadingScreen label="Loading document" />
  if (doc.error || !document) return <ErrorState message={doc.error ?? 'Not found.'} onRetry={() => doc.reload()} />

  const reviewable = document.status === 'extracted' || document.status === 'needs_manual'
  const locked = !reviewable
  const pending = document.facts.filter((f) => f.status === 'proposed').length
  const ordered = [...document.facts].sort((a, b) => {
    // Waiting facts first, then by page, then in the order they were read.
    const wait = Number(b.status === 'proposed') - Number(a.status === 'proposed')
    return wait || (a.page_no ?? 0) - (b.page_no ?? 0) || a.id - b.id
  })

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <Link to="/admin/documents" className="inline-flex items-center gap-1 text-small text-text-secondary hover:underline">
          <ArrowLeft className="h-4 w-4" aria-hidden /> All documents
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="truncate text-h1 font-semibold text-text-primary">{document.title}</h1>
            <p className="text-small text-text-secondary">
              {DOCUMENT_TYPE_LABELS[document.doc_type]} · uploaded {formatDateTime(document.created_at)} by{' '}
              {document.uploaded_by_name ?? 'unknown'} ({document.uploader_role})
              {document.visit_id ? ` during visit #${document.visit_id}` : ''}
            </p>
          </div>
          <DocumentStatusBadge document={document} showCode />
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* The evidence */}
        <div className="space-y-4">
          <Card
            title="The page"
            action={
              document.file ? (
                <Button size="sm" variant="ghost" onClick={() => document.file && void openDocumentFile(document.file)}>
                  <FileText className="h-4 w-4" aria-hidden /> Open file
                </Button>
              ) : null
            }
          >
            <OriginalPreview document={document} />
          </Card>

          {(document.pages ?? []).map((page) => (
            <Card
              key={page.page_no}
              title={`What was read — page ${page.page_no}`}
              action={<Badge tone={page.method === 'none' ? 'neutral' : 'info'}>{METHOD_LABELS[page.method]}</Badge>}
            >
              {page.text ? <OcrText text={page.text} /> : <p className="text-small text-text-muted">No text on this page.</p>}
            </Card>
          ))}
        </div>

        {/* The decisions */}
        <div className="space-y-4">
          <Card
            title="Facts"
            description={
              locked
                ? 'This document has been decided. Its facts can no longer change.'
                : 'Nothing here is in the record until you confirm, correct or add it.'
            }
            action={
              reviewable ? (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={busy}
                  onClick={() => void guarded(() => documentsApi.extractAgain(id), 'Facts proposed again from the page text.')}
                >
                  <Sparkles className="h-4 w-4" aria-hidden /> Extract again
                </Button>
              ) : null
            }
          >
            {ordered.length === 0 && !adding && (
              <EmptyState
                title="No facts proposed"
                description={
                  reviewable
                    ? 'Nothing was found automatically. Add the facts from the page by hand, or verify the document with none if it holds nothing clinical.'
                    : 'No facts were added from this document.'
                }
              />
            )}
            <ul className="divide-y divide-border-subtle">
              {ordered.map((fact) => (
                <FactRow key={fact.id} fact={fact} locked={locked} onDecide={(action, changes) => decide(fact.id, action, changes)} />
              ))}
            </ul>

            {reviewable &&
              (adding ? (
                <div className="mt-3">
                  <FactForm
                    submitLabel="Add fact"
                    busy={busy}
                    onCancel={() => setAdding(false)}
                    onSubmit={(fields) =>
                      void guarded(async () => {
                        await documentsApi.addFact(id, fields)
                        setAdding(false)
                      })
                    }
                  />
                </div>
              ) : (
                <Button size="sm" variant="ghost" className="mt-3" onClick={() => setAdding(true)}>
                  <Plus className="h-4 w-4" aria-hidden /> Add a fact
                </Button>
              ))}
          </Card>

          {reviewable && (
            <Card title="Decide the document">
              <div className="grid gap-3 sm:grid-cols-2">
                <Select label="Document type" value={docType} onChange={(e) => setDocType(e.target.value as DocumentType)}>
                  {(Object.keys(DOCUMENT_TYPE_LABELS) as DocumentType[]).map((type) => (
                    <option key={type} value={type}>
                      {DOCUMENT_TYPE_LABELS[type]}
                    </option>
                  ))}
                </Select>
                <Input label="Date on the document" type="date" value={docDate} onChange={(e) => setDocDate(e.target.value)} />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  disabled={busy || pending > 0}
                  onClick={() =>
                    void guarded(
                      () =>
                        documentsApi.verify(id, {
                          doc_type: docType || undefined,
                          document_date: docDate || null,
                        }),
                      'Document verified. Its confirmed facts are now part of the record.',
                    )
                  }
                >
                  {pending > 0 ? `Verify (${pending} fact${pending === 1 ? '' : 's'} still to decide)` : 'Verify document'}
                </Button>
                <Button variant="danger" disabled={busy} onClick={() => setRejecting(true)}>
                  Reject document
                </Button>
              </div>
            </Card>
          )}
        </div>
      </div>

      <Modal open={rejecting} onClose={() => setRejecting(false)} title="Reject this document">
        <div className="space-y-3">
          <p className="text-small text-text-secondary">
            Nothing from it will be added to the record. The reason is kept in the audit log.
          </p>
          <Textarea
            label="Why?"
            rows={3}
            maxLength={255}
            value={reason}
            placeholder="e.g. Wrong patient, unreadable, not a medical document"
            onChange={(e) => setReason(e.target.value)}
          />
          <div className="flex gap-2">
            <Button
              variant="danger"
              disabled={busy || !reason.trim()}
              onClick={() =>
                void guarded(async () => {
                  await documentsApi.reject(id, reason.trim())
                  setRejecting(false)
                  navigate('/admin/documents')
                }, 'Document rejected.')
              }
            >
              Reject document
            </Button>
            <Button variant="ghost" onClick={() => setRejecting(false)}>
              Cancel
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
