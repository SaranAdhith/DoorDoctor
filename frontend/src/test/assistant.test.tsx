import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { assistantApi } from '../api/assistant'
import { AssistantPanel } from '../components/assistant/AssistantPanel'
import type { AssistantAnswer, AssistantMessage } from '../types'

vi.mock('../api/assistant', () => ({
  assistantApi: { ask: vi.fn(), conversations: vi.fn(), suggestions: vi.fn() },
}))

const ask = vi.mocked(assistantApi.ask)
const conversations = vi.mocked(assistantApi.conversations)
const suggestions = vi.mocked(assistantApi.suggestions)

function answer(overrides: Partial<AssistantAnswer> = {}): AssistantAnswer {
  return {
    id: 1,
    question: 'How has she been this week?',
    answer: 'Lakshmi has been doing well over the last 7 days.',
    intent: 'how_have_they_been',
    intent_title: 'How they have been',
    source: 'deterministic',
    is_emergency: false,
    patient_id: 1,
    disclaimer: 'I am not a doctor. In an emergency, call 108.',
    suggestions: ['What were her last readings?'],
    created_at: '2026-08-22T10:00:00',
    ...overrides,
  }
}

function message(overrides: Partial<AssistantMessage> = {}): AssistantMessage {
  const { disclaimer: _d, suggestions: _s, ...rest } = answer()
  return { ...rest, ...overrides }
}

describe('AssistantPanel', () => {
  beforeEach(() => {
    ask.mockReset()
    conversations.mockReset()
    suggestions.mockReset()
    conversations.mockResolvedValue([])
    suggestions.mockResolvedValue([
      { intent: 'latest_readings', title: 'Latest readings', question: 'What were her last readings?' },
      { intent: 'medicines', title: 'Medicines', question: 'Is she taking her medicines?' },
    ])
  })

  it('sends a typed question and shows the answer', async () => {
    ask.mockResolvedValue(answer())
    render(<AssistantPanel intro="Ask about care." patientId={1} />)

    const box = await screen.findByPlaceholderText(/ask in your own words/i)
    fireEvent.change(box, { target: { value: 'How has she been this week?' } })
    fireEvent.click(screen.getByRole('button', { name: /^ask$/i }))

    expect(await screen.findByText(/doing well over the last 7 days/i)).toBeInTheDocument()
    expect(ask).toHaveBeenCalledWith('How has she been this week?', 1)
  })

  it('asks the suggested question when a chip is clicked', async () => {
    ask.mockResolvedValue(answer({ answer: 'At the check on 20 August, blood pressure 132 over 84.' }))
    render(<AssistantPanel intro="Ask about care." patientId={1} />)

    fireEvent.click(await screen.findByRole('button', { name: 'What were her last readings?' }))

    expect(await screen.findByText(/132 over 84/)).toBeInTheDocument()
    expect(ask).toHaveBeenCalledWith('What were her last readings?', 1)
  })

  it('labels where the answer came from', async () => {
    // Provenance is shown, not hidden. `deterministic` is the configuration the
    // demo runs in, so the fallback can be demonstrated rather than described.
    ask.mockResolvedValue(answer())
    render(<AssistantPanel intro="Ask about care." patientId={1} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Is she taking her medicines?' }))

    expect(await screen.findByText(/direct from records/i)).toBeInTheDocument()
  })

  it('marks an assisted answer differently', async () => {
    ask.mockResolvedValue(answer({ source: 'assisted' }))
    render(<AssistantPanel intro="Ask about care." patientId={1} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Is she taking her medicines?' }))

    expect(await screen.findByText(/ai assisted/i)).toBeInTheDocument()
  })

  it('announces an emergency answer as an alert', async () => {
    // Matched deterministically on the server and never sent to a model. It must
    // be announced immediately rather than when the reader happens to reach it.
    ask.mockResolvedValue(
      answer({
        is_emergency: true,
        intent: 'emergency',
        intent_title: 'Emergency',
        answer: 'If this is an emergency, call 108 for an ambulance now.',
      }),
    )
    render(<AssistantPanel intro="Ask about care." patientId={1} showEmergencyBlock />)

    const box = await screen.findByPlaceholderText(/ask in your own words/i)
    fireEvent.change(box, { target: { value: 'she has collapsed' } })
    fireEvent.click(screen.getByRole('button', { name: /^ask$/i }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/call 108 for an ambulance/i)
  })

  it('always shows the 108 block on a family screen, before anything is asked', async () => {
    render(<AssistantPanel intro="Ask about care." patientId={1} showEmergencyBlock />)

    // "108" sits in its own `tnum` span, so the sentence spans several text
    // nodes and has to be matched on a fragment within one of them.
    expect(await screen.findByText(/for an ambulance first/i)).toBeInTheDocument()
    expect(screen.getByText('108')).toBeInTheDocument()
  })

  it('reads history oldest-first even though the server sends newest-first', async () => {
    conversations.mockResolvedValue([
      message({ id: 2, question: 'Second question' }),
      message({ id: 1, question: 'First question' }),
    ])
    render(<AssistantPanel intro="Ask about care." patientId={1} />)

    await screen.findByText('First question')
    // Anchored on both ends: the composer's visually-hidden label is literally
    // "Your question" and would otherwise join the list.
    const questions = screen.getAllByText(/^(First|Second) question$/).map((n) => n.textContent)
    expect(questions).toEqual(['First question', 'Second question'])
  })

  it('surfaces a rate limit without losing what was typed', async () => {
    const { ApiError } = await import('../api/client')
    ask.mockRejectedValue(new ApiError(429, 'Too many attempts. Please wait a few minutes.'))
    render(<AssistantPanel intro="Ask about care." patientId={1} />)

    const box = await screen.findByPlaceholderText(/ask in your own words/i)
    fireEvent.change(box, { target: { value: 'How has she been?' } })
    fireEvent.click(screen.getByRole('button', { name: /^ask$/i }))

    await waitFor(() => expect(screen.getByText(/too many attempts/i)).toBeInTheDocument())
    expect(box).toHaveValue('How has she been?')
  })

  it("closes with the server's disclaimer once an answer arrives", async () => {
    // §2.3 requires every answer to close with the monitoring disclaimer, and
    // the server owns its wording — the family and admin texts differ.
    ask.mockResolvedValue(answer({ disclaimer: 'I am not a doctor. In an emergency, call 108.' }))
    render(<AssistantPanel intro="Ask about care." patientId={1} />)

    expect(await screen.findByText(/answers come from doordoctor's own records/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Is she taking her medicines?' }))

    expect(await screen.findByText(/i am not a doctor\. in an emergency, call 108\./i)).toBeInTheDocument()
  })

  it('does not send an empty question', async () => {
    render(<AssistantPanel intro="Ask about care." patientId={1} />)

    await screen.findByPlaceholderText(/ask in your own words/i)
    expect(screen.getByRole('button', { name: /^ask$/i })).toBeDisabled()
    expect(ask).not.toHaveBeenCalled()
  })
})
