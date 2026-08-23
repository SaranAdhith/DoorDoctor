import { CheckCircle2, CircleDashed, PhoneOff, XCircle } from 'lucide-react'

import type { EscalationStep } from '../../types'

/**
 * The parallel-notification timeline (§4.9).
 *
 * The one thing this must not do is imply a queue. Steps that share a
 * `sequence` went out **at the same moment**, and drawing them stacked with
 * their own connector line would tell the reader the fourth person was
 * contacted only after the third — which is not what happened, and is exactly
 * the reassurance a family should not be given falsely.
 *
 * So steps are grouped by sequence, and each group renders as one row of
 * simultaneous contacts under a single marker.
 */

const STATUS_ICONS: Record<string, typeof CheckCircle2> = {
  simulated: CheckCircle2,
  delivered: CheckCircle2,
  pending: CircleDashed,
  failed: XCircle,
  skipped: PhoneOff,
}

const STATUS_TONES: Record<string, string> = {
  simulated: 'text-status-good',
  delivered: 'text-status-good',
  pending: 'text-text-muted',
  failed: 'text-status-critical',
  skipped: 'text-text-muted',
}

function timeOf(value: string): string {
  return new Date(value).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
}

export function EscalationTimeline({ steps }: { steps: EscalationStep[] }) {
  if (steps.length === 0) {
    return <p className="text-small text-text-muted">Nothing has been recorded yet.</p>
  }

  const groups = new Map<number, EscalationStep[]>()
  for (const step of steps) {
    const bucket = groups.get(step.sequence)
    if (bucket) bucket.push(step)
    else groups.set(step.sequence, [step])
  }
  const ordered = [...groups.entries()].sort((a, b) => a[0] - b[0])

  return (
    <ol className="space-y-4">
      {ordered.map(([sequence, group], index) => (
        <li key={sequence} className="relative pl-6">
          {index < ordered.length - 1 && (
            <span
              aria-hidden
              className="absolute left-[7px] top-5 h-[calc(100%+0.5rem)] w-px bg-border-subtle"
            />
          )}
          <span
            aria-hidden
            className="absolute left-0 top-1.5 h-[15px] w-[15px] rounded-full border-2 border-border-strong bg-surface-raised"
          />

          {group.length > 1 && (
            <p className="mb-1 text-caption font-medium uppercase tracking-wide text-text-muted">
              {/* Said explicitly, because the visual grouping alone is a
                  convention the reader has not agreed to. */}
              {group.length} contacts at the same time
            </p>
          )}

          <ul className="space-y-1.5">
            {group.map((step) => {
              const Icon = STATUS_ICONS[step.status] ?? CircleDashed
              const tone = STATUS_TONES[step.status] ?? 'text-text-muted'
              return (
                <li key={step.id} className="flex items-start gap-2">
                  <Icon size={14} aria-hidden className={`mt-0.5 shrink-0 ${tone}`} />
                  <div className="min-w-0">
                    <p className="text-small text-text-primary">
                      <span className="font-medium">{step.actor}</span>
                      <span className="text-text-muted"> · {step.channel} · </span>
                      {step.target}
                      <span className="tnum ml-2 text-caption text-text-muted">
                        {timeOf(step.occurred_at)}
                      </span>
                    </p>
                    <p className="text-caption text-text-secondary">{step.detail}</p>
                  </div>
                </li>
              )
            })}
          </ul>
        </li>
      ))}
    </ol>
  )
}
