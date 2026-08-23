import { Plus, Trash2, UsersRound } from 'lucide-react'
import { useState } from 'react'

import { patientsApi } from '../../api/patients'
import { careCircleApi } from '../../api/trust'
import {
  Badge,
  Button,
  Card,
  Checkbox,
  EmptyState,
  ErrorState,
  Input,
  LoadingScreen,
  Modal,
  Select,
  Switch,
  useToast,
} from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import type { CareCircleMember, Patient } from '../../types'

/**
 * The people around one patient (§4.13).
 *
 * The screen is written for the member who is **not** on the account: the
 * neighbour two doors down with the spare key. She has no login and never will,
 * and she is frequently the most useful person to reach at 2am — so "no
 * DoorDoctor account" is stated plainly rather than shown as something missing.
 *
 * The alert checkbox is disabled until there is a phone number or an email
 * address, because the server refuses that combination and a control that
 * always errors is worse than a control that explains itself.
 */

const ROLES = [
  { value: 'contributor', label: 'Can see everything and add notes' },
  { value: 'viewer', label: 'Can see readings and alerts' },
  { value: 'emergency_contact', label: 'Emergency contact' },
]

const RELATIONSHIPS = [
  'Son',
  'Daughter',
  'Spouse',
  'Sibling',
  'Grandchild',
  'Neighbour',
  'Family friend',
  'Other',
]

const EMPTY_FORM = {
  name: '',
  relationship_label: 'Son',
  phone: '',
  email: '',
  role: 'contributor',
  receives_alerts: false,
  receives_reports: false,
  note: '',
}

export function FamilyCareCircle() {
  const toast = useToast()
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)

  const patients = useAsync<Patient[]>(() => patientsApi.list(), [])
  const patient = patients.data?.[0] ?? null
  const circle = useAsync<CareCircleMember[]>(
    async () => (patient ? careCircleApi.list(patient.id) : []),
    [patient?.id],
  )

  const reachable = Boolean(form.phone.trim() || form.email.trim())

  async function submit() {
    if (!patient) return
    setBusy(true)
    try {
      await careCircleApi.add(patient.id, {
        ...form,
        phone: form.phone.trim() || null,
        email: form.email.trim() || null,
        note: form.note.trim() || null,
      })
      toast.notify(`${form.name} was added to the care circle.`, 'success')
      setAdding(false)
      setForm(EMPTY_FORM)
      await circle.reload({ quiet: true })
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not add them.', 'error')
    } finally {
      setBusy(false)
    }
  }

  async function toggleAlerts(member: CareCircleMember, value: boolean) {
    try {
      await careCircleApi.update(member.id, { receives_alerts: value })
      await circle.reload({ quiet: true })
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not save that.', 'error')
    }
  }

  async function remove(member: CareCircleMember) {
    try {
      await careCircleApi.remove(member.id)
      toast.notify(`${member.name} was removed.`, 'success')
      await circle.reload({ quiet: true })
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not remove them.', 'error')
    }
  }

  if (patients.loading) return <LoadingScreen label="Loading the care circle" />
  if (patients.error)
    return <ErrorState message={patients.error} onRetry={() => patients.reload()} />
  if (!patient) {
    return (
      <EmptyState
        icon={<UsersRound aria-hidden />}
        title="No patient linked yet"
        description="Ask DoorDoctor to link a patient to your account."
      />
    )
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-h1 font-semibold text-text-primary">Care circle</h1>
          <p className="max-w-2xl text-small text-text-secondary">
            Everyone who should know how {patient.name.split(' ')[0]} is. People without a
            DoorDoctor account can still be sent alerts — the neighbour who can be there in ten
            minutes matters more at 2am than anyone abroad.
          </p>
        </div>
        <Button onClick={() => setAdding(true)}>
          <Plus aria-hidden className="mr-1 h-4 w-4" />
          Add someone
        </Button>
      </header>

      {circle.loading && <LoadingScreen label="Loading" />}
      {circle.error && <ErrorState message={circle.error} onRetry={() => circle.reload()} />}

      <div className="grid gap-4 sm:grid-cols-2">
        {circle.data?.map((member) => (
          <Card key={member.id}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-medium text-text-primary">{member.name}</p>
                <p className="text-small text-text-secondary">{member.relationship_label}</p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
                {member.is_primary && <Badge tone="info">Primary contact</Badge>}
                {!member.has_login && <Badge tone="neutral">No account</Badge>}
              </div>
            </div>

            <dl className="mt-3 space-y-1 text-small text-text-secondary">
              {member.phone && (
                <div className="flex gap-2">
                  <dt className="text-text-muted">Phone</dt>
                  <dd className="tnum">{member.phone}</dd>
                </div>
              )}
              {member.email && (
                <div className="flex min-w-0 gap-2">
                  <dt className="text-text-muted">Email</dt>
                  <dd className="truncate">{member.email}</dd>
                </div>
              )}
            </dl>

            {member.note && <p className="mt-2 text-small text-text-secondary">{member.note}</p>}

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border-subtle pt-3">
              <Switch
                checked={member.receives_alerts}
                onChange={(value) => toggleAlerts(member, value)}
                label="Send alerts"
                disabled={member.is_primary}
                hint={member.is_primary ? 'The primary contact is always told.' : undefined}
              />
              {!member.is_primary && (
                <Button variant="ghost" size="sm" onClick={() => remove(member)}>
                  <Trash2 aria-hidden className="mr-1 h-4 w-4" />
                  Remove
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>

      <Modal open={adding} onClose={() => setAdding(false)} title="Add someone to the care circle">
        <div className="space-y-4">
          <Input
            label="Name"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            required
          />
          <Select
            label="How are they related?"
            value={form.relationship_label}
            onChange={(event) => setForm({ ...form, relationship_label: event.target.value })}
          >
            {RELATIONSHIPS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Phone"
              hint="Used for SMS and WhatsApp."
              value={form.phone}
              onChange={(event) => setForm({ ...form, phone: event.target.value })}
            />
            <Input
              label="Email"
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
            />
          </div>
          <Select
            label="What can they see?"
            value={form.role}
            onChange={(event) => setForm({ ...form, role: event.target.value })}
          >
            {ROLES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
          <Checkbox
            checked={form.receives_alerts}
            onChange={(event) => setForm({ ...form, receives_alerts: event.target.checked })}
            disabled={!reachable}
            label="Send them alerts"
            hint={
              reachable
                ? 'They will be messaged when something needs attention.'
                : 'Add a phone number or an email address first.'
            }
          />
          <Input
            label="Anything the care team should know?"
            value={form.note}
            onChange={(event) => setForm({ ...form, note: event.target.value })}
            placeholder="Has the spare key"
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setAdding(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={busy || !form.name.trim()}>
              {busy ? 'Adding…' : 'Add to circle'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
