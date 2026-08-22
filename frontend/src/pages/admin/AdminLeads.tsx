import { useState } from 'react'
import { Mail, MapPin, Phone } from 'lucide-react'

import { ApiError } from '../../api/client'
import { leadsApi } from '../../api/leads'
import { useAsync } from '../../hooks/useAsync'
import { formatDateTime, formatRelative } from '../../lib/format'
import type { Lead, LeadStatus } from '../../types'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingScreen,
  SegmentedControl,
  StatTile,
  Textarea,
  useToast,
  type BadgeTone,
} from '../../components/ui'

/**
 * The enquiry queue.
 *
 * The other side of `POST /leads` — the only unauthenticated write in the
 * product. Rendered as cards rather than a table on purpose: a lead is mostly a
 * paragraph somebody typed, and a table column would truncate the one part that
 * tells you how to answer them.
 */

type Filter = 'all' | LeadStatus

const FILTERS: ReadonlyArray<{ value: Filter; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'new', label: 'New' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'qualified', label: 'Qualified' },
  { value: 'closed', label: 'Closed' },
]

const STATUS_TONES: Record<LeadStatus, BadgeTone> = {
  new: 'critical',
  contacted: 'watch',
  qualified: 'good',
  closed: 'neutral',
}

const KIND_LABELS: Record<string, string> = {
  family: 'Family',
  nri: 'NRI family',
  corporate: 'Employer',
  institution: 'Residence',
  other: 'Other',
}

/** The next sensible move, so the common case is one click and not a dropdown. */
const NEXT_STATUS: Partial<Record<LeadStatus, { to: LeadStatus; label: string }>> = {
  new: { to: 'contacted', label: 'Mark contacted' },
  contacted: { to: 'qualified', label: 'Mark qualified' },
  qualified: { to: 'closed', label: 'Close' },
}

