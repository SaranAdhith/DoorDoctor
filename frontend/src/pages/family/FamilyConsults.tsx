import { Video } from 'lucide-react'
import { useState } from 'react'

import { consultsApi } from '../../api/clinical'
import { patientsApi } from '../../api/patients'
import { EmergencyBlock } from '../../components/clinical'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Input,
  LoadingScreen,
  Modal,
  Textarea,
  useToast,
} from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import { formatDateTime, localInputToApi, toLocalInputValue } from '../../lib/format'
import type { Consult, ConsultAllowance, Patient } from '../../types'

/**
 * Doctor video consults, for the family (§4.6).
 *
 * This is the first screen in the product where an entitlement actually says
 * no, so the allowance is stated **before** the booking form rather than
 * discovered in an error. When the server does refuse, it refuses with a 409
 * and a sentence, and that sentence is what the toast shows — a client-side
 * guess at the reason would be a second implementation of the rule.
 */

const STATUS_TONES = {
  scheduled: 'info',
  completed: 'good',
  cancelled: 'neutral',
  no_show: 'watch',
} as const

const STATUS_LABELS = {
  scheduled: 'Scheduled',
  completed: 'Completed',
  cancelled: 'Cancelled',
  no_show: 'Missed',
} as const

function defaultSlot(): string {
  const when = new Date()
  when.setDate(when.getDate() + 2)
  when.setHours(11, 0, 0, 0)
  return toLocalInputValue(when)
}

export function FamilyConsults() {
  const toast = useToast()
  const [booking, setBooking] = useState(false)
  const [slot, setSlot] = useState(defaultSlot)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  const patients = useAsync<Patient[]>(() => patientsApi.list(), [])
  const patientId = patients.data?.[0]?.id ?? null

  const allowance = useAsync<ConsultAllowance | null>(
    async () => (patientId ? consultsApi.allowance(patientId) : null),
    [patientId],
  )
  const consults = useAsync<Consult[]>(
    async () => (patientId ? consultsApi.list(patientId) : []),
    [patientId],
  )

  async function refresh() {
    await Promise.all([allowance.reload({ quiet: true }), consults.reload({ quiet: true })])
  }

  async function submit() {
    if (!patientId) return
    setBusy(true)
    try {
      await consultsApi.book(patientId, localInputToApi(slot), reason)
      toast.notify('Consult booked. You will get the joining details by SMS.', 'success')
      setBooking(false)
      setReason('')
      await refresh()
    } catch (error) {
      // The server's sentence, not a guess at it — it knows the allowance.
      toast.notify(error instanceof Error ? error.message : 'Could not book.', 'error')
    } finally {
      setBusy(false)
    }
  }

  async function cancel(consult: Consult) {
    try {
      const updated = await consultsApi.cancel(consult.id)
      toast.notify(
        updated.quota_released
          ? 'Consult cancelled, and the consult has been returned to your plan.'
          : 'Consult cancelled. It was too close to the appointment to return it to your plan.',
        'success',
      )
      await refresh()
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not cancel.', 'error')
    }
  }

  if (patients.loading) return <LoadingScreen label="Loading consults" />
  if (patients.error) return <ErrorState message={patients.error} onRetry={() => patients.reload()} />
  if (!patientId) {
    return (
      <EmptyState
        icon={<Video aria-hidden />}
        title="No patient linked yet"
        description="Ask DoorDoctor to link a patient to your account."
      />
    )
  }

  const left = allowance.data
  const none = left ? !left.unlimited && (left.remaining ?? 0) <= 0 : false

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-h1 font-semibold text-text-primary">Doctor consults</h1>
          <p className="text-small text-text-secondary">
            A video call with a doctor, arranged around your parent&rsquo;s day.
          </p>
        </div>
        <Button onClick={() => setBooking(true)} disabled={none}>
          Book a consult
        </Button>
      </header>

      <EmergencyBlock compact />

      {left && (
        <Card>
          <p className="text-body text-text-primary">
            {left.unlimited ? (
              'Your plan includes unlimited doctor consults.'
            ) : (
              <>
                <span className="tnum font-semibold">{left.remaining}</span> of{' '}
                <span className="tnum">{left.included}</span> consults left this month.
              </>
            )}
          </p>
          <p className="mt-1 text-caption text-text-muted">
            Each consult runs about {left.duration_minutes} minutes. Cancel more than{' '}
            {left.cancellation_hours} hours ahead and it goes back on your plan.
          </p>
          {none && (
            <p className="mt-2 text-caption text-status-watch">
              You have used this month&rsquo;s consults. Upgrading your plan adds more.
            </p>
          )}
        </Card>
      )}

      {consults.loading && <LoadingScreen label="Loading consults" />}
      {consults.error && <ErrorState message={consults.error} onRetry={() => consults.reload()} />}

      {consults.data?.length === 0 && (
        <EmptyState
          icon={<Video aria-hidden />}
          title="No consults yet"
          description="Book one when you would like a doctor's opinion between nurse visits."
        />
      )}

      <div className="space-y-3">
        {consults.data?.map((consult) => (
          <Card
            key={consult.id}
            title={formatDateTime(consult.scheduled_for)}
            description={`${consult.doctor_name} · ${consult.duration_minutes} minutes`}
            action={<Badge tone={STATUS_TONES[consult.status]}>{STATUS_LABELS[consult.status]}</Badge>}
          >
            {consult.reason && <p className="text-small text-text-secondary">{consult.reason}</p>}
            {consult.summary && (
              <p className="mt-2 text-small text-text-primary">{consult.summary}</p>
            )}
            {consult.status === 'scheduled' && (
              <Button variant="ghost" size="sm" className="mt-3" onClick={() => cancel(consult)}>
                Cancel this consult
              </Button>
            )}
          </Card>
        ))}
      </div>

      <Modal open={booking} onClose={() => setBooking(false)} title="Book a doctor consult">
        <div className="space-y-4">
          <Input
            type="datetime-local"
            label="When would suit?"
            value={slot}
            onChange={(event) => setSlot(event.target.value)}
          />
          <Textarea
            label="What would you like to discuss?"
            hint="Optional, but it helps the doctor prepare."
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={3}
          />
          <div className="flex gap-2">
            <Button onClick={submit} disabled={busy}>
              {busy ? 'Booking…' : 'Book consult'}
            </Button>
            <Button variant="ghost" onClick={() => setBooking(false)}>
              Cancel
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
