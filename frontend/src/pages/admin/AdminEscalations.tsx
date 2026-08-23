import { Ambulance, ShieldAlert } from 'lucide-react'
import { useState } from 'react'

import { escalationsApi, hospitalApi } from '../../api/clinical'
import { EscalationTimeline } from '../../components/clinical'
import {
  Badge,
  Button,
  Card,
  Drawer,
  EmptyState,
  ErrorState,
  LoadingScreen,
  SegmentedControl,
  Table,
  TableWrap,
  TBody,
  TD,
  TEmptyRow,
  TH,
  THead,
  TR,
  Textarea,
  useToast,
} from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import { formatDateTime } from '../../lib/format'
import type { Escalation, HospitalBooking } from '../../types'

/**
 * The escalation and hospital SLA queue (§4.3, §4.9).
 *
 * Two queues on one screen because an operator works them as one job. Both are
 * ordered by deadline with the open work first — the server does that ordering,
 * so the table and the API agree about what is most urgent.
 *
 * `breached_sla` is read from the row, never recomputed here. The backend
 * stamps a breach when it observes one, which is what makes a breach from last
 * week still say so after somebody edits the SLA constants.
 */

function minutesLeft(dueAt: string): number {
  return Math.round((new Date(dueAt).getTime() - Date.now()) / 60_000)
}

function SlaCell({ dueAt, breached }: { dueAt: string; breached: boolean }) {
  if (breached) return <Badge tone="critical">SLA breached</Badge>
  const left = minutesLeft(dueAt)
  if (left <= 0) return <Badge tone="critical">Due now</Badge>
  const tone = left <= 15 ? 'watch' : 'neutral'
  return (
    <Badge tone={tone}>
      {left < 60 ? `${left} min left` : `${Math.round(left / 60)} h left`}
    </Badge>
  )
}

