import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { authApi } from '../api/auth'
import { ForgotPassword } from '../pages/ForgotPassword'

vi.mock('../api/auth', () => ({
  authApi: { forgotPassword: vi.fn() },
}))

const forgotPassword = vi.mocked(authApi.forgotPassword)

const SERVER_MESSAGE =
  'If that email is registered with DoorDoctor, a reset link is on its way. The link is valid for 30 minutes.'

function renderPage() {
  return render(
    <MemoryRouter>
      <ForgotPassword />
    </MemoryRouter>,
  )
}

function submit(email: string) {
  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: email } })
  fireEvent.click(screen.getByRole('button', { name: /send reset link/i }))
}

describe('ForgotPassword', () => {
  beforeEach(() => {
    forgotPassword.mockReset()
  })

  it('shows the same confirmation for a known and an unknown address', async () => {
    // The server answers identically either way; the screen must not add a
    // difference of its own, or it becomes an account-enumeration oracle.
    forgotPassword.mockResolvedValue({
      message: SERVER_MESSAGE,
      debug_reset_url: 'http://localhost:5173/reset-password?token=abc123',
    })
    const known = renderPage()
    submit('family@doordoctor.in')
    const knownConfirmation = await screen.findByRole('status')
    const knownText = knownConfirmation.textContent
    known.unmount()

    forgotPassword.mockResolvedValue({ message: SERVER_MESSAGE, debug_reset_url: null })
    renderPage()
    submit('nobody@doordoctor.in')
    const unknownConfirmation = await screen.findByRole('status')

    expect(unknownConfirmation.textContent).toBe(knownText)
  })

  it('offers the development link only when the API returns one', async () => {
    forgotPassword.mockResolvedValue({
      message: SERVER_MESSAGE,
      debug_reset_url: 'http://localhost:5173/reset-password?token=abc123',
    })
    renderPage()
    submit('family@doordoctor.in')

    const link = await screen.findByRole('link', { name: /open the reset link/i })
    expect(link).toHaveAttribute('href', '/reset-password?token=abc123')
  })

  it('hides the development block when the API returns no link', async () => {
    forgotPassword.mockResolvedValue({ message: SERVER_MESSAGE, debug_reset_url: null })
    renderPage()
    submit('nobody@doordoctor.in')

    await screen.findByRole('status')
    expect(screen.queryByText(/development only/i)).not.toBeInTheDocument()
  })

  it('surfaces a rate-limit refusal instead of a false confirmation', async () => {
    const { ApiError } = await import('../api/client')
    forgotPassword.mockRejectedValue(new ApiError(429, 'Too many attempts. Please wait a few minutes and try again.'))
    renderPage()
    submit('family@doordoctor.in')

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/too many attempts/i)
    })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
