import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { ROLE_HOME, useAuth } from '../auth/AuthContext'
import { Disclaimer } from '../components/layout/Disclaimer'
import { Logo } from '../components/layout/Logo'
import { Button, Card, Input } from '../components/ui'

const DEMO_ACCOUNTS = [
  { role: 'Family member', email: 'family@doordoctor.in', description: "Lakshmi's health dashboard" },
  { role: 'Nurse', email: 'nurse@doordoctor.in', description: "Today's assigned visits" },
  { role: 'Admin', email: 'admin@doordoctor.in', description: 'Operations and alerts' },
]
const DEMO_PASSWORD = 'Demo@123'

export function Login() {
  const { user, login, initialising } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (!initialising && user) return <Navigate to={ROLE_HOME[user.role]} replace />

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

  function useDemoAccount(demoEmail: string) {
    setEmail(demoEmail)
    setPassword(DEMO_PASSWORD)
    setError(null)
  }

  return (
    <div className="flex min-h-screen flex-col bg-surface lg:flex-row">
      {/* Brand panel */}
      <aside className="relative overflow-hidden bg-navy-800 px-6 py-10 text-white sm:px-10 lg:w-[45%] lg:py-16">
        <div className="relative z-10 mx-auto max-w-md">
          <p className="text-h1 font-extrabold tracking-tight">
            DOOR<span className="text-brand-400">DOCTOR</span>
          </p>
          <p className="mt-1 text-caption font-medium uppercase tracking-[0.2em] text-navy-100">
            Elderly Healthcare
          </p>

          <h1 className="mt-10 text-display font-bold leading-tight sm:text-4xl">
            Care at home, visible to the family that cannot be there.
          </h1>
          <p className="mt-4 text-navy-100">
            Scheduled nurse visits, recorded vitals, medication adherence and threshold-based
            escalation - in one place.
          </p>

          <ol className="mt-10 space-y-3 text-small">
            {[
              'Nurse checks in and records vitals',
              'Threshold engine evaluates every reading',
              'Out-of-range readings raise an alert',
              'Family and admin see it immediately',
            ].map((step, index) => (
              <li key={step} className="flex items-start gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-500 text-caption font-bold">
                  {index + 1}
                </span>
                <span className="text-navy-50">{step}</span>
              </li>
            ))}
          </ol>
        </div>
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-brand-500/20 blur-3xl"
          aria-hidden="true"
        />
      </aside>

      {/* Sign-in panel */}
      <main className="flex flex-1 items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-md">
          <Logo variant="lockup" className="mx-auto mb-8" />

          <Card>
            <h2 className="text-h2 font-bold text-text-primary">Sign in</h2>
            <p className="mt-1 text-small text-text-secondary">Use a demo account to explore each role.</p>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
              <Input
                label="Email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="family@doordoctor.in"
                required
              />

              <Input
                label="Password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
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
                {submitting ? 'Signing in…' : 'Sign in'}
              </Button>
            </form>
          </Card>

          <div className="mt-6 rounded-2xl border border-border-subtle bg-surface-raised p-4">
            <p className="text-caption font-semibold uppercase tracking-wide text-text-secondary">Demo accounts</p>
            <ul className="mt-3 space-y-2">
              {DEMO_ACCOUNTS.map((account) => (
                <li key={account.email}>
                  <button
                    type="button"
                    onClick={() => useDemoAccount(account.email)}
                    className="flex w-full items-center justify-between gap-3 rounded-xl border border-border-subtle px-3 py-2.5 text-left hover:border-brand-300 hover:bg-brand-50/50"
                  >
                    <span>
                      <span className="block text-small font-semibold text-text-primary">{account.role}</span>
                      <span className="block text-caption text-text-secondary">{account.email}</span>
                    </span>
                    <span className="text-caption font-semibold text-brand-600">Use</span>
                  </button>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-caption text-text-secondary">
              Password for all demo accounts: <span className="font-semibold">{DEMO_PASSWORD}</span>
            </p>
          </div>

          <div className="mt-6">
            <Disclaimer compact />
          </div>
        </div>
      </main>
    </div>
  )
}
