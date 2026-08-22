import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import { publicApi } from '../api/public'
import { LeadForm } from '../components/public/LeadForm'

vi.mock('../api/public', () => ({
  publicApi: { submitLead: vi.fn(), plans: vi.fn() },
}))

const submitLead = vi.mocked(publicApi.submitLead)

const ACCEPTED =
  'Thank you — your enquiry has reached the DoorDoctor team. We will be in touch within one working day.'

function renderForm(route = '/contact') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <LeadForm />
    </MemoryRouter>,
  )
}

function fillRequired() {
  fireEvent.change(screen.getByLabelText(/your name/i), { target: { value: 'Ramesh Iyer' } })
  fireEvent.change(screen.getByLabelText(/^email/i), {
    target: { value: 'ramesh@example.com' },
  })
}

function send() {
  fireEvent.click(screen.getByRole('button', { name: /send enquiry/i }))
}

describe('LeadForm', () => {
  beforeEach(() => {
    submitLead.mockReset()
    submitLead.mockResolvedValue({ message: ACCEPTED })
  })

  it('submits an enquiry and shows the server’s confirmation', async () => {
    renderForm()
    fillRequired()
    send()

    await waitFor(() => expect(submitLead).toHaveBeenCalledTimes(1))
    // The confirmation is the server's sentence, not one the client invented —
    // otherwise the two drift and the page starts promising its own SLA.
    expect(await screen.findByRole('status')).toHaveTextContent(ACCEPTED)
  })

  it('records which page converted', async () => {
    // A marketing site only has more than one page because this is knowable.
    renderForm('/pricing/corporate')
    fillRequired()
    send()

    await waitFor(() => expect(submitLead).toHaveBeenCalled())
    expect(submitLead.mock.calls[0][0]).toMatchObject({ source_page: '/pricing/corporate' })
  })

  it('never sends a honeypot value of its own', async () => {
    // A person cannot fill the honeypot, so the field must go out empty. If this
    // ever fails, every real enquiry is being silently discarded server-side.
    renderForm()
    fillRequired()
    send()

    await waitFor(() => expect(submitLead).toHaveBeenCalled())
    expect(submitLead.mock.calls[0][0].company_website).toBeUndefined()
  })

  it('keeps the honeypot out of the tab order and away from screen readers', () => {
    renderForm()

    const honeypot = document.getElementById('company_website')
    expect(honeypot).not.toBeNull()
    expect(honeypot).toHaveAttribute('tabindex', '-1')
    expect(honeypot?.closest('[aria-hidden="true"]')).not.toBeNull()
  })

  it('omits optional fields rather than sending empty strings', async () => {
    renderForm()
    fillRequired()
    send()

    await waitFor(() => expect(submitLead).toHaveBeenCalled())
    const payload = submitLead.mock.calls[0][0]
    expect(payload.phone).toBeUndefined()
    expect(payload.city).toBeUndefined()
    expect(payload.message).toBeUndefined()
  })

  it('shows the rate limit as a sentence rather than a failure', async () => {
    submitLead.mockRejectedValue(
      new ApiError(429, 'Too many attempts. Please wait a few minutes and try again.'),
    )
    renderForm()
    fillRequired()
    send()

    expect(await screen.findByRole('alert')).toHaveTextContent(/wait a few minutes/i)
    // And the form is still there to retry with, not replaced by the error.
    expect(screen.getByRole('button', { name: /send enquiry/i })).toBeInTheDocument()
  })

  it('tells someone with an emergency to call 108 instead of waiting for a reply', async () => {
    renderForm()
    fillRequired()
    send()

    const confirmation = await screen.findByRole('status')
    expect(confirmation).toHaveTextContent('108')
  })

  it('carries the enquiry type the page preselected', async () => {
    render(
      <MemoryRouter initialEntries={['/pricing/institutions']}>
        <LeadForm defaultKind="institution" />
      </MemoryRouter>,
    )
    fireEvent.change(screen.getByLabelText(/your name/i), { target: { value: 'Fr. Thomas' } })
    fireEvent.change(screen.getByLabelText(/^email/i), { target: { value: 't@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: /send enquiry/i }))

    await waitFor(() => expect(submitLead).toHaveBeenCalled())
    expect(submitLead.mock.calls[0][0].kind).toBe('institution')
  })
})
