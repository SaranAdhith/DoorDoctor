import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'

/**
 * The vertical rhythm and measure every public page shares.
 *
 * Marketing pages are the place a codebase grows a second layout system, one
 * `py-24` at a time. These two components are that system, and they are the only
 * place a public page decides how much air a band of content gets.
 */

interface SectionProps {
  children: ReactNode
  /** `sunken` and `inverted` alternate the page's bands so it reads as sections. */
  tone?: 'default' | 'sunken' | 'inverted'
  className?: string
  id?: string
  /** Narrower measure for long-form prose (privacy, terms). */
  narrow?: boolean
}

const TONE: Record<NonNullable<SectionProps['tone']>, string> = {
  default: 'bg-surface-raised',
  sunken: 'bg-surface',
  inverted: 'bg-navy-800 text-white',
}

export function Section({ children, tone = 'default', className, id, narrow }: SectionProps) {
  return (
    <section id={id} className={cn(TONE[tone], 'px-4 py-14 sm:px-6 sm:py-16 lg:py-20', className)}>
      <div className={cn('mx-auto w-full', narrow ? 'max-w-3xl' : 'max-w-6xl')}>{children}</div>
    </section>
  )
}

interface HeadingProps {
  /** Small uppercase label above the heading. */
  eyebrow?: string
  title: string
  description?: ReactNode
  /** Centred for full-width bands, left for content that continues beside it. */
  align?: 'left' | 'center'
  /** Set on an inverted section so the text inverts with it. */
  inverted?: boolean
  as?: 'h2' | 'h3'
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  align = 'left',
  inverted = false,
  as: Tag = 'h2',
}: HeadingProps) {
  return (
    <div className={cn('max-w-2xl', align === 'center' && 'mx-auto text-center')}>
      {eyebrow && (
        <p
          className={cn(
            'text-caption font-semibold uppercase tracking-[0.14em]',
            inverted ? 'text-brand-300' : 'text-brand-700',
          )}
        >
          {eyebrow}
        </p>
      )}
      <Tag
        className={cn(
          'text-h1 font-bold tracking-tight sm:text-display',
          eyebrow && 'mt-2',
          inverted ? 'text-white' : 'text-text-primary',
        )}
      >
        {title}
      </Tag>
      {description && (
        <div className={cn('mt-3 text-body', inverted ? 'text-navy-100' : 'text-text-secondary')}>
          {description}
        </div>
      )}
    </div>
  )
}
