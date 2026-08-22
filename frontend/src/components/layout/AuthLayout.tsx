import { Activity, Lock, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'

import { Disclaimer } from './Disclaimer'
import { Logo } from './Logo'

/**
 * The shell behind sign-in, forgot-password and reset-password.
 *
 * One layout for all three so they read as one product and not three forms.
 * The brand panel is decorative and comes second in the DOM on mobile — the
 * form is what someone came here to use.
 */

const HOW_IT_WORKS = [
  'A nurse checks in at the home and records vitals',
  'Every reading is checked against that patient’s thresholds',
  'An out-of-range reading raises an alert',
  'Family and the care team see it immediately',
]

/**
 * Claims limited to what the platform actually does. DoorDoctor is pre-launch:
 * no certifications, customer counts or partner logos belong here.
 */
const TRUST_SIGNALS = [
  { icon: ShieldCheck, label: 'Nurse credentials verified before assignment' },
  { icon: Activity, label: 'Threshold alerts worked by a care team' },
  { icon: Lock, label: 'Role-based access to every record' },
]

interface Props {
  title: string
  description?: ReactNode
  children: ReactNode
  /** Rendered under the card — a back-link, demo access, secondary actions. */
  footer?: ReactNode
}

export function AuthLayout({ title, description, children, footer }: Props) {
  return (
    <div className="flex min-h-screen flex-col bg-surface lg:flex-row">
      {/* Sign-in panel. First in the DOM: it is the reason for the page. */}
      <main className="order-1 flex flex-1 items-center justify-center px-4 py-10 sm:px-8 lg:order-2">
        <div className="w-full max-w-md">
          <Logo variant="lockup" className="mx-auto mb-8" />

          <div className="rounded-2xl border border-border-subtle bg-surface-raised p-6 shadow-card">
            <h1 className="text-h2 font-bold text-text-primary">{title}</h1>
            {description && <p className="mt-1.5 text-small text-text-secondary">{description}</p>}
            <div className="mt-6">{children}</div>
          </div>

          {footer && <div className="mt-6">{footer}</div>}

          <div className="mt-8 border-t border-border-subtle pt-5">
            <Disclaimer compact />
          </div>
        </div>
      </main>

      {/* Brand panel. */}
      <aside className="order-2 relative overflow-hidden bg-navy-800 px-6 py-10 text-white sm:px-10 lg:order-1 lg:w-[45%] lg:py-16">
        <div className="relative z-10 mx-auto flex h-full max-w-md flex-col justify-center">
          <p className="text-h1 font-extrabold tracking-tight">
            DOOR<span className="text-brand-400">DOCTOR</span>
          </p>
          <p className="mt-1 text-caption font-medium uppercase tracking-[0.2em] text-navy-100">
            Elderly Healthcare
          </p>

          <p className="mt-10 text-display font-bold leading-tight">
            Care at home, visible to the family that cannot be there.
          </p>
          <p className="mt-4 text-navy-100">
            Scheduled nurse visits, recorded vitals, medication adherence and threshold-based
            escalation — in one place.
          </p>

          <ol className="mt-10 space-y-3 text-small">
            {HOW_IT_WORKS.map((step, index) => (
              <li key={step} className="flex items-start gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-500 text-caption font-bold">
                  {index + 1}
                </span>
                <span className="text-navy-50">{step}</span>
              </li>
            ))}
          </ol>

          <ul className="mt-10 space-y-2.5 border-t border-white/15 pt-6">
            {TRUST_SIGNALS.map(({ icon: Icon, label }) => (
              <li key={label} className="flex items-center gap-2.5 text-small text-navy-100">
                <Icon className="h-4 w-4 shrink-0 text-brand-400" aria-hidden="true" />
                {label}
              </li>
            ))}
          </ul>
        </div>
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-brand-500/20 blur-3xl"
          aria-hidden="true"
        />
      </aside>
    </div>
  )
}
