import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { ROLE_HOME, useAuth } from '../auth/AuthContext'
import { Disclaimer } from '../components/layout/Disclaimer'
import { Logo } from '../components/layout/Logo'

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
    <div className="flex min-h-screen flex-col bg-slate-50 lg:flex-row">
      {/* Brand panel */}
      <aside className="relative overflow-hidden bg-navy-800 px-6 py-10 text-white sm:px-10 lg:w-[45%] lg:py-16">
        <div className="relative z-10 mx-auto max-w-md">
          <p className="text-2xl font-extrabold tracking-tight">
            DOOR<span className="text-brand-400">DOCTOR</span>
          </p>
          <p className="mt-1 text-xs font-medium uppercase tracking-[0.2em] text-navy-100">
            Elderly Healthcare
          </p>

          <h1 className="mt-10 text-3xl font-bold leading-tight sm:text-4xl">
            Care at home, visible to the family that cannot be there.
          </h1>
          <p className="mt-4 text-navy-100">
            Scheduled nurse visits, recorded vitals, medication adherence and threshold-based
            escalation - in one place.
          </p>

          <ol className="mt-10 space-y-3 text-sm">
            {[
              'Nurse checks in and records vitals',
              'Threshold engine evaluates every reading',
              'Out-of-range readings raise an alert',
              'Family and admin see it immediately',
            ].map((step, index) => (
              <li key={step} className="flex items-start gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-500 text-xs font-bold">
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

          <div className="card">
            <h2 className="text-xl font-bold text-navy-800">Sign in</h2>
            <p className="mt-1 text-sm text-slate-500">Use a demo account to explore each role.</p>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
              <div>
                <label className="field-label" htmlFor="email">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="username"
                  className="field-input"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="family@doordoctor.in"
                  required
                />
              </div>

              <div>
                <label className="field-label" htmlFor="password">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  className="field-input"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Demo@123"
                  required
                />
              </div>

              {error && (
                <p className="rounded-xl bg-critical-50 px-3 py-2.5 text-sm font-medium text-critical-700" role="alert">
                  {error}
                </p>
              )}

              <button type="submit" className="btn-accent w-full" disabled={submitting}>
                {submitting ? 'Signing in...' : 'Sign in'}
              </button>
            </form>
          </div>

          <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Demo accounts</p>
            <ul className="mt-3 space-y-2">
              {DEMO_ACCOUNTS.map((account) => (
                <li key={account.email}>
                  <button
                    type="button"
                    onClick={() => useDemoAccount(account.email)}
                    className="flex w-full items-center justify-between gap-3 rounded-xl border border-slate-200 px-3 py-2.5 text-left hover:border-brand-300 hover:bg-brand-50/50"
                  >
                    <span>
                      <span className="block text-sm font-semibold text-navy-800">{account.role}</span>
                      <span className="block text-xs text-slate-500">{account.email}</span>
                    </span>
                    <span className="text-xs font-semibold text-brand-600">Use</span>
                  </button>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-slate-500">
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
