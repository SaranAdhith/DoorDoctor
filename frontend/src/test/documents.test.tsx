import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { DocumentRow, DocumentStatusBadge, DocumentUploadForm } from '../components/documents'
import { FactRow } from '../components/documents/FactReview'
import { OcrText } from '../components/documents/OcrText'
import { ToastProvider } from '../components/ui'
import type { ExtractedFact, MedicalDocument } from '../types/intelligence'

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
  facts_in_record: 0,
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

describe('OcrText (Phase 12)', () => {
  const CHANDRA =
    '<div data-bbox="1 2 3 4" data-label="Page-Header"><p>City Hospital<br/>Bengaluru</p></div>' +
    '<div data-label="Table"><table border="1"><thead><tr><th>Test</th><th>Result</th></tr></thead>' +
    '<tbody><tr><td>HbA1c</td><td>8.1</td></tr></tbody></table></div>' +
    '<div data-label="Image"><img alt="Hospital logo"/></div>' +
    '<div data-label="Text"><p>→ ORS 2 sachets</p></div>'

  it('turns Chandra layout HTML into readable text and a real table', () => {
    const { container } = render(<OcrText text={CHANDRA} />)
    expect(screen.getByText('Header')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Test' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '8.1' })).toBeInTheDocument()
    expect(screen.getByText('[Image: Hospital logo]')).toBeInTheDocument()
    expect(screen.getByText('→ ORS 2 sachets')).toBeInTheDocument()
    expect(container.textContent).not.toContain('data-bbox')
    expect(container.textContent).not.toContain('<td>')
  })

  it('never injects markup from an uploaded page', () => {
    const hostile =
      '<div data-label="Text"><p>Rx<script>window.__pwned = true</script>' +
      '<img src="x" onerror="window.__pwned = true" alt="x"/><a href="javascript:alert(1)">link</a></p></div>'
    const { container } = render(<OcrText text={hostile} />)
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('a')).toBeNull()
    expect(container.innerHTML).not.toContain('onerror')
    expect((window as unknown as { __pwned?: boolean }).__pwned).toBeUndefined()
    expect(screen.getByText(/Rx/)).toBeInTheDocument()
  })

  it('shows a PDF text layer as it is, and the raw output on request', () => {
    render(<OcrText text={'Haemoglobin 12.4 g/dL'} />)
    expect(screen.getByText('Haemoglobin 12.4 g/dL')).toBeInTheDocument()
    expect(screen.queryByText('Show raw OCR output')).not.toBeInTheDocument()
  })

  it('lets an admin see the raw OCR output', () => {
    render(<OcrText text={CHANDRA} />)
    fireEvent.click(screen.getByText('Show raw OCR output'))
    expect(screen.getByText(/data-label="Table"/)).toBeInTheDocument()
  })
})

describe('Fact review (Phase 12, Stage 2)', () => {
  const proposed: ExtractedFact = {
    id: 11,
    page_no: 1,
    kind: 'lab_value',
    label: 'HbA1c',
    value_text: '8.1',
    value_num: 8.1,
    unit: '%',
    ref_low: 4,
    ref_high: 5.6,
    out_of_range: true,
    observed_on: null,
    status: 'proposed',
    source: 'table',
    source_quote: 'HbA1c | 8.1 | % | 4.0 - 5.6',
    original: null,
  }

  it('shows the value beside the page text it came from', () => {
    render(<ul><FactRow fact={proposed} locked={false} onDecide={vi.fn()} /></ul>)
    expect(screen.getByText('8.1')).toBeInTheDocument()
    expect(screen.getByText('Outside range')).toBeInTheDocument()
    expect(screen.getByText('HbA1c | 8.1 | % | 4.0 - 5.6')).toBeInTheDocument()
    expect(screen.getByText(/Read from a table · page 1/)).toBeInTheDocument()
    expect(screen.getByText('Needs a decision')).toBeInTheDocument()
  })

  it('confirms and rejects with one click', async () => {
    const onDecide = vi.fn().mockResolvedValue(undefined)
    render(<ul><FactRow fact={proposed} locked={false} onDecide={onDecide} /></ul>)
    fireEvent.click(screen.getByRole('button', { name: /Confirm/ }))
    await waitFor(() => expect(onDecide).toHaveBeenCalledWith('confirm', undefined))
    fireEvent.click(screen.getByRole('button', { name: /Reject/ }))
    await waitFor(() => expect(onDecide).toHaveBeenCalledWith('reject', undefined))
  })

  it('sends a correction with the edited value', async () => {
    const onDecide = vi.fn().mockResolvedValue(undefined)
    render(<ul><FactRow fact={{ ...proposed, label: 'DRS', value_text: '2 sachets', unit: '' }} locked={false} onDecide={onDecide} /></ul>)
    fireEvent.click(screen.getByRole('button', { name: /Correct/ }))
    fireEvent.change(screen.getByLabelText(/What it is/), { target: { value: 'ORS' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save correction' }))
    await waitFor(() => expect(onDecide).toHaveBeenCalledOnce())
    expect(onDecide.mock.calls[0][0]).toBe('edit')
    expect(onDecide.mock.calls[0][1]).toMatchObject({ label: 'ORS', value_text: '2 sachets' })
  })

  it('shows what software first read after a correction', () => {
    render(
      <ul>
        <FactRow
          fact={{ ...proposed, label: 'ORS', status: 'edited', original: { label: 'DRS', value_text: '2 sachets' } }}
          locked={false}
          onDecide={vi.fn()}
        />
      </ul>,
    )
    expect(screen.getByText('Corrected')).toBeInTheDocument()
    expect(screen.getByText(/Originally read as/)).toHaveTextContent('Originally read as: DRS 2 sachets')
  })

  it('offers no actions on a decided document', () => {
    render(<ul><FactRow fact={proposed} locked onDecide={vi.fn()} /></ul>)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})

describe('Documents menu badge (Phase 12)', () => {
  it('shows the count, caps it at 9+, and hides at zero', async () => {
    const { NavBadge } = await import('../components/layout/NavBadge')
    const { rerender } = render(<NavBadge count={3} label="document updates" />)
    expect(screen.getByLabelText('3 document updates')).toHaveTextContent('3')
    rerender(<NavBadge count={14} label="document updates" />)
    expect(screen.getByLabelText('14 document updates')).toHaveTextContent('9+')
    rerender(<NavBadge count={0} label="document updates" />)
    expect(screen.queryByLabelText(/document updates/)).not.toBeInTheDocument()
  })
})
