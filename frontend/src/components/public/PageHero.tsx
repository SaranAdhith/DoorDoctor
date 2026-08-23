import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'
import { EcgLine } from './EcgLine'

/**
 * The top of every public page.
 *
 * One component so fourteen pages cannot each invent their own idea of how big
 * a headline is — the pricing page and the FAQ should feel like the same site.
 *
 * Three tones. `light` is the default and the quiet one; `dark` is navy; `brand`
 * is the deep green used on the home page, where the hero is the first thing
 * anyone sees and ought to be the brand rather than a grey box.
 *
 * `brand` is the deep green hero: `brand-800` washed toward navy, carrying white
 * copy at 8.08:1 and 5.79:1 at the lighter end of the gradient.
 *
 * It is deliberately *not* the logo green. #32B641 (`brand-500`, sampled from
 * the mark) measures 2.66:1 against white — it can only carry dark text, and a
 * navy-on-bright-green hero was tried and rejected. Choosing white copy is what
 * forces the field down to brand-700 or darker, which is a deeper green than the
 * logo. That trade is the decision here, not an oversight: if a future edit
 * wants the exact logo green back, the text has to go dark with it.
 */

type Tone = 'light' | 'dark' | 'brand'

interface Props {
  eyebrow?: string
  title: ReactNode
  description?: ReactNode
  /** Buttons. Kept as children so a page can use `LinkButton` or a form. */
  actions?: ReactNode
  /** Below the actions: three or four short proof points, never a claim. */
  footnote?: ReactNode
  tone?: Tone
  /** Rendered beside the copy on wide screens — a screenshot stand-in, a card. */
  aside?: ReactNode
}

const SURFACE: Record<Tone, string> = {
  light: 'bg-surface',
  dark: 'bg-navy-800 text-white',
  brand: 'bg-brand-800 text-white',
}

const EYEBROW: Record<Tone, string> = {
  light: 'text-brand-700',
  dark: 'text-brand-300',
  brand: 'text-brand-200',
}

const TITLE: Record<Tone, string> = {
  light: 'text-text-primary',
  dark: 'text-white',
  brand: 'text-white',
}

const BODY: Record<Tone, string> = {
  light: 'text-text-secondary',
  dark: 'text-navy-100',
  brand: 'text-brand-50',
}

const FOOTNOTE: Record<Tone, string> = {
  light: 'text-text-muted',
  dark: 'text-navy-100',
  brand: 'text-brand-100',
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
  const onDark = tone !== 'light'

  return (
    <section
      className={cn(
        'relative overflow-hidden px-4 py-14 sm:px-6 sm:py-20 lg:py-24',
        SURFACE[tone],
      )}
    >
      {/* Depth wash. The gradient deepens toward navy so the band has somewhere
          to go without ever lightening under the white copy. */}
      {tone === 'brand' && (
        <div
          className="pointer-events-none absolute inset-0 bg-gradient-to-br from-brand-700 via-brand-800 to-navy-900"
          aria-hidden="true"
        />
      )}

      {/* Brand blooms. Stronger on the dark tones, barely there on light — the
          difference between a tinted page and a coloured rectangle stuck on. */}
      <div
        className={cn(
          'pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full blur-3xl',
          tone === 'brand' ? 'bg-brand-400/25' : tone === 'dark' ? 'bg-brand-500/20' : 'bg-brand-400/15',
        )}
        aria-hidden="true"
      />
      <div
        className={cn(
          'pointer-events-none absolute -bottom-40 -left-32 h-80 w-80 rounded-full blur-3xl',
          tone === 'brand' ? 'bg-brand-500/20' : 'bg-brand-300/10',
        )}
        aria-hidden="true"
      />

      <div
        className={cn(
          'relative z-10 mx-auto grid max-w-6xl gap-12',
          // Two columns only from `xl`. At `lg` the aside was wide enough to
          // squeeze the headline into four lines; below 1280 the hero stacks
          // instead, which gives the copy the full measure and the art the
          // full width. 30rem so nine faces stay legible side by side.
          Boolean(aside) && 'xl:grid-cols-[minmax(0,1fr)_minmax(0,30rem)] xl:items-center',
        )}
      >
        <div className={cn(!aside && 'max-w-3xl')}>
          {eyebrow && (
            <p
              className={cn(
                'text-caption font-semibold uppercase tracking-[0.14em]',
                EYEBROW[tone],
              )}
            >
              {eyebrow}
            </p>
          )}
          <h1
            className={cn(
              'text-display font-bold leading-tight tracking-tight sm:text-[2.5rem] sm:leading-[3rem]',
              // Balanced wrapping: the measure changes with the aside and the
              // breakpoint, so a hand-placed <br> is wrong at half of them.
              'text-balance',
              eyebrow && 'mt-3',
              TITLE[tone],
            )}
          >
            {title}
          </h1>
          {description && (
            <div
              className={cn(
                'mt-5 max-w-2xl text-body sm:text-[1.0625rem] sm:leading-7',
                BODY[tone],
              )}
            >
              {description}
            </div>
          )}
          {actions && <div className="mt-8 flex flex-wrap items-center gap-3">{actions}</div>}
          {footnote && (
            <div className={cn('mt-6 text-small', FOOTNOTE[tone])}>{footnote}</div>
          )}
        </div>

        {aside && <div className="min-w-0">{aside}</div>}
      </div>

      {/* The rule that closes every hero is a live trace, not a straight line.
          It is lifted clear of the bottom edge: the S wave is the deepest part
          of the waveform and sitting it on the floor made the trace look like it
          was resting on the section boundary rather than running across it. */}
      <EcgLine
        tone={tone === 'brand' ? 'on-green' : 'on-light'}
        className={cn('absolute inset-x-0 bottom-4 sm:bottom-6', onDark && 'opacity-95')}
      />
    </section>
  )
}
