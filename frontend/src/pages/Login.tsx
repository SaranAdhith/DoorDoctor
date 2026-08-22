import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { CheckCircle2, Mail } from 'lucide-react'

import { ApiError } from '../api/client'
import { ROLE_HOME, useAuth } from '../auth/AuthContext'
import { AuthLayout } from '../components/layout/AuthLayout'
import { Button, Input, SegmentedControl } from '../components/ui'
import type { Role } from '../types'

/**
 * The segmented picker is **not** an authentication control.
 *
 * The server decides a user's role from their account; this only tailors the
 * copy and picks which demo account the demo block fills. Signing in as a nurse
 * with "Family" selected still succeeds and still lands on /nurse/visits.
 */
const ROLE_TABS: ReadonlyArray<{ role: Role; label: string; blurb: string; email: string }> = [
  {
    role: 'family',
    label: 'Family',
    blurb: 'See how your parent is doing, whenever you need to.',
    email: 'family@doordoctor.in',
  },
  {
    role: 'nurse',
    label: 'Nurse',
    blurb: 'Your visits for today, and the readings to record.',
    email: 'nurse@doordoctor.in',
  },
  {
    role: 'admin',
    label: 'Admin',
    blurb: 'The visit board, the alert queue and nurse coverage.',
    email: 'admin@doordoctor.in',
  },
]

const DEMO_PASSWORD = 'Demo@123'

interface LoginLocationState {
  passwordReset?: boolean
}

export function Login() {
  const { user, login, initialising } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [selectedRole, setSelectedRole] = useState<Role>('family')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Set by the reset-password screen so the success lands where the user does.
  const justReset = Boolean((location.state as LoginLocationState | null)?.passwordReset)

  if (!initialising && user) return <Navigate to={ROLE_HOME[user.role]} replace />

  const activeTab = ROLE_TABS.find((tab) => tab.role === selectedRole) ?? ROLE_TABS[0]

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const signedIn = await login(email.trim(), password)
      navigate(ROLE_HOME[signedIn.role], { replace: true })
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to sign in. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  function fillDemoAccount(demoEmail: string) {
    setEmail(demoEmail)
    setPassword(DEMO_PASSWORD)
    setError(null)
  }

  return (
    <AuthLayout
      title="Sign in"
      description={activeTab.blurb}
      // §2.5 asked for this in Phase 3 and it was deferred: `/` redirected to
      // `/login` back then, so the link would have been a loop. Phase 8 makes
      // `/` the public home, so it now goes somewhere.
      footer={
        <p className="text-center text-small text-text-secondary">
          <Link to="/" className="font-medium hover:text-text-primary hover:underline">
            &larr; Back to doordoctor.in
          </Link>
        </p>
      }
    >
      {justReset && (
        <p
          className="mb-5 flex items-start gap-2 rounded-xl border border-status-good-border bg-status-good-bg px-3.5 py-2.5 text-small font-medium text-status-good"
          role="status"
        >
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          Your password has been changed. Sign in with it below.
        </p>
      )}

      <SegmentedControl
        legend="I am signing in as"
        value={selectedRole}
        options={ROLE_TABS.map((tab) => ({ value: tab.role, label: tab.label }))}
        onChange={setSelectedRole}
      />

      <form onSubmit={handleSubmit} className="mt-5 space-y-4" noValidate>
        <Input
          label="Email"
          type="email"
          autoComplete="username"
          leadingIcon={<Mail className="h-4 w-4" />}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.com"
          required
        />

        <Input
          label="Password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          labelAction={
            <Link
              to="/forgot-password"
              className="mb-1.5 text-small font-semibold text-brand-700 hover:underline"
            >
              Forgot password?
            </Link>
          }
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
          {submitting ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>

      <details className="group mt-6 rounded-xl border border-border-subtle bg-surface px-4 py-3">
        <summary className="min-h-control -mx-1 flex cursor-pointer list-none items-center justify-between gap-3 px-1 text-small font-semibold text-text-primary">
          Demo access
          <span className="text-caption font-medium text-text-secondary group-open:hidden">Show</span>
          <span className="hidden text-caption font-medium text-text-secondary group-open:inline">
            Hide
          </span>
        </summary>

        <p className="mt-2 text-caption text-text-secondary">
          Every demo account uses the password{' '}
          <span className="font-semibold text-text-primary">{DEMO_PASSWORD}</span>. All data is
          fictional.
        </p>

        <ul className="mt-3 space-y-2">
          {ROLE_TABS.map((tab) => (
            <li key={tab.email}>
              <button
                type="button"
                onClick={() => {
                  setSelectedRole(tab.role)
                  fillDemoAccount(tab.email)
                }}
                className="min-h-control flex w-full items-center justify-between gap-3 rounded-lg border border-border-subtle bg-surface-raised px-3 py-2 text-left hover:border-brand-300 hover:bg-brand-50/60"
              >
                <span className="min-w-0">
                  <span className="block text-small font-semibold text-text-primary">
                    {tab.label}
                  </span>
                  <span className="block truncate text-caption text-text-secondary">
                    {tab.email}
                  </span>
                </span>
                <span className="shrink-0 text-caption font-semibold text-brand-700">Use</span>
              </button>
            </li>
          ))}
        </ul>
      </details>
    </AuthLayout>
  )
}
