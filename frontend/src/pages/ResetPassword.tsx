import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, LinkIcon } from 'lucide-react'

import { authApi } from '../api/auth'
import { ApiError } from '../api/client'
import { AuthLayout } from '../components/layout/AuthLayout'
import { Button, Input, LinkButton, Spinner } from '../components/ui'
import { cn } from '../lib/cn'
import { PASSWORD_RULE, passwordProblem, passwordStrength } from '../lib/password'

const STRENGTH_LABEL = { weak: 'Weak', fair: 'Fair', strong: 'Strong' } as const
const STRENGTH_STYLE = {
  weak: { bar: 'bg-status-attention', text: 'text-status-attention', width: 'w-1/3' },
  fair: { bar: 'bg-status-watch', text: 'text-status-watch', width: 'w-2/3' },
  strong: { bar: 'bg-status-good', text: 'text-status-good', width: 'w-full' },
} as const

export function ResetPassword() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') ?? ''

  const [tokenValid, setTokenValid] = useState<boolean | null>(null)
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [showProblems, setShowProblems] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Checked up front so an expired link says so before anyone types a password.
  useEffect(() => {
    let active = true
    if (!token) {
      setTokenValid(false)
      return
    }
    authApi
      .checkResetToken(token)
      .then((status) => {
        if (active) setTokenValid(status.valid)
      })
      .catch(() => {
        if (active) setTokenValid(false)
      })
    return () => {
      active = false
    }
  }, [token])

  const problem = passwordProblem(password)
  const mismatch = confirmation.length > 0 && confirmation !== password
  const strength = passwordStrength(password)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setShowProblems(true)
    if (problem || password !== confirmation) return

    setSubmitting(true)
    setError(null)
    try {
      await authApi.resetPassword(token, password)
      navigate('/login', { replace: true, state: { passwordReset: true } })
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : 'Unable to reset the password. Please try again.',
      )
      // A rejected token cannot be retried, so send the user back to the start.
      if (caught instanceof ApiError && caught.status === 400) setTokenValid(false)
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

  if (tokenValid === null) {
    return (
      <AuthLayout title="Checking your link" footer={backLink}>
        <p className="flex items-center gap-2.5 text-small text-text-secondary">
          <Spinner className="h-4 w-4" />
          One moment…
        </p>
      </AuthLayout>
    )
  }

  if (!tokenValid) {
    return (
      <AuthLayout
        title="This link no longer works"
        description="Reset links last 30 minutes and can be used once."
        footer={backLink}
      >
        <p
          className="flex items-start gap-2.5 rounded-xl border border-status-watch-border bg-status-watch-bg px-3.5 py-3 text-small text-status-watch"
          role="alert"
        >
          <LinkIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {error ??
            'This link has expired, has already been used, or a newer one was requested. Your password has not changed.'}
        </p>

        <LinkButton to="/forgot-password" variant="accent" fullWidth className="mt-5">
          Request a new link
        </LinkButton>
      </AuthLayout>
    )
  }

  const style = STRENGTH_STYLE[strength]

  return (
    <AuthLayout
      title="Choose a new password"
      description="Pick something you don't use anywhere else."
      footer={backLink}
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <Input
          label="New password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          hint={PASSWORD_RULE}
          error={showProblems ? problem : null}
          required
        />

        {password.length > 0 && !problem && (
          <div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken">
              <div className={cn('h-full rounded-full transition-all', style.bar, style.width)} />
            </div>
            <p className={cn('mt-1.5 text-caption font-medium', style.text)} role="status">
              Password strength: {STRENGTH_LABEL[strength]}
            </p>
          </div>
        )}

        <Input
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          value={confirmation}
          onChange={(event) => setConfirmation(event.target.value)}
          error={mismatch || (showProblems && !confirmation) ? 'Both passwords must match.' : null}
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
          {submitting ? 'Saving…' : 'Set new password'}
        </Button>
      </form>
    </AuthLayout>
  )
}
