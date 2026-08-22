import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'

/**
 * The top of every public page.
 *
 * One component so fourteen pages cannot each invent their own idea of how big
 * a headline is — the pricing page and the FAQ should feel like the same site.
 */

interface Props {
  eyebrow?: string
  title: ReactNode
  description?: ReactNode
  /** Buttons. Kept as children so a page can use `LinkButton` or a form. */
  actions?: ReactNode
  /** Below the actions: three or four short proof points, never a claim. */
  footnote?: ReactNode
  tone?: 'light' | 'dark'
  /** Rendered beside the copy on wide screens — a screenshot stand-in, a card. */
  aside?: ReactNode
}

export function PageHero({
  eyebrow,
  title,
  description,
  actions,
  footnote,
  tone = 'light',
  aside,
}: Props) {
  const dark = tone === 'dark'

  return (
    <section
      className={cn(
        'relative overflow-hidden px-4 py-14 sm:px-6 sm:py-20 lg:py-24',
        dark ? 'bg-navy-800 text-white' : 'bg-surface',
      )}
    >
      <div
        className={cn(
          'relative z-10 mx-auto grid max-w-6xl gap-12',
          Boolean(aside) && 'lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:items-center',
        )}
      >
        <div className={cn(!aside && 'max-w-3xl')}>
          {eyebrow && (
            <p
              className={cn(
                'text-caption font-semibold uppercase tracking-[0.14em]',
                dark ? 'text-brand-300' : 'text-brand-700',
              )}
            >
              {eyebrow}
            </p>
          )}
          <h1
            className={cn(
              'text-display font-bold leading-tight tracking-tight sm:text-[2.5rem] sm:leading-[3rem]',
              eyebrow && 'mt-3',
              dark ? 'text-white' : 'text-text-primary',
            )}
          >
            {title}
          </h1>
          {description && (
            <div
              className={cn(
                'mt-5 max-w-2xl text-body sm:text-[1.0625rem] sm:leading-7',
                dark ? 'text-navy-100' : 'text-text-secondary',
              )}
            >
              {description}
            </div>
          )}
          {actions && <div className="mt-8 flex flex-wrap items-center gap-3">{actions}</div>}
          {footnote && (
            <div className={cn('mt-6 text-small', dark ? 'text-navy-100' : 'text-text-muted')}>
              {footnote}
            </div>
          )}
        </div>

        {aside && <div className="min-w-0">{aside}</div>}
      </div>

      {dark && (
        <div
          className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-brand-500/20 blur-3xl"
          aria-hidden="true"
        />
      )}
    </section>
  )
}