export function AdminLeads() {
  const { notify } = useToast()
  const [filter, setFilter] = useState<Filter>('all')
  const [noteFor, setNoteFor] = useState<number | null>(null)
  const [noteDraft, setNoteDraft] = useState('')
  const [busyId, setBusyId] = useState<number | null>(null)

  const data = useAsync(async () => {
    const [leads, summary] = await Promise.all([
      leadsApi.list(filter === 'all' ? {} : { status: filter }),
      leadsApi.summary(),
    ])
    return { leads, summary }
  }, [filter])

  async function apply(lead: Lead, changes: { status?: LeadStatus; admin_note?: string }) {
    setBusyId(lead.id)
    try {
      await leadsApi.update(lead.id, changes)
      await data.reload({ quiet: true })
      notify(`${lead.name} updated.`, 'success')
      setNoteFor(null)
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'Something went wrong.', 'error')
    } finally {
      setBusyId(null)
    }
  }

  if (data.loading) return <LoadingScreen label="Loading enquiries" />
  if (data.error) return <ErrorState message={data.error} onRetry={() => void data.reload()} />
  if (!data.data) return null

  const { leads, summary } = data.data

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 font-bold text-text-primary">Leads</h1>
        <p className="mt-1 text-small text-text-secondary">
          Enquiries from the public site. Newest first — an enquiry is worth most on the day it
          arrives.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile
          label="Unworked"
          value={summary.new}
          tone={summary.new > 0 ? 'attention' : 'good'}
          hint={summary.new > 0 ? 'Waiting for a first reply' : 'Nothing waiting'}
        />
        <StatTile label="Contacted" value={summary.contacted} />
        <StatTile label="Qualified" value={summary.qualified} tone="good" />
        <StatTile label="Total received" value={summary.total} />
      </div>

      <Card
        title="Enquiries"
        action={
          <SegmentedControl
            legend="Filter enquiries"
            hideLegend
            value={filter}
            options={FILTERS}
            onChange={setFilter}
          />
        }
      >
        {leads.length === 0 ? (
          <EmptyState
            title={filter === 'all' ? 'No enquiries yet' : 'No enquiries match this filter'}
            description={
              filter === 'all'
                ? 'Enquiries submitted through the public site appear here.'
                : undefined
            }
          />
        ) : (
          <ul className="space-y-4">
            {leads.map((lead) => {
              const next = NEXT_STATUS[lead.status]
              const editing = noteFor === lead.id

              return (
                <li
                  key={lead.id}
                  className="rounded-2xl border border-border-subtle bg-surface p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-body font-semibold text-text-primary">{lead.name}</h3>
                        <Badge tone={STATUS_TONES[lead.status]}>{lead.status}</Badge>
                        <Badge tone="neutral">{KIND_LABELS[lead.kind] ?? lead.kind}</Badge>
                      </div>

                      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-small text-text-secondary">
                        <a
                          href={`mailto:${lead.email}`}
                          className="inline-flex items-center gap-1.5 hover:text-text-primary hover:underline"
                        >
                          <Mail className="h-3.5 w-3.5" aria-hidden="true" />
                          {lead.email}
                        </a>
                        {lead.phone && (
                          <a
                            href={`tel:${lead.phone}`}
                            className="inline-flex items-center gap-1.5 hover:text-text-primary hover:underline"
                          >
                            <Phone className="h-3.5 w-3.5" aria-hidden="true" />
                            {lead.phone}
                          </a>
                        )}
                        {lead.city && (
                          <span className="inline-flex items-center gap-1.5">
                            <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                            {lead.city}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="shrink-0 text-right">
                      <p className="text-small font-medium text-text-primary">
                        {formatRelative(lead.created_at)}
                      </p>
                      <p className="text-caption text-text-muted">
                        {formatDateTime(lead.created_at)}
                      </p>
                    </div>
                  </div>

                  {lead.message && (
                    <p className="mt-3 whitespace-pre-line rounded-xl border border-border-subtle bg-surface-raised px-4 py-3 text-body text-text-secondary">
                      {lead.message}
                    </p>
                  )}

                  <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-text-muted">
                    {lead.source_page && (
                      <span>
                        Submitted from{' '}
                        <span className="font-medium text-text-secondary">{lead.source_page}</span>
                      </span>
                    )}
                    {lead.handled_by && (
                      <span>
                        Worked by{' '}
                        <span className="font-medium text-text-secondary">{lead.handled_by}</span>
                        {lead.handled_at ? ` · ${formatDateTime(lead.handled_at)}` : ''}
                      </span>
                    )}
                  </div>

                  {lead.admin_note && !editing && (
                    <p className="mt-3 rounded-xl border border-status-good-border bg-status-good-bg px-4 py-2.5 text-small text-text-secondary">
                      <span className="font-semibold text-text-primary">Note: </span>
                      {lead.admin_note}
                    </p>
                  )}

                  {editing && (
                    <div className="mt-3">
                      <Textarea
                        label="Note"
                        hint="What happened when you contacted them."
                        rows={3}
                        maxLength={2000}
                        value={noteDraft}
                        onChange={(event) => setNoteDraft(event.target.value)}
                      />
                      <div className="mt-2 flex gap-2">
                        <Button
                          size="sm"
                          loading={busyId === lead.id}
                          onClick={() => void apply(lead, { admin_note: noteDraft })}
                        >
                          Save note
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setNoteFor(null)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}

                  {!editing && (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {next && (
                        <Button
                          size="sm"
                          variant="accent"
                          loading={busyId === lead.id}
                          onClick={() => void apply(lead, { status: next.to })}
                        >
                          {next.label}
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setNoteFor(lead.id)
                          setNoteDraft(lead.admin_note ?? '')
                        }}
                      >
                        {lead.admin_note ? 'Edit note' : 'Add note'}
                      </Button>
                      {lead.status !== 'new' && (
                        <Button
                          size="sm"
                          variant="ghost"
                          loading={busyId === lead.id}
                          onClick={() => void apply(lead, { status: 'new' })}
                        >
                          Reopen
                        </Button>
                      )}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </div>
  )
}
