import { FileText } from 'lucide-react'
import { useState } from 'react'

import { documentsApi, openDocumentFile } from '../../api/documents'
import { DOCUMENT_TYPE_LABELS, DocumentRow, DocumentStatusBadge } from '../../components/documents'
import {
  Badge,
  Button,
  Card,
  Drawer,
  EmptyState,
  ErrorState,
  LoadingScreen,
  Tabs,
  useToast,
} from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import { formatDateTime } from '../../lib/format'
import type {
  DocumentStatus,
  MedicalDocument,
  MedicalDocumentDetail,
  PageMethod,
} from '../../types/intelligence'

/**
 * Every uploaded document, for admins (Phase 12, Layer 1).
 *
 * Stage 1 shows what was read and how: each page says whether its text came
 * from the PDF itself (exact), from OCR (an engine's reading), or from nothing
 * (needs entering by hand). Stage 2 turns this into the verification screen.
 */

type Filter = 'all' | DocumentStatus

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'needs_manual', label: 'Needs manual entry' },
  { value: 'extracted', label: 'Read' },
  { value: 'uploaded', label: 'Queued' },
  { value: 'failed', label: 'Failed' },
]

const METHOD_LABELS: Record<PageMethod, string> = {
  text_layer: 'Text from the PDF (exact)',
  ocr: 'Read by OCR (check against the page)',
  none: 'Not readable — enter by hand',
}

export function AdminDocuments() {
  const { notify } = useToast()
  const [filter, setFilter] = useState<Filter>('all')
  const [openId, setOpenId] = useState<number | null>(null)

  const documents = useAsync<MedicalDocument[]>(
    () => documentsApi.adminList(filter === 'all' ? undefined : filter),
    [filter],
  )
  const detail = useAsync<MedicalDocumentDetail | null>(
    async () => (openId ? documentsApi.get(openId) : null),
    [openId],
  )

  async function reprocess(id: number) {
    try {
      await documentsApi.reprocess(id)
      notify('Queued to be read again.', 'success')
      await Promise.all([documents.reload({ quiet: true }), detail.reload({ quiet: true })])
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not queue that document.', 'error')
    }
  }

  async function remove(document: MedicalDocument) {
    if (!window.confirm(`Remove "${document.title}" and its file? This cannot be undone.`)) return
    try {
      await documentsApi.remove(document.id)
      notify('Document removed.', 'success')
      setOpenId(null)
      await documents.reload({ quiet: true })
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not remove that document.', 'error')
    }
  }

  async function openFile(document: MedicalDocument) {
    if (!document.file) return
    try {
      await openDocumentFile(document.file)
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not open that document.', 'error')
    }
  }

  const current = detail.data

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-h1 font-semibold text-text-primary">Documents</h1>
        <p className="text-small text-text-secondary">
          Everything families, nurses and the team have uploaded, and how each page was read.
        </p>
      </header>

      <Tabs
        label="Filter documents"
        items={FILTERS}
        value={filter}
        onChange={(value) => setFilter(value)}
      />

      <Card flush>
        {documents.loading && <LoadingScreen label="Loading documents" />}
        {documents.error && <ErrorState message={documents.error} onRetry={() => documents.reload()} />}
        {documents.data?.length === 0 && (
          <EmptyState icon={<FileText aria-hidden />} title="Nothing here" description="No documents match this filter." />
        )}
        {documents.data && documents.data.length > 0 && (
          <ul className="divide-y divide-border-subtle px-5">
            {documents.data.map((document) => (
              <DocumentRow
                key={document.id}
                document={document}
                showCode
                onOpen={() => setOpenId(document.id)}
              />
            ))}
          </ul>
        )}
      </Card>

      <Drawer
        open={openId !== null}
        onClose={() => setOpenId(null)}
        title={current?.title ?? 'Document'}
        footer={
          current ? (
            <div className="flex flex-wrap gap-2">
              <Button variant="ghost" onClick={() => void openFile(current)}>
                Open file
              </Button>
              {current.status !== 'verified' && current.status !== 'extracting' && (
                <Button variant="ghost" onClick={() => void reprocess(current.id)}>
                  Read again
                </Button>
              )}
              <Button variant="danger" onClick={() => void remove(current)}>
                Remove
              </Button>
            </div>
          ) : null
        }
      >
        {detail.loading && <LoadingScreen label="Loading document" />}
        {detail.error && <ErrorState message={detail.error} onRetry={() => detail.reload()} />}
        {current && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <DocumentStatusBadge document={current} showCode />
              <Badge>{DOCUMENT_TYPE_LABELS[current.doc_type]}</Badge>
            </div>
            <dl className="grid grid-cols-2 gap-2 text-small">
              <dt className="text-text-muted">Uploaded</dt>
              <dd className="text-text-primary">{formatDateTime(current.created_at)}</dd>
              <dt className="text-text-muted">By</dt>
              <dd className="text-text-primary">
                {current.uploaded_by_name ?? '—'} ({current.uploader_role})
                {current.visit_id ? ` · visit #${current.visit_id}` : ''}
              </dd>
              <dt className="text-text-muted">Attempts</dt>
              <dd className="tnum text-text-primary">{current.attempts ?? 0}</dd>
            </dl>
            {current.error && <p className="text-small text-status-attention">{current.error}</p>}

            {(current.pages ?? []).length === 0 && (
              <p className="text-small text-text-muted">Not read yet.</p>
            )}
            {(current.pages ?? []).map((page) => (
              <section key={page.page_no} className="rounded-md border border-border-subtle p-3">
                <header className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-small font-semibold text-text-primary">Page {page.page_no}</h3>
                  <Badge tone={page.method === 'none' ? 'neutral' : 'info'}>{METHOD_LABELS[page.method]}</Badge>
                </header>
                {page.text ? (
                  <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words text-caption text-text-secondary">
                    {page.text}
                  </pre>
                ) : (
                  <p className="text-caption text-text-muted">No text on this page.</p>
                )}
                {page.engine && (
                  <p className="mt-2 text-caption text-text-muted">
                    {page.engine}
                    {page.elapsed_ms ? ` · ${(page.elapsed_ms / 1000).toFixed(1)} s` : ''}
                  </p>
                )}
              </section>
            ))}
          </div>
        )}
      </Drawer>
    </div>
  )
}
