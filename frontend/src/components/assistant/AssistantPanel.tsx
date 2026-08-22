import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Phone, Send } from 'lucide-react'

import { assistantApi } from '../../api/assistant'
import { ApiError } from '../../api/client'
import { useAsync } from '../../hooks/useAsync'
import type { AssistantMessage } from '../../types'
import { Button, Card, ErrorState, Skeleton, Textarea } from '../ui'
import { AssistantExchange } from './AssistantExchange'

export interface AssistantPanelProps {
  /** Family only. Omitted for admins, whose questions are org-wide. */
  patientId?: number | null
  /** Shown above the composer. Written by the page, because the two roles differ. */
  intro: string
  /** Family screens carry the 108 block; admin screens have their own escalation paths. */
  showEmergencyBlock?: boolean
}

/**
 * The assistant thread: history, suggestions, composer.
 *
 * The whole surface works with no API key configured — that is the demo
 * configuration, not a degraded one, and each answer says which it was.
 */
export function AssistantPanel({
  patientId,
  intro,
  showEmergencyBlock = false,
}: AssistantPanelProps) {
  const history = useAsync(() => assistantApi.conversations(), [])
  const suggestions = useAsync(() => assistantApi.suggestions(patientId), [patientId])

  const [messages, setMessages] = useState<AssistantMessage[]>([])
  const [question, setQuestion] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // The server owns the disclaimer text, and it differs by role. Held from the
  // most recent answer and shown once below the composer rather than repeated
  // under every message — "always close with the disclaimer" without a wall.
  const [disclaimer, setDisclaimer] = useState<string | null>(null)
  const threadEnd = useRef<HTMLDivElement>(null)
  const composer = useRef<HTMLTextAreaElement>(null)

  // Server history arrives newest-first; the thread reads oldest-first.
  useEffect(() => {
    if (history.data) setMessages([...history.data].reverse())
  }, [history.data])

  useEffect(() => {
    // Feature-detected: `scrollIntoView` is absent in jsdom and in some older
    // environments, and keeping the newest answer in view is a convenience that
    // must never be able to throw inside a render effect and blank the thread.
    const end = threadEnd.current
    if (messages.length && typeof end?.scrollIntoView === 'function') {
      end.scrollIntoView({ behavior: 'smooth', block: 'end' })
    }
  }, [messages.length])

  async function submit(text: string) {
    const cleaned = text.trim()
    if (!cleaned || sending) return

    setSending(true)
    setError(null)
    try {
      const answer = await assistantApi.ask(cleaned, patientId)
      setMessages((current) => [...current, answer])
      setDisclaimer(answer.disclaimer)
      setQuestion('')
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'Something went wrong. Please try again.',
      )
    } finally {
      setSending(false)
      composer.current?.focus()
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void submit(question)
  }

  return (
    <div className="space-y-4">
      {showEmergencyBlock && (
        // Permanent, not conditional. It is the one instruction that must be on
        // screen before the reader has typed anything.
        <div className="flex items-start gap-3 rounded-xl border border-status-critical-border bg-status-critical-bg p-4">
          <Phone
            className="mt-0.5 h-5 w-5 shrink-0 text-status-critical"
            aria-hidden="true"
            strokeWidth={2.5}
          />
          <p className="text-small font-medium text-status-critical">
            In an emergency, call <span className="tnum">108</span> for an ambulance first, then
            your nurse. This assistant reads recorded visit information and cannot send help.
          </p>
        </div>
      )}

      <Card title="Ask DoorDoctor" description={intro}>
        {history.error ? (
          <ErrorState message={history.error} onRetry={() => void history.reload()} />
        ) : (
          <>
            <div className="max-h-[28rem] space-y-5 overflow-y-auto pr-1" aria-live="polite">
              {history.loading && !messages.length ? (
                <div aria-busy="true" aria-label="Loading your questions">
                  <Skeleton className="mb-3 ml-auto h-9 w-2/3" />
                  <Skeleton className="h-20 w-full" />
                </div>
              ) : messages.length ? (
                messages.map((message) => (
                  <AssistantExchange key={message.id} message={message} />
                ))
              ) : (
                <p className="py-6 text-center text-small text-text-muted">
                  Nothing asked yet. Pick a question below, or type your own.
                </p>
              )}
              <div ref={threadEnd} />
            </div>

            {suggestions.data && suggestions.data.length > 0 && (
              <div className="mt-4 border-t border-border-subtle pt-4">
                <h3 className="text-caption font-semibold uppercase tracking-wide text-text-secondary">
                  Try asking
                </h3>
                <ul className="mt-2 flex flex-wrap gap-2">
                  {suggestions.data.map((suggestion) => (
                    <li key={suggestion.intent}>
                      <button
                        type="button"
                        disabled={sending}
                        onClick={() => void submit(suggestion.question)}
                        className="rounded-full border border-border-subtle bg-surface-raised px-3 py-1.5 text-small text-text-secondary transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 disabled:opacity-50"
                      >
                        {suggestion.question}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <form onSubmit={onSubmit} className="mt-4 border-t border-border-subtle pt-4">
              <Textarea
                ref={composer}
                label="Your question"
                hideLabel
                rows={2}
                value={question}
                maxLength={500}
                disabled={sending}
                placeholder="Ask in your own words…"
                error={error ?? undefined}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  // Enter sends; Shift+Enter is a newline. A two-row composer
                  // that needs a mouse to submit is a form, not a conversation.
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    void submit(question)
                  }
                }}
              />
              <div className="mt-2 flex items-center justify-between gap-3">
                <p className="text-caption text-text-muted">
                  {disclaimer ?? "Answers come from DoorDoctor's own records."}
                </p>
                <Button type="submit" loading={sending} disabled={!question.trim()} icon={<Send className="h-4 w-4" aria-hidden="true" />}>
                  Ask
                </Button>
              </div>
            </form>
          </>
        )}
      </Card>
    </div>
  )
}
