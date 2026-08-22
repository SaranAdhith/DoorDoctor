import { AlertTriangle, Sparkles, User } from 'lucide-react'

import { cn } from '../../lib/cn'
import type { AssistantMessage } from '../../types'
import { Badge } from '../ui'

export interface AssistantExchangeProps {
  message: AssistantMessage
}

/**
 * One question and the answer it received.
 *
 * An emergency answer is not styled as a paragraph. It is matched
 * deterministically on the server, never sent to a model, and it gets the
 * critical treatment plus `role="alert"` so a screen reader announces it
 * immediately rather than when the reader happens to reach it.
 */
export function AssistantExchange({ message }: AssistantExchangeProps) {
  const emergency = message.is_emergency

  return (
    <article className="space-y-3">
      <div className="flex justify-end">
        <p className="flex max-w-[85%] items-start gap-2 rounded-2xl rounded-br-sm bg-navy-700 px-4 py-2.5 text-small text-white">
          <User className="mt-0.5 h-4 w-4 shrink-0 opacity-70" aria-hidden="true" />
          <span className="min-w-0">{message.question}</span>
        </p>
      </div>

      <div
        className={cn(
          'rounded-2xl rounded-bl-sm border p-4',
          emergency
            ? 'border-status-critical-border bg-status-critical-bg'
            : 'border-border-subtle bg-surface-sunken',
        )}
        {...(emergency ? { role: 'alert' } : {})}
      >
        <div className="mb-2 flex flex-wrap items-center gap-2">
          {emergency ? (
            <AlertTriangle
              className="h-4 w-4 shrink-0 text-status-critical"
              aria-hidden="true"
              strokeWidth={2.5}
            />
          ) : (
            <Sparkles className="h-4 w-4 shrink-0 text-brand-600" aria-hidden="true" />
          )}
          <span
            className={cn(
              'text-caption font-semibold uppercase tracking-wide',
              emergency ? 'text-status-critical' : 'text-text-secondary',
            )}
          >
            {emergency ? 'Emergency' : message.intent_title}
          </span>
          {/*
            Provenance is shown, not hidden. `deterministic` is the normal case
            and the configuration the demo runs in — labelling it lets the
            fallback be demonstrated rather than described.

            Except on an emergency: that answer is a fixed escalation, not a
            record lookup, and a provenance chip beside "call 108" is noise
            competing with the one instruction that matters.
          */}
          {!emergency && (
            <Badge tone={message.source === 'assisted' ? 'info' : 'neutral'}>
              {message.source === 'assisted' ? 'AI assisted' : 'Direct from records'}
            </Badge>
          )}
        </div>

        {message.answer.split('\n').map((line, index) =>
          line.trim() ? (
            <p
              key={index}
              className={cn(
                'text-body leading-relaxed',
                index > 0 && 'mt-2',
                emergency ? 'font-medium text-status-critical' : 'text-text-primary',
              )}
            >
              {line}
            </p>
          ) : null,
        )}
      </div>
    </article>
  )
}
