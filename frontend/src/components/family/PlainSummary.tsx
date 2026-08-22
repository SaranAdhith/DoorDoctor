import { useState } from 'react'
import { HeartPulse, Info } from 'lucide-react'

import { summaryApi } from '../../api/summary'
import { useAsync } from '../../hooks/useAsync'
import { cn } from '../../lib/cn'
import type { SummaryHighlight, SummaryWindow } from '../../types'
import { Badge, Card, ErrorState, SegmentedControl, Skeleton, type BadgeTone } from '../ui'

const WINDOWS: ReadonlyArray<{ value: SummaryWindow; label: string }> = [
  { value: '7d', label: 'This week' },
  { value: '30d', label: 'This month' },
  { value: '90d', label: '3 months' },
]

/** The server's tones are already the clinical status vocabulary. */
const TONES: Record<SummaryHighlight['tone'], BadgeTone> = {
  good: 'good',
  watch: 'watch',
  attention: 'attention',
}

export interface PlainSummaryProps {
  patientId: number
}

/**
 * How your relative has been, in the language you actually speak.
 *
 * This is deliberately the first thing on the family dashboard. The detailed
 * clinical record still exists in full below it — it has simply stopped being
 * the front door, because a grid of numbers is not an answer to "is Amma okay?".
 *
 * The wording comes from the server (`summary_service`), which owns the
 * vocabulary rule. This component never composes a clinical sentence of its own.
 */
export function PlainSummary({ patientId }: PlainSummaryProps) {
  const [window, setWindow] = useState<SummaryWindow>('7d')
  const summary = useAsync(() => summaryApi.plain(patientId, window), [patientId, window])

  const picker = (
    <SegmentedControl
      legend="Summary period"
      hideLegend
      className="sm:w-80"
      value={window}
      options={WINDOWS}
      onChange={setWindow}
    />
  )

  if (summary.error) {
    return (
      <Card title="How they have been" action={picker}>
        <ErrorState message={summary.error} onRetry={() => void summary.reload()} />
      </Card>
    )
  }

  // `data` is kept while a new window loads, so switching period dims the card
  // rather than collapsing the page height and throwing the scroll position.
  const data = summary.data
  const loadingFirstTime = summary.loading && !data

  return (
    <Card
      title="How they have been"
      action={picker}
      className="border-brand-100 bg-gradient-to-br from-brand-50/60 to-surface-raised"
    >
      {loadingFirstTime ? (
        <div aria-busy="true" aria-label="Loading summary">
          <Skeleton className="mb-4 h-6 w-3/4" />
          <Skeleton className="mb-2.5 h-3 w-full" />
          <Skeleton className="mb-2.5 h-3 w-11/12" />
          <Skeleton className="h-3 w-2/3" />
        </div>
      ) : data ? (
        <div className={cn('transition-opacity', summary.loading && 'opacity-60')}>
          <div className="flex gap-3">
            <HeartPulse
              className="mt-0.5 h-6 w-6 shrink-0 text-brand-600"
              aria-hidden="true"
              strokeWidth={2}
            />
            <p className="text-h2 font-bold leading-snug text-text-primary">{data.headline}</p>
          </div>

          {data.highlights.length > 0 && (
            <ul className="mt-4 flex flex-wrap gap-2">
              {data.highlights.map((highlight) => (
                <li key={highlight.text}>
                  <Badge tone={TONES[highlight.tone]} dot>
                    {highlight.text}
                  </Badge>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-4 space-y-3">
            {data.paragraphs.map((paragraph) => (
              <p key={paragraph} className="text-body leading-relaxed text-text-secondary">
                {paragraph}
              </p>
            ))}
          </div>

          {data.what_happens_next.length > 0 && (
            <div className="mt-5 rounded-xl bg-surface-sunken p-4">
              <h3 className="text-caption font-semibold uppercase tracking-wide text-text-secondary">
                What happens next
              </h3>
              <ul className="mt-2 space-y-1.5">
                {data.what_happens_next.map((step) => (
                  <li key={step} className="flex gap-2 text-small text-text-secondary">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-600" aria-hidden="true" />
                    {step}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="mt-4 flex gap-2 text-caption text-text-muted">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            {data.disclaimer}
          </p>
        </div>
      ) : null}
    </Card>
  )
}
