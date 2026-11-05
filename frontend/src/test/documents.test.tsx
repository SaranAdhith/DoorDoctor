import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { DocumentRow, DocumentStatusBadge, DocumentUploadForm } from '../components/documents'
import { ToastProvider } from '../components/ui'
import type { MedicalDocument } from '../types/intelligence'

const base: MedicalDocument = {
  id: 7,
  patient_id: 1,
  visit_id: null,
  title: 'CBC report.pdf',
  doc_type: 'lab_report',
  document_date: null,
  status: 'needs_manual',
  status_label: 'Waiting for the care team to check',
  page_count: 2,
  uploader_role: 'family',
  uploaded_by_name: 'Priya',
  uploaded_by_me: true,
  created_at: '2026-11-05T10:00:00Z',
  extracted_at: null,
  verified_at: null,
  file: { url: '/attachments/3', content_type: 'application/pdf', size_bytes: 1200 },
  can_delete: true,
}

describe('Documents (Phase 12)', () => {
  it('shows the server-written status to families, never the pipeline code', () => {
    render(<DocumentStatusBadge document={base} />)
    expect(screen.getByText('Waiting for the care team to check')).toBeInTheDocument()
    expect(screen.queryByText(/needs manual/)).not.toBeInTheDocument()
  })

  it('shows the pipeline state alongside the label on staff screens', () => {
    render(<DocumentStatusBadge document={base} showCode />)
    expect(screen.getByText(/needs manual/)).toBeInTheDocument()
  })

  it('describes who added a document and how long it is', () => {
    render(
      <ToastProvider>
        <ul>
          <DocumentRow document={base} />
        </ul>
      </ToastProvider>,
    )
    expect(screen.getByText('CBC report.pdf')).toBeInTheDocument()
    expect(screen.getByText(/Lab report .* added by you · 2 pages/)).toBeInTheDocument()
  })

  it('asks what the document is only after a file is chosen, then uploads it', async () => {
    const onUpload = vi.fn().mockResolvedValue(undefined)
    const { container } = render(
      <ToastProvider>
        <DocumentUploadForm onUpload={onUpload} />
      </ToastProvider>,
    )
    expect(screen.queryByLabelText('What is it?')).not.toBeInTheDocument()

    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['%PDF-1.4'], 'rx.pdf', { type: 'application/pdf' })
    fireEvent.change(input, { target: { files: [file] } })

    fireEvent.change(screen.getByLabelText('What is it?'), { target: { value: 'prescription' } })
    fireEvent.click(screen.getByRole('button', { name: 'Upload' }))

    await waitFor(() => expect(onUpload).toHaveBeenCalledOnce())
    expect(onUpload.mock.calls[0][0]).toBe(file)
    expect(onUpload.mock.calls[0][1]).toMatchObject({ docType: 'prescription' })
  })
})
