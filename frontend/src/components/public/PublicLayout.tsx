import { Menu, Phone, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'

import { ROLE_HOME, useAuth } from '../../auth/AuthContext'
import { cn } from '../../lib/cn'
import { Disclaimer } from '../layout/Disclaimer'
import { Logo } from '../layout/Logo'
import { LinkButton } from '../ui'

/**
 * The shell behind every public page.
 *
 * A sibling of `AuthLayout` and `AppShell`, not a replacement for either, and
 * built from the same primitives and the same Phase 2 tokens — a marketing site
 * with its own palette and its own buttons puts a visible seam between the page
 * that sells the product and the product.
 */

interface NavLinkSpec {
  to: string
  label: string
}

const PRIMARY_NAV: NavLinkSpec[] = [
  { to: '/what-is-doordoctor', label: 'What we do' },
  { to: '/how-it-works', label: 'How it works' },
  { to: '/who-its-for', label: "Who it's for" },
  { to: '/pricing', label: 'Pricing' },
  { to: '/nri', label: 'For NRI families' },
  { to: '/about', label: 'About' },
]

const FOOTER_NAV: { title: string; links: NavLinkSpec[] }[] = [
  {
    title: 'Product',
    links: [
      { to: '/what-is-doordoctor', label: 'What is DoorDoctor' },
      { to: '/how-it-works', label: 'How it works' },
      { to: '/who-its-for', label: "Who it's for" },
      { to: '/trust-and-safety', label: 'Trust and safety' },
    ],
  },
  {
    title: 'Pricing',
    links: [
      { to: '/pricing', label: 'For families' },
      { to: '/pricing/corporate', label: 'For employers' },
      { to: '/pricing/institutions', label: 'For residences' },
      { to: '/nri', label: 'For NRI families' },
    ],
  },
  {
    title: 'Company',
    links: [
      { to: '/about', label: 'About us' },
      { to: '/faq', label: 'FAQ' },
      { to: '/contact', label: 'Contact' },
      { to: '/login', label: 'Sign in' },
    ],
  },
  {
    title: 'Legal',
    links: [
      { to: '/privacy', label: 'Privacy policy' },
      { to: '/terms', label: 'Terms of service' },
    ],
  },
]

export function PublicLayout() {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  // A route change must close the menu, or a visitor taps a link and lands on
  // the new page still looking at the old page's navigation.
  useEffect(() => setMenuOpen(false), [pathname])

  // Public pages are long. Landing halfway down the next one is disorienting in
  // a way it never is inside the app, where routes are short and scroll rarely
  // matters. Guarded because jsdom has no `scrollTo`.
  useEffect(() => {
    if (typeof window !== 'undefined' && typeof window.scrollTo === 'function') {
      window.scrollTo({ top: 0 })
    }
  }, [pathname])

  return (
    <div className="flex min-h-screen flex-col bg-surface-raised">
      {/* Visible only once focused — the first tab stop on every public page. */}
      <a
        href="#main"
        className={cn(
          'sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-overlay',
          'focus:rounded-lg focus:bg-navy-800 focus:px-4 focus:py-2.5 focus:text-body',
          'focus:font-semibold focus:text-text-inverted',
        )}
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-header border-b border-border-subtle bg-surface-raised/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4 sm:px-6">
          <Link to="/" className="shrink-0" aria-label="DoorDoctor home">
            <Logo variant="header" showStrapline={false} />
          </Link>

          <nav aria-label="Main" className="ml-auto hidden lg:block">
            <ul className="flex items-center gap-1">
              {PRIMARY_NAV.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        'rounded-lg px-3 py-2 text-small font-medium transition-colors',
                        isActive
                          ? 'bg-surface text-text-primary'
                          : 'text-text-secondary hover:bg-surface hover:text-text-primary',
                      )
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>

          <div className="ml-auto flex items-center gap-2 lg:ml-0">
            {/* A signed-in visitor reading the marketing site is not a mistake to
                correct — the header simply offers them the way back in. */}
            {user ? (
              <LinkButton to={ROLE_HOME[user.role]} size="sm" variant="accent">
                {/* Every element in this row is `shrink-0`, so a label that is
                    one word longer than the signed-out buttons pushed the header
                    past 375px and gave the whole marketing site a horizontal
                    scrollbar on a phone. The label shortens instead. */}
                <span className="sm:hidden">Dashboard</span>
                <span className="hidden sm:inline">Go to dashboard</span>
              </LinkButton>
            ) : (
              <>
                <LinkButton to="/login" size="sm" variant="ghost" className="hidden sm:inline-flex">
                  Sign in
                </LinkButton>
                <LinkButton to="/contact" size="sm" variant="accent">
                  Talk to us
                </LinkButton>
              </>
            )}

            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-expanded={menuOpen}
              aria-controls="public-mobile-nav"
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              className="min-h-control min-w-control -mr-2 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface hover:text-text-primary lg:hidden"
            >
              {menuOpen ? (
                <X className="h-5 w-5" aria-hidden="true" />
              ) : (
                <Menu className="h-5 w-5" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>

        {menuOpen && (
          <nav
            id="public-mobile-nav"
            aria-label="Main"
            className="animate-fade-in border-t border-border-subtle bg-surface-raised px-4 pb-4 pt-2 lg:hidden"
          >
            <ul className="space-y-1">
              {PRIMARY_NAV.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        'min-h-control flex items-center rounded-lg px-3 text-body font-medium',
                        isActive ? 'bg-surface text-text-primary' : 'text-text-secondary',
                      )
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
              {!user && (
                <li>
                  <NavLink
                    to="/login"
                    className="min-h-control flex items-center rounded-lg px-3 text-body font-medium text-text-secondary"
                  >
                    Sign in
                  </NavLink>
                </li>
              )}
            </ul>
          </nav>
        )}
      </header>

      <main id="main" className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t-4 border-brand-500 bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
          <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-5">
            <div className="lg:col-span-1">
              {/* No strapline down here — the wordmark alone, as in the header. */}
              <Logo variant="header" showStrapline={false} />
              <p className="mt-4 max-w-xs text-small text-text-secondary">
                Scheduled nurse visits at home for elderly parents in Bengaluru, with everything
                that happens visible to the family.
              </p>
              <a
                href="tel:108"
                className="mt-4 inline-flex items-center gap-2 text-small font-semibold text-status-critical"
              >
                <Phone className="h-4 w-4" aria-hidden="true" />
                In an emergency, call 108
              </a>
            </div>

            {FOOTER_NAV.map((group) => (
              <div key={group.title}>
                <h2 className="text-small font-semibold text-text-primary">{group.title}</h2>
                <ul className="mt-3 space-y-2">
                  {group.links.map((link) => (
                    <li key={`${group.title}-${link.to}`}>
                      <Link
                        to={link.to}
                        className="text-small text-text-secondary hover:text-text-primary hover:underline"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="mt-10 space-y-3 border-t border-border-subtle pt-6">
            <Disclaimer />
            <p className="text-caption text-text-muted">
              © {new Date().getFullYear()} DoorDoctor. Founded by Saran Adhith and Darren D&rsquo;Souza.
              Bengaluru, India.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
