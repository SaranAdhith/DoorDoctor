import { NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '../../auth/AuthContext'
import type { Role } from '../../types'
import { Disclaimer } from './Disclaimer'
import { Logo } from './Logo'
import { NotificationBell } from './NotificationBell'

const NAV_BY_ROLE: Record<Role, { to: string; label: string }[]> = {
  family: [
    { to: '/family/dashboard', label: 'Dashboard' },
    { to: '/family/medications', label: 'Medications' },
    { to: '/family/alerts', label: 'Alerts' },
  ],
  nurse: [{ to: '/nurse/visits', label: "Today's Visits" }],
  admin: [
    { to: '/admin/dashboard', label: 'Dashboard' },
    { to: '/admin/visits', label: 'Visits' },
    { to: '/admin/patients', label: 'Patients' },
    { to: '/admin/nurses', label: 'Nurses' },
    { to: '/admin/alerts', label: 'Alerts' },
  ],
}

const ROLE_LABELS: Record<Role, string> = {
  family: 'Family Member',
  nurse: 'Nurse',
  admin: 'Admin',
}

export function AppShell() {
  const { user, logout } = useAuth()
  if (!user) return null

  const links = NAV_BY_ROLE[user.role]

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Logo />

          <div className="flex items-center gap-3">
            <NotificationBell />
            <div className="hidden text-right sm:block">
              <p className="text-sm font-semibold text-navy-800">{user.name}</p>
              <p className="text-xs text-slate-500">{ROLE_LABELS[user.role]}</p>
            </div>
            <button
              type="button"
              onClick={logout}
              className="btn-ghost whitespace-nowrap px-3 py-2 text-xs"
            >
              Sign out
            </button>
          </div>
        </div>

        <nav aria-label="Primary" className="border-t border-slate-100">
          <ul className="mx-auto flex w-full max-w-7xl gap-1 overflow-x-auto px-2 sm:px-5">
            {links.map((link) => (
              <li key={link.to}>
                <NavLink
                  to={link.to}
                  className={({ isActive }) =>
                    `inline-block whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-semibold transition-colors ${
                      isActive
                        ? 'border-brand-500 text-navy-800'
                        : 'border-transparent text-slate-500 hover:text-navy-800'
                    }`
                  }
                >
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto w-full max-w-7xl px-4 py-5 sm:px-6">
          <Disclaimer />
          <p className="mt-2 text-[11px] text-slate-400">
            DoorDoctor MVP - academic prototype. Demo data is fictional.
          </p>
        </div>
      </footer>
    </div>
  )
}
