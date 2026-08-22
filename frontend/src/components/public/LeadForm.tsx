import { CheckCircle2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useLocation } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { publicApi } from '../../api/public'
import type { LeadKind } from '../../types'
import { Button, ErrorState, Input, Select, Textarea } from '../ui'

/**
 * The public enquiry form.
 *
 * This posts to the only unauthenticated write endpoint in the product, so two
 * things here are deliberate and should not be tidied away:
 *
 * 1. **The honeypot.** `company_website` is rendered, hidden from sight *and*
 *    from assistive tech, taken out of the tab order, and never written to by
 *    this component. A bot that fills every field it can find gets a cheerful
 *    success message and its submission is discarded server-side. Do not remove
 *    it, do not rename it without changing `schemas/lead.py`, and do not hide it
 *    with `display:none` alone — some bots skip those.
 * 2. **The 429 is handled as a sentence, not a stack trace.** The server sends a
 *    human message and a `Retry-After`; this shows the message.
 */

const KINDS: ReadonlyArray<{ value: LeadKind; label: string }> = [
  { value: 'family', label: 'Care for my parent or relative' },
  { value: 'nri', label: 'I live abroad, my parents are in India' },
  { value: 'corporate', label: 'Elder care as an employee benefit' },
  { value: 'institution', label: 'A residence or care home' },
  { value: 'other', label: 'Something else' },
]

interface Props {
  /** Preselects the enquiry type on the pricing pages. */
  defaultKind?: LeadKind
  title?: string
  description?: string
  submitLabel?: string
}

export function LeadForm({
  defaultKind = 'family',
  title = 'Tell us about your parents',
  description = 'We will come back to you within one working day. No obligation, and no automated calls.',
  submitLabel = 'Send enquiry',
}: Props) {
  const { pathname } = useLocation()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [city, setCity] = useState('')
  const [kind, setKind] = useState<LeadKind>(defaultKind)
  const [message, setMessage] = useState('')
  const [honeypot, setHoneypot] = useState('')

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      const { message: reply } = await publicApi.submitLead({
        name: name.trim(),
        email: email.trim(),
        phone: phone.trim() || undefined,
        city: city.trim() || undefined,
        kind,
        message: message.trim() || undefined,
        // Which page converted. The server records it; the marketing site is the
        // only reason it has more than one page.
        source_page: pathname,
        company_website: honeypot || undefined,
      })
      setSent(reply)
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'Your enquiry could not be sent. Please try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  if (sent) {
    return (
      <div
        className="rounded-2xl border border-status-good-border bg-status-good-bg p-6"
        role="status"
      >
        <CheckCircle2 className="h-8 w-8 text-status-good" aria-hidden="true" />
        <h2 className="mt-3 text-h2 font-bold text-text-primary">Enquiry sent</h2>
        <p className="mt-2 text-body text-text-secondary">{sent}</p>
        <p className="mt-4 text-small text-text-secondary">
          If this is urgent and someone needs medical help right now, call{' '}
          <a href="tel:108" className="font-semibold text-status-critical underline">
            108
          </a>
          .
        </p>
      </div>
    )
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border border-border-subtle bg-surface-raised p-6 shadow-card"
      noValidate
    >
      <h2 className="text-h2 font-bold text-text-primary">{title}</h2>
      <p className="mt-1.5 text-small text-text-secondary">{description}</p>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Input
          label="Your name"
          required
          value={name}
          autoComplete="name"
          maxLength={120}
          onChange={(event) => setName(event.target.value)}
        />
        <Input
          label="Email"
          type="email"
          required
          value={email}
          autoComplete="email"
          maxLength={255}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Input
          label="Phone"
          type="tel"
          value={phone}
          autoComplete="tel"
          maxLength={32}
          hint="Optional, but it is the fastest way to reach you."
          onChange={(event) => setPhone(event.target.value)}
        />
        <Input
          label="City"
          value={city}
          autoComplete="address-level2"
          maxLength={80}
          onChange={(event) => setCity(event.target.value)}
        />
      </div>

      <Select
        label="What is this about?"
        className="mt-4"
        value={kind}
        onChange={(event) => setKind(event.target.value as LeadKind)}
      >
        {KINDS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>

      <Textarea
        label="Anything you would like us to know"
        className="mt-4"
        value={message}
        rows={4}
        maxLength={2000}
        hint="Who needs care, roughly where they live, and what worries you most."
        onChange={(event) => setMessage(event.target.value)}
      />

      {/* Honeypot. Hidden from sight and from assistive tech, and out of the tab
          order, so no person will ever fill it in. See the note at the top. */}
      <div className="absolute left-[-9999px] top-auto h-px w-px overflow-hidden" aria-hidden="true">
        <label htmlFor="company_website">Company website</label>
        <input
          id="company_website"
          name="company_website"
          type="text"
          tabIndex={-1}
          autoComplete="off"
          value={honeypot}
          onChange={(event) => setHoneypot(event.target.value)}
        />
      </div>

      {error && <ErrorState message={error} className="mt-4" />}

      <Button type="submit" variant="accent" size="lg" fullWidth loading={submitting} className="mt-6">
        {submitting ? 'Sending…' : submitLabel}
      </Button>

      <p className="mt-3 text-caption text-text-muted">
        We use your details only to answer this enquiry. See our{' '}
        <a href="/privacy" className="underline hover:text-text-secondary">
          privacy policy
        </a>
        .
      </p>
    </form>
  )
}
