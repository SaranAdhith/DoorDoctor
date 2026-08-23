import { ChevronDown, Info, Minus, TrendingDown, TrendingUp } from 'lucide-react'
import { useState } from 'react'

import type { SafetyBandTone, SafetyComponent, SafetyScore } from '../../types'
import { Card, ProgressMeter, Skeleton } from '../ui'
import type { MeterTone } from '../ui'

/**
 * The Senior Safety Score, and the breakdown that makes it defensible (§4.5).
 *
 * The rule this component exists to honour: **a score a family cannot have
 * explained to them is worse than no score, because it looks authoritative.**
 * So the breakdown is not an optional detail view — it is one click away on the
 * same card, it lists every component with its own weight and sentence, and it
 * says out loud which components had no data.
 *
 * Nothing here decides anything. The weights, the band, the tone and every
 * explanatory sentence are served from `core/clinical.py`; this renders them.
 */

const TONE_CLASSES: Record<SafetyBandTone, string> = {
  good: 'text-status-good',
  watch: 'text-status-watch',
  attention: 'text-status-attention',
  critical: 'text-status-critical',
}

function meterTone(tone: SafetyBandTone | null): MeterTone {
  // The band tones and the meter tones are the same four words by design —
  // Phase 2 chose them so a clinical status never needs translating.
  return (tone ?? 'watch') as MeterTone
}

export function SafetyScoreCardSkeleton() {
  return (
    <Card>
      <Skeleton className="h-5 w-40" />
      <Skeleton className="mt-4 h-12 w-24" />
      <Skeleton className="mt-4 h-2 w-full" />
    </Card>
  )
}

export function SafetyScoreCard({ score }: { score: SafetyScore }) {
  const [open, setOpen] = useState(false)

  if (!score.available || score.score === null) {
    return (
      <Card title="Safety score">
        <p className="text-small text-text-secondary">{score.unavailable_reason}</p>
        <p className="mt-2 text-caption text-text-muted">
          A score appears once there is enough recorded care to explain one.
        </p>
      </Card>
    )
  }

  const tone = score.band_tone
  const partial = score.covered_weight < score.total_weight

  return (
    <Card
      title="Safety score"
      description={`How things have been over the last ${score.window_days} days`}
    >
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <p className={`tnum text-display font-semibold ${tone ? TONE_CLASSES[tone] : ''}`}>
          {score.score}
          <span className="ml-1 text-h2 font-normal text-text-muted">/ 100</span>
        </p>
        <div className="min-w-0 flex-1">
          <p className={`text-body font-medium ${tone ? TONE_CLASSES[tone] : ''}`}>
            {score.band_label}
          </p>
          <p className="text-small text-text-secondary">{score.band_blurb}</p>
        </div>
        <Delta delta={score.delta} previous={score.previous_score} />
      </div>

      <div className="mt-4">
        <ProgressMeter
          label="Safety score"
          value={score.score}
          max={score.total_weight}
          tone={meterTone(tone)}
        />
      </div>

      {partial && (
        <p className="mt-3 flex items-start gap-1.5 text-caption text-text-muted">
          <Info size={13} className="mt-0.5 shrink-0" aria-hidden />
          {/* Said plainly rather than hidden. A score rescaled across four of six
              components is a different claim from one that had all six. */}
          <span>
            Based on {score.covered_weight} of {score.total_weight} points — the rest had nothing
            recorded yet, so they were left out rather than counted against.
          </span>
        </p>
      )}

      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        className="mt-4 flex items-center gap-1 rounded-sm text-small font-medium text-brand-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
      >
        {open ? 'Hide the breakdown' : 'What makes up this score?'}
        <ChevronDown
          size={15}
          aria-hidden
          className={`transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <ul className="mt-3 space-y-3 border-t border-border-subtle pt-3">
          {score.components.map((component) => (
            <ComponentRow key={component.key} component={component} />
          ))}
        </ul>
      )}
    </Card>
  )
}

function ComponentRow({ component }: { component: SafetyComponent }) {
  return (
    <li>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-small font-medium text-text-primary">{component.label}</p>
        <p className="tnum shrink-0 text-caption text-text-muted">
          {component.has_data ? (
            <>
              {component.points} of {component.weight}
            </>
          ) : (
            <span className="italic">not counted</span>
          )}
        </p>
      </div>
      <p className="mt-0.5 text-caption text-text-secondary">{component.detail}</p>
    </li>
  )
}

function Delta({ delta, previous }: { delta: number | null; previous: number | null }) {
  if (delta === null || previous === null) {
    return (
      <p className="text-caption text-text-muted">
        {/* Not "no change" — there is nothing to compare against yet, which is a
            different thing and would otherwise read as reassurance. */}
        No earlier score to compare with yet.
      </p>
    )
  }

  const Icon = delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus
  const tone =
    delta > 0 ? 'text-status-good' : delta < 0 ? 'text-status-attention' : 'text-text-muted'
  const word = delta > 0 ? 'up' : delta < 0 ? 'down' : 'unchanged'

  return (
    <p className={`flex items-center gap-1 text-small ${tone}`}>
      <Icon size={15} aria-hidden />
      <span className="tnum">
        {delta === 0 ? 'Unchanged' : `${word} ${Math.abs(delta)}`}
      </span>
      <span className="text-text-muted">from {previous}</span>
    </p>
  )
}
