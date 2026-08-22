import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { summaryApi } from '../api/summary'
import { PlainSummary } from '../components/family/PlainSummary'
import type { PlainSummary as PlainSummaryData, SummaryWindow } from '../types'

vi.mock('../api/summary', () => ({
  summaryApi: { plain: vi.fn() },
}))

const plain = vi.mocked(summaryApi.plain)

function summary(overrides: Partial<PlainSummaryData> = {}): PlainSummaryData {
  return {
    patient_id: 1,
    patient_name: "Lakshmi D'Souza",
    window: '7d',
    window_label: 'the last 7 days',
    headline: 'Lakshmi has been doing well over the last 7 days.',
    paragraphs: [
      'Lakshmi was checked 3 times in the last 7 days.',
      'Lakshmi took 10 of the 12 medicine doses the nurse recorded, which is good.',
    ],
    highlights: [
      { tone: 'good', text: 'Blood pressure steady' },
      { tone: 'attention', text: '1 still being reviewed' },
    ],
    what_happens_next: ['The next visit is on Sunday 23 August at 9:45 am.'],
    reading_count: 3,
    dose_count: 12,
    visit_count: 3,
    flagged_count: 0,
    open_alert_count: 0,
    generated_at: '2026-08-22T10:00:00',
    source: 'deterministic',
    disclaimer: 'This summary describes readings taken at home. It is not a medical diagnosis.',
    ...overrides,
  }
}

describe('PlainSummary', () => {
  beforeEach(() => {
    plain.mockReset()
  })

  it('leads with the headline and shows the whole narrative', async () => {
    plain.mockResolvedValue(summary())
    render(<PlainSummary patientId={1} />)

    expect(await screen.findByText(/doing well over the last 7 days/i)).toBeInTheDocument()
    expect(screen.getByText(/was checked 3 times/i)).toBeInTheDocument()
    expect(screen.getByText(/Blood pressure steady/i)).toBeInTheDocument()
    expect(screen.getByText(/next visit is on Sunday/i)).toBeInTheDocument()
    expect(screen.getByText(/not a medical diagnosis/i)).toBeInTheDocument()
  })

  it('asks the server for the window the reader picked', async () => {
    plain.mockImplementation((_id: number, window: SummaryWindow) =>
      Promise.resolve(summary({ window, headline: `Summary for ${window}.` })),
    )
    render(<PlainSummary patientId={1} />)

    await screen.findByText('Summary for 7d.')
    expect(plain).toHaveBeenCalledWith(1, '7d')

    fireEvent.click(screen.getByRole('radio', { name: 'This month' }))

    await screen.findByText('Summary for 30d.')
    expect(plain).toHaveBeenLastCalledWith(1, '30d')
  })

  it('never renders clinical vocabulary of its own', async () => {
    // The wording is the server's job. This asserts the component adds none of
    // its own — the banned list is enforced in `summary_service`, and a label
    // added here would slip past it entirely.
    plain.mockResolvedValue(summary())
    const { container } = render(<PlainSummary patientId={1} />)
    await screen.findByText(/doing well/i)

    const text = container.textContent?.toLowerCase() ?? ''
    for (const word of ['systolic', 'diastolic', 'spo2', 'adherence', 'threshold', 'breach']) {
      expect(text).not.toContain(word)
    }
  })

  it('offers a retry when the summary cannot be loaded', async () => {
    const { ApiError } = await import('../api/client')
    plain.mockRejectedValueOnce(new ApiError(500, 'Something went wrong.'))
    render(<PlainSummary patientId={1} />)

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/something went wrong/i))

    plain.mockResolvedValue(summary())
    fireEvent.click(screen.getByRole('button', { name: /try again|retry/i }))

    expect(await screen.findByText(/doing well/i)).toBeInTheDocument()
  })

  it('shows a loading placeholder before the first summary arrives', () => {
    plain.mockReturnValue(new Promise(() => {}))
    render(<PlainSummary patientId={1} />)

    expect(screen.getByLabelText(/loading summary/i)).toBeInTheDocument()
  })
})
