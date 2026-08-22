import { ArrowRight } from 'lucide-react'

import { LinkButton } from '../ui'

/**
 * The closing band on most public pages: one question, two ways to answer it.
 *
 * Shared so the call to action is worded and placed identically everywhere —
 * a visitor who scrolls to the bottom of any page finds the same door.
 */

interface Props {
  title?: string
  description?: string
  primaryLabel?: string
  primaryTo?: string
  secondaryLabel?: string
  secondaryTo?: string
}

export function CtaBand({
  title = 'Talk to us about your parents',
  description = 'Tell us who needs looking after and where they live. We will come back to you within one working day.',
  primaryLabel = 'Send an enquiry',
  primaryTo = '/contact',
  secondaryLabel = 'See pricing',
  secondaryTo = '/pricing',
}: Props) {
  return (
    <section className="bg-navy-800 px-4 py-14 text-white sm:px-6 sm:py-16">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="max-w-2xl">
          <h2 className="text-h1 font-bold tracking-tight sm:text-display">{title}</h2>
          <p className="mt-3 text-navy-100">{description}</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <LinkButton
            to={primaryTo}
            variant="accent"
            size="lg"
            icon={<ArrowRight className="h-4 w-4" aria-hidden="true" />}
          >
            {primaryLabel}
          </LinkButton>
          <LinkButton
            to={secondaryTo}
            size="lg"
            className="border border-white/25 bg-transparent text-white hover:bg-white/10"
          >
            {secondaryLabel}
          </LinkButton>
        </div>
      </div>
    </section>
  )
}
