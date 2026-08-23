import { Check, CircleDashed } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button, Card, ProgressMeter } from '../ui'
import type { OnboardingProgress } from '../../types'

/**
 * The setup checklist on the family dashboard (§4.15).
 *
 * It disappears the moment it is complete rather than sitting there ticked.
 * A finished checklist is clutter on the screen a family opens every day.
 *
 * Steps marked `derived` have no button: they complete themselves when the work
 * is done, and offering a tick would invite somebody to mark a thing done that
 * is not.
 */
export function OnboardingChecklist({
  progress,
  onAcknowledge,
}: {
  progress: OnboardingProgress
  onAcknowledge: (step: string) => void
}) {
  if (progress.complete) return null

  return (
    <Card
      title="Finish setting up"
      description={`${progress.completed} of ${progress.total} done. Each of these takes a minute.`}
    >
      <ProgressMeter
        value={progress.completed}
        max={progress.total}
        label="Setup progress"
        tone={progress.completed === progress.total ? 'good' : 'neutral'}
      />
      <ul className="mt-4 space-y-3">
        {progress.steps.map((step) => (
          <li key={step.key} className="flex items-start gap-3">
            <span
              className={step.done ? 'mt-0.5 text-status-good' : 'mt-0.5 text-text-muted'}
              aria-hidden
            >
              {step.done ? <Check className="h-5 w-5" /> : <CircleDashed className="h-5 w-5" />}
            </span>
            <div className="min-w-0 flex-1">
              <p
                className={
                  step.done ? 'text-text-muted line-through' : 'font-medium text-text-primary'
                }
              >
                {step.label}
              </p>
              {!step.done && <p className="text-small text-text-secondary">{step.blurb}</p>}
            </div>
            {!step.done &&
              (step.derived ? (
                <Link
                  to={step.path}
                  className="shrink-0 text-small font-medium text-brand-700 hover:underline"
                >
                  Open
                </Link>
              ) : (
                <Button size="sm" variant="subtle" onClick={() => onAcknowledge(step.key)}>
                  Looks right
                </Button>
              ))}
          </li>
        ))}
      </ul>
    </Card>
  )
}