export function AdminEscalations() {
  const toast = useToast()
  const [filter, setFilter] = useState('open')
  const [selected, setSelected] = useState<Escalation | null>(null)
  const [note, setNote] = useState('')

  const escalations = useAsync<Escalation[]>(
    () => escalationsApi.list(filter === 'all' ? undefined : filter),
    [filter],
  )
  const bookings = useAsync<HospitalBooking[]>(() => hospitalApi.queue(), [])

  async function act(event: Escalation, action: 'acknowledge' | 'resolve') {
    try {
      const updated =
        action === 'acknowledge'
          ? await escalationsApi.acknowledge(event.id)
          : await escalationsApi.resolve(event.id, note)
      toast.notify(action === 'acknowledge' ? 'Picked up.' : 'Escalation closed.', 'success')
      setSelected(updated)
      setNote('')
      await escalations.reload({ quiet: true })
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not update.', 'error')
    }
  }

  async function advance(booking: HospitalBooking) {
    const next = booking.status === 'requested' ? 'coordinating' : 'confirmed'
    try {
      await hospitalApi.update(booking.id, { status: next })
      toast.notify(`Marked ${next}.`, 'success')
      await bookings.reload({ quiet: true })
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not update.', 'error')
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-h1 font-semibold text-text-primary">Escalations</h1>
        <p className="text-small text-text-secondary">
          Anything urgent, with the clock running and every contact attempt recorded.
        </p>
      </header>

      <SegmentedControl
        legend="Filter escalations"
        hideLegend
        value={filter}
        onChange={setFilter}
        options={[
          { value: 'open', label: 'Open' },
          { value: 'acknowledged', label: 'Picked up' },
          { value: 'resolved', label: 'Resolved' },
          { value: 'all', label: 'All' },
        ]}
      />

      {escalations.loading && <LoadingScreen label="Loading escalations" />}
      {escalations.error && (
        <ErrorState message={escalations.error} onRetry={() => escalations.reload()} />
      )}

      {escalations.data?.length === 0 && (
        <EmptyState
          icon={<ShieldAlert aria-hidden />}
          title="Nothing escalated"
          description="Escalations appear here the moment a home monitor, a lab result or a family raises one."
        />
      )}

      {escalations.data && escalations.data.length > 0 && (
        <Card flush>
          <TableWrap>
            <Table>
              <THead>
                <TR>
                  <TH>Patient</TH>
                  <TH>What happened</TH>
                  <TH>Opened</TH>
                  <TH>SLA</TH>
                  <TH>Status</TH>
                  <TH>{''}</TH>
                </TR>
              </THead>
              <TBody>
                {escalations.data.map((event) => (
                  <TR key={event.id}>
                    <TD>{event.patient_name}</TD>
                    <TD>{event.summary}</TD>
                    <TD>{formatDateTime(event.opened_at)}</TD>
                    <TD>
                      <SlaCell dueAt={event.sla_due_at} breached={event.breached_sla} />
                    </TD>
                    <TD>
                      <Badge tone={event.status === 'resolved' ? 'good' : 'info'}>
                        {event.status}
                      </Badge>
                    </TD>
                    <TD>
                      <Button variant="ghost" size="sm" onClick={() => setSelected(event)}>
                        Open timeline
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </TableWrap>
        </Card>
      )}

      <section className="space-y-3">
        <h2 className="text-h2 font-semibold text-text-primary">Hospital coordination</h2>
        {bookings.loading && <LoadingScreen label="Loading hospital queue" />}
        {bookings.error && <ErrorState message={bookings.error} onRetry={() => bookings.reload()} />}
        {bookings.data && (
          <Card flush>
            <TableWrap>
              <Table>
                <THead>
                  <TR>
                    <TH>Patient</TH>
                    <TH>Hospital</TH>
                    <TH>Reason</TH>
                    <TH>SLA</TH>
                    <TH>Status</TH>
                    <TH>{''}</TH>
                  </TR>
                </THead>
                <TBody>
                  {bookings.data.length === 0 && <TEmptyRow colSpan={6}>Nothing waiting.</TEmptyRow>}
                  {bookings.data.map((booking) => (
                    <TR key={booking.id}>
                      <TD>{booking.patient_name}</TD>
                      <TD>
                        <span className="flex items-center gap-1.5">
                          {booking.ambulance_required && (
                            <Ambulance size={14} aria-label="Ambulance requested" className="text-status-critical" />
                          )}
                          {booking.hospital_name}
                        </span>
                      </TD>
                      <TD className="max-w-xs truncate">{booking.reason}</TD>
                      <TD>
                        <SlaCell dueAt={booking.sla_due_at} breached={booking.breached_sla} />
                      </TD>
                      <TD>
                        <Badge tone={booking.status === 'confirmed' ? 'good' : 'info'}>
                          {booking.status}
                        </Badge>
                      </TD>
                      <TD>
                        {booking.status !== 'confirmed' && booking.status !== 'admitted' && (
                          <Button variant="ghost" size="sm" onClick={() => advance(booking)}>
                            {booking.status === 'requested' ? 'Start coordinating' : 'Confirm'}
                          </Button>
                        )}
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </TableWrap>
          </Card>
        )}
      </section>

      <Drawer
        open={selected !== null}
        onClose={() => setSelected(null)}
        title={selected?.summary ?? 'Escalation'}
      >
        {selected && (
          <div className="space-y-5">
            <div>
              <p className="text-small text-text-secondary">{selected.detail}</p>
              <p className="mt-1 text-caption text-text-muted">
                {selected.patient_name} · opened {formatDateTime(selected.opened_at)} · SLA{' '}
                {selected.sla_minutes} minutes
              </p>
            </div>

            {selected.ladder.length > 0 && (
              <div className="rounded-md bg-surface-sunken p-3">
                <p className="text-caption font-medium uppercase tracking-wide text-text-muted">
                  Escalation ladder
                </p>
                <ol className="mt-1 space-y-0.5 text-caption text-text-secondary">
                  {selected.ladder.map((rung, index) => (
                    <li key={rung}>
                      {index + 1}. {rung}
                    </li>
                  ))}
                </ol>
              </div>
            )}

            <div>
              <h3 className="mb-3 text-small font-semibold text-text-primary">
                What was done, and when
              </h3>
              <EscalationTimeline steps={selected.steps} />
            </div>

            {selected.status !== 'resolved' && (
              <div className="space-y-2 border-t border-border-subtle pt-4">
                <Textarea
                  label="Resolution note"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  rows={3}
                />
                <div className="flex gap-2">
                  {selected.status === 'open' && (
                    <Button variant="subtle" onClick={() => act(selected, 'acknowledge')}>
                      Pick this up
                    </Button>
                  )}
                  <Button onClick={() => act(selected, 'resolve')}>Resolve</Button>
                </div>
              </div>
            )}

            {selected.resolution_note && (
              <p className="border-t border-border-subtle pt-4 text-small text-text-secondary">
                {selected.resolution_note}
              </p>
            )}
          </div>
        )}
      </Drawer>
    </div>
  )
}
