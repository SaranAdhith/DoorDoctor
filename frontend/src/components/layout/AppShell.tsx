import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Menu } from 'lucide-react'

import { useAuth } from '../../auth/AuthContext'
import { cn } from '../../lib/cn'
import { Drawer } from '../ui'
import { AccountMenu } from './AccountMenu'
import { BottomTabs } from './BottomTabs'
import { Disclaimer } from './Disclaimer'
import { Logo } from './Logo'
import { NotificationBell } from './NotificationBell'
import { Sidebar } from './Sidebar'

const COLLAPSED_KEY = 'doordoctor.sidebar.collapsed'

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === 'true'
  } catch {
    // Private-mode browsers can throw on access; an expanded sidebar is the safe default.
    return false
  }
}

export function AppShell() {
  const { user } = useAuth()
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSED_KEY, String(collapsed))
    } catch {
      /* the preference is a convenience, not a requirement */
    }
  }, [collapsed])

  if (!user) return null

  return (
    <div className="flex min-h-screen bg-surface">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      {/* Sidebar: persistent from 768px, collapsible to icons from 1024px. */}
      <aside
        className={cn(
          'sticky top-0 z-sidebar hidden h-screen shrink-0 transition-[width] duration-200 md:block',
          collapsed ? 'w-[4.5rem]' : 'w-64',
        )}
      >
        <Sidebar role={user.role} collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      </aside>

      {/* Below 768px the same navigation is served in a drawer. */}
      <Drawer open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} title="Menu" side="left">
        <Sidebar
          role={user.role}
          collapsed={false}
          onToggle={() => undefined}
          onNavigate={() => setMobileNavOpen(false)}
        />
      </Drawer>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-header border-b border-border-subtle bg-surface-raised/95 backdrop-blur">
          <div className="flex h-16 items-center justify-between gap-3 px-4 sm:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                onClick={() => setMobileNavOpen(true)}
                aria-label="Open navigation"
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border-subtle text-text-secondary hover:bg-surface md:hidden"
              >
                <Menu className="h-5 w-5" aria-hidden="true" />
              </button>
              {/*
                At 375px the wordmark competes with the bell and account menu,
                so the mark alone carries the brand on the narrowest screens.
              */}
              <span className="md:hidden">
                <Logo variant="mark" className="sm:hidden" />
                <Logo showStrapline={false} className="hidden sm:flex" />
              </span>
            </div>

            <div className="flex items-center gap-3">
              <NotificationBell />
              <AccountMenu />
            </div>
          </div>
        </header>

        <main id="main-content" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
          <Outlet />
        </main>

        <footer className="border-t border-border-subtle bg-surface-raised">
          <div className="mx-auto w-full max-w-7xl px-4 py-5 sm:px-6">
            <Disclaimer />
          </div>
        </footer>

        <BottomTabs role={user.role} />
      </div>
    </div>
  )
}
