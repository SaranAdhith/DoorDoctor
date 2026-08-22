import { Link } from 'react-router-dom'

import { Section, Seo } from '../../components/public'
import { LinkButton } from '../../components/ui'

/**
 * The 404.
 *
 * `noIndex` because a search engine that indexes this page will show it to
 * somebody searching for the real one. It renders inside `PublicLayout`, so the
 * header and footer navigation are still there — a dead end with no way out is
 * the actual failure, not the wrong URL.
 */

const SUGGESTIONS = [
  { to: '/', label: 'Home' },
  { to: '/what-is-doordoctor', label: 'What is DoorDoctor' },
  { to: '/how-it-works', label: 'How it works' },
  { to: '/pricing', label: 'Pricing' },
  { to: '/faq', label: 'Frequently asked questions' },
  { to: '/contact', label: 'Contact us' },
]

export function NotFound() {
  return (
    <>
      <Seo
        title="Page not found"
        description="That page does not exist on the DoorDoctor website."
        path="/404"
        noIndex
      />

      <Section tone="default" narrow className="py-20 sm:py-24">
        <p className="text-caption font-semibold uppercase tracking-[0.14em] text-brand-700">
          404
        </p>
        <h1 className="mt-2 text-display font-bold tracking-tight text-text-primary">
          That page does not exist
        </h1>
        <p className="mt-4 text-body text-text-secondary">
          The link may be out of date, or the address may have a typo in it. Here is where most
          people are going.
        </p>

        <ul className="mt-8 grid gap-2 sm:grid-cols-2">
          {SUGGESTIONS.map((item) => (
            <li key={item.to}>
              <Link
                to={item.to}
                className="min-h-control flex items-center rounded-xl border border-border-subtle bg-surface px-4 text-body font-medium text-text-primary hover:border-brand-300 hover:bg-brand-50/60"
              >
                {item.label}
              </Link>
            </li>
          ))}
        </ul>

        <div className="mt-8 flex flex-wrap gap-3">
          <LinkButton to="/" variant="accent">
            Back to the home page
          </LinkButton>
          <LinkButton to="/login" variant="ghost">
            Sign in to your account
          </LinkButton>
        </div>
      </Section>
    </>
  )
}
