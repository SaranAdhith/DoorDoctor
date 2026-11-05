import { documentsApi } from '../../api/documents'
import { useAsync } from '../../hooks/useAsync'
import type { DocumentUploadOptions, MedicalDocument } from '../../types/intelligence'
import { Card, ErrorState, useToast } from '../ui'
import { DocumentRow, DocumentUploadForm } from './index'

/**
 * Documents added during a visit (Phase 12) — one self-contained card.
 *
 * It fetches on its own rather than through the visit screen's data, so if the
 * documents API is switched off or failing, this card shows its own error and
 * the rest of the visit screen is exactly as it was before Phase 12.
 *
 * The server enforces the nurse rule (their visit, in progress, check-in not
 * out of range). The disabled state here is a courtesy, not the control.
 */
export function VisitDocumentsCard({
  visitId,
  patientId,
  inProgress,
}: {
  visitId: number
  patientId: number
  inProgress: boolean
}) {
  const { notify } = useToast()
  const documents = useAsync<MedicalDocument[]>(() => documentsApi.list(patientId), [patientId])
  const fromThisVisit = (documents.data ?? []).filter((d) => d.visit_id === visitId)

  async function upload(file: File, options: DocumentUploadOptions) {
    await documentsApi.uploadDuringVisit(visitId, file, options)
    notify('Document added to this visit. The care team will check it.', 'success')
    await documents.reload({ quiet: true })
  }

  return (
    <Card
      title="Documents"
      description="Photograph a prescription or report the family has at home."
    >
      {documents.error ? (
        <ErrorState message={documents.error} onRetry={() => documents.reload()} />
      ) : (
        <>
          <DocumentUploadForm
            onUpload={upload}
            capture
            disabled={!inProgress}
            allowedTypes={['prescription', 'lab_report', 'discharge_summary', 'imaging_report', 'other']}
          />
          {!inProgress && (
            <p className="mt-2 text-caption text-text-muted">
              Documents can be added once you have checked in.
            </p>
          )}
          {fromThisVisit.length > 0 && (
            <ul className="mt-4 divide-y divide-border-subtle">
              {fromThisVisit.map((document) => (
                <DocumentRow key={document.id} document={document} showCode />
              ))}
            </ul>
          )}
        </>
      )}
    </Card>
  )
}
