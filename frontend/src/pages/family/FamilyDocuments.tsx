import { FileText } from 'lucide-react'
import { useEffect } from 'react'

import { documentsApi } from '../../api/documents'
import { patientsApi } from '../../api/patients'
import { DocumentRow, DocumentUploadForm } from '../../components/documents'
import { Button, Card, EmptyState, ErrorState, LoadingScreen, useToast } from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import { markDocumentsSeen } from '../../hooks/useDocumentUpdates'
import type { Patient } from '../../types'
import type { DocumentUploadOptions, MedicalDocument } from '../../types/intelligence'

/**
 * Medical documents, for the family (Phase 12, Layer 1).
 *
 * A family hands over what the hospital gave them — a lab report, a discharge
 * summary, a photo of a prescription. The page says plainly that nothing in a
 * document counts until the care team has checked it, because that is the rule
 * the whole layer is built on.
 */
export function FamilyDocuments() {
  const { notify } = useToast()
  const patients = useAsync<Patient[]>(() => patientsApi.list(), [])
  const patient = patients.data?.[0] ?? null

  const documents = useAsync<MedicalDocument[]>(
    async () => (patient ? documentsApi.list(patient.id) : []),
    [patient?.id],
  )

  // Opening this page is reading the updates: the menu count clears.
  useEffect(() => {
    void markDocumentsSeen()
  }, [])

  async function upload(file: File, options: DocumentUploadOptions) {
    if (!patient) return
    await documentsApi.upload(patient.id, file, options)
    notify('Document received. The care team will check it before it is added to the record.', 'success')
    await documents.reload({ quiet: true })
  }

  async function remove(document: MedicalDocument) {
    if (!window.confirm(`Remove "${document.title}"?`)) return
    try {
      await documentsApi.remove(document.id)
      notify('Document removed.', 'success')
      await documents.reload({ quiet: true })
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not remove that document.', 'error')
    }
  }

  if (patients.loading) return <LoadingScreen label="Loading documents" />
  if (patients.error) return <ErrorState message={patients.error} onRetry={() => patients.reload()} />
  if (!patient) {
    return (
      <EmptyState
        icon={<FileText aria-hidden />}
        title="No patient linked yet"
        description="Ask DoorDoctor to link a patient to your account."
      />
    )
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-h1 font-semibold text-text-primary">Documents</h1>
        <p className="text-small text-text-secondary">
          Reports, prescriptions and discharge papers for {patient.name}. The care team checks every
          document before anything in it is added to the record.
        </p>
      </header>

      <Card title="Add a document">
        <DocumentUploadForm onUpload={upload} />
      </Card>

      <Card title="Your documents" flush>
        {documents.loading && <LoadingScreen label="Loading documents" />}
        {documents.error && <ErrorState message={documents.error} onRetry={() => documents.reload()} />}
        {documents.data?.length === 0 && (
          <EmptyState
            icon={<FileText aria-hidden />}
            title="No documents yet"
            description="Upload a lab report, prescription or hospital letter and the care team will take it from there."
          />
        )}
        {documents.data && documents.data.length > 0 && (
          <ul className="divide-y divide-border-subtle px-5">
            {documents.data.map((document) => (
              <DocumentRow
                key={document.id}
                document={document}
                actions={
                  document.can_delete ? (
                    <Button variant="subtle" size="sm" onClick={() => void remove(document)}>
                      Remove
                    </Button>
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
