import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, MailCheck, Wrench } from 'lucide-react'

import { authApi } from '../api/auth'
import { ApiError } from '../api/client'
import { AuthLayout } from '../components/layout/AuthLayout'
import { Button, Input, LinkButton } from '../components/ui'

/**
 * Pulls the token out of the development-only link the API returns, so the
 * "open it" button routes inside the SPA instead of reloading the page — and
 * still works if the API's configured frontend URL is not this origin.
 */
function tokenFrom(url: string): string | null {
  const match = /[?&]token=([^&]+)/.exec(url)
  return match ? decodeURIComponent(match[1]) : null
}

export function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState<{ message: string; devToken: string | null } | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const response = await authApi.forgotPassword(email.trim())
      setSent({
        message: response.message,
        devToken: response.debug_reset_url ? tokenFrom(response.debug_reset_url) : null,
      })
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : 'Unable to send the link. Please try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  const backLink = (
    <Link
      to="/login"
      className="inline-flex min-h-control items-center gap-2 text-small font-semibold text-text-secondary hover:text-text-primary"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Back to sign in
    </Link>
  )

  // The confirmation is deliberately identical whether or not the address has
  // an account — the screen must not answer "does this person use DoorDoctor?"
  if (sent) {
    return (
      <AuthLayout
        title="Check your email"
        description="If we found an account, the link is on its way."
        footer={backLink}
      >
        <p
          className="flex items-start gap-2.5 rounded-xl border border-status-good-border bg-status-good-bg px-3.5 py-3 text-small text-status-good"
          role="status"
        >
          <MailCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {sent.message}
        </p>

        <p className="mt-4 text-small text-text-secondary">
          Nothing after a few minutes? Check the spam folder, or{' '}
          <button
            type="button"
            onClick={() => setSent(null)}
            className="font-semibold text-brand-700 underline hover:text-brand-800"
          >
            try a different email address
          </button>
          .
        </p>

        {sent.devToken && (
          <div className="mt-6 rounded-xl border border-dashed border-border-strong bg-surface p-4">
            <p className="flex items-center gap-2 text-caption font-semibold uppercase tracking-wide text-text-secondary">
              <Wrench className="h-3.5 w-3.5" aria-hidden="true" />
              Development only
            </p>
            <p className="mt-1.5 text-caption text-text-secondary">
              No mail provider is configured in this build, so the link is returned here instead.
              This block does not exist outside development.
            </p>
            <LinkButton
              to={`/reset-password?token=${encodeURIComponent(sent.devToken)}`}
              variant="ghost"
              size="sm"
              className="mt-3"
            >
              Open the reset link
            </LinkButton>
          </div>
        )}
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Forgot your password?"
      description="Enter the email on your DoorDoctor account and we'll send a link to set a new one."
      footer={backLink}
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <Input
          label="Email"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.com"
          hint="The link is valid for 30 minutes and can be used once."
          required
        />

        {error && (
          <p
            className="rounded-xl bg-status-critical-bg px-3 py-2.5 text-small font-medium text-status-critical"
            role="alert"
          >
            {error}
          </p>
        )}

        <Button type="submit" variant="accent" fullWidth loading={submitting}>
          {submitting ? 'Sending…' : 'Send reset link'}
        </Button>
      </form>
    </AuthLayout>
  )
}
