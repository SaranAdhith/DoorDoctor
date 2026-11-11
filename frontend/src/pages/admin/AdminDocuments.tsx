import { FileText } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { documentsApi } from '../../api/documents'
import { DocumentRow } from '../../components/documents'
import { Badge, Card, EmptyState, ErrorState, LoadingScreen, Tabs } from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import { markDocumentsSeen } from '../../hooks/useDocumentUpdates'
import type { DocumentStatus, MedicalDocument } from '../../types/intelligence'

/**
 * Every uploaded document, for admins (Phase 12).
 *
 * Opens on the review queue — documents that have been read and are waiting for
 * a person — oldest first, because the family who uploaded first has waited
 * longest. Each row says how many facts still need a decision; clicking it
 * opens the side-by-side review.
 */

type Filter = 'queue' | 'all' | DocumentStatus

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'queue', label: 'To review' },
  { value: 'all', label: 'All' },
  { value: 'verified', label: 'Verified' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'uploaded', label: 'Queued' },
  { value: 'failed', label: 'Failed' },
]

function load(filter: Filter): Promise<MedicalDocument[]> {
  if (filter === 'queue') return documentsApi.queue()
  return documentsApi.adminList(filter === 'all' ? undefined : filter)
}

export function AdminDocuments() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<Filter>('queue')
  const documents = useAsync<MedicalDocument[]>(() => load(filter), [filter])

  // Opening this page is reading the updates: the menu count clears.
  useEffect(() => {
    void markDocumentsSeen()
  }, [])

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-h1 font-semibold text-text-primary">Documents</h1>
        <p className="text-small text-text-secondary">
          Reports and prescriptions from families, nurses and the team. Nothing read from a document
          is part of the record until it is checked here.
        </p>
      </header>

      <Tabs label="Filter documents" items={FILTERS} value={filter} onChange={(value) => setFilter(value)} />

      <Card flush>
        {documents.loading && <LoadingScreen label="Loading documents" />}
        {documents.error && <ErrorState message={documents.error} onRetry={() => documents.reload()} />}
        {documents.data?.length === 0 && (
          <EmptyState
            icon={<FileText aria-hidden />}
            title={filter === 'queue' ? 'Nothing waiting for review' : 'Nothing here'}
            description={
              filter === 'queue'
                ? 'New uploads appear here once their pages have been read.'
                : 'No documents match this filter.'
            }
          />
        )}
        {documents.data && documents.data.length > 0 && (
          <ul className="divide-y divide-border-subtle px-5">
            {documents.data.map((document) => (
              <DocumentRow
                key={document.id}
                document={document}
                showCode
                onOpen={() => navigate(`/admin/documents/${document.id}`)}
                actions={
                  document.facts_pending ? (
                    <Badge tone="info">
                      {document.facts_pending} to decide
                    </Badge>
                  ) : null
                }
              />
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
