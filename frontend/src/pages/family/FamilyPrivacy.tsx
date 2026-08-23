import { Download, Eye, ShieldCheck, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { patientsApi } from '../../api/patients'
import { privacyApi } from '../../api/trust'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingScreen,
  Modal,
  Switch,
  Table,
  TableWrap,
  TBody,
  TD,
  TEmptyRow,
  TH,
  THead,
  Textarea,
  TR,
  useToast,
} from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import { formatDateTime } from '../../lib/format'
import type { Patient, PrivacyOverview } from '../../types'

/**
 * Privacy and data (§4.14).
 *
 * Three promises on one page, and each is written so it can be checked:
 *
 * * **What is held** — counted from the rows themselves, not described.
 * * **Who has looked** — the audit trail, so "who opened my mother's record"
 *   has an answer rather than an assurance.
 * * **What erasure does** — and, said just as plainly, what it does not. The
 *   retained categories carry their reasons, because "we delete everything"
 *   followed by keeping the invoices is the kind of promise this whole phase
 *   exists to stop.
 *
 * The export is fetched and saved as a file the browser downloads; it is the
 * actual record, not a summary of it.
 */
export function FamilyPrivacy() {
  const toast = useToast()
  const [erasing, setErasing] = useState(false)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  const patients = useAsync<Patient[]>(() => patientsApi.list(), [])
  const patient = patients.data?.[0] ?? null
  const overview = useAsync<PrivacyOverview | null>(
    async () => (patient ? privacyApi.overview(patient.id) : null),
    [patient?.id],
  )

  async function setConsent(kind: string, granted: boolean) {
    if (!patient) return
    try {
      await privacyApi.setConsent(kind, granted, patient.id)
      await overview.reload({ quiet: true })
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not save that.', 'error')
    }
  }

  async function download() {
    if (!patient) return
    try {
      const payload = await privacyApi.exportRecord(patient.id)
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `doordoctor-record-${patient.id}.json`
      link.click()
      URL.revokeObjectURL(url)
      toast.notify('Your copy has been downloaded.', 'success')
      await overview.reload({ quiet: true })
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not export.', 'error')
    }
  }

  async function requestErasure() {
    if (!patient) return
    setBusy(true)
    try {
      await privacyApi.requestErasure(patient.id, reason.trim() || null)
      toast.notify('Your request has been sent to the DoorDoctor team.', 'success')
      setErasing(false)
      setReason('')
      await overview.reload({ quiet: true })
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not send that.', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (patients.loading) return <LoadingScreen label="Loading your data" />
  if (patients.error)
    return <ErrorState message={patients.error} onRetry={() => patients.reload()} />
  if (!patient) {
    return (
      <EmptyState
        icon={<ShieldCheck aria-hidden />}
        title="No patient linked yet"
        description="Ask DoorDoctor to link a patient to your account."
      />
    )
  }
  if (overview.loading) return <LoadingScreen label="Loading your data" />
  if (overview.error)
    return <ErrorState message={overview.error} onRetry={() => overview.reload()} />
  const data = overview.data
  if (!data) return null

  const pending = data.erasure_request?.status === 'requested'

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-h1 font-semibold text-text-primary">Privacy and data</h1>
        <p className="max-w-2xl text-small text-text-secondary">
          Everything DoorDoctor holds about {data.patient_name}, who has looked at it, and how to
          get a copy or have it destroyed.
        </p>
      </header>

      <Card
        title="What you have agreed to"
        description={`Policy version ${data.policy_version}. You can change the optional ones at any time.`}
      >
        <ul className="space-y-4">
          {data.consents.map((consent) => (
            <li key={consent.kind} className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 max-w-xl">
                <p className="font-medium text-text-primary">
                  {consent.label}
                  {consent.required && (
                    <Badge tone="neutral" className="ml-2">
                      Required
                    </Badge>
                  )}
                  {consent.needs_review && (
                    <Badge tone="watch" className="ml-2">
                      Policy has changed
                    </Badge>
                  )}
                </p>
                <p className="text-small text-text-secondary">{consent.blurb}</p>
                {consent.decided_at && (
                  <p className="mt-1 text-caption text-text-muted">
                    {consent.granted ? 'Agreed' : 'Withdrawn'} by {consent.decided_by_name} on{' '}
                    {formatDateTime(consent.decided_at)}
                  </p>
                )}
              </div>
              <Switch
                checked={consent.granted}
                onChange={(value) => setConsent(consent.kind, value)}
                label={consent.granted ? 'On' : 'Off'}
                disabled={consent.required && consent.granted}
                hint={
                  consent.required && consent.granted
                    ? 'This is what the service is.'
                    : undefined
                }
              />
            </li>
          ))}
        </ul>
      </Card>

      <Card
        title="What we hold"
        description="Counted from the records themselves, not from a description of them."
      >
        <ul className="grid gap-2 sm:grid-cols-2">
          {data.holdings.map((holding) => (
            <li
              key={holding.key}
              className="flex items-center justify-between rounded-lg border border-border-subtle px-3 py-2"
            >
              <span className="text-small text-text-secondary">{holding.label}</span>
              <span className="tnum font-medium text-text-primary">{holding.count}</span>
            </li>
          ))}
        </ul>
        <div className="mt-4">
          <Button variant="subtle" onClick={download}>
            <Download aria-hidden className="mr-1 h-4 w-4" />
            Download a copy
          </Button>
        </div>
      </Card>

      <Card
        title="Who has looked at this record"
        description={`Kept for ${Math.round(data.audit_retention_days / 365)} years. Your own visits to these pages are not logged.`}
      >
        <TableWrap>
          <Table>
            <THead>
              <TR>
                <TH>When</TH>
                <TH>Who</TH>
                <TH>What</TH>
              </TR>
            </THead>
            <TBody>
              {data.audit_trail.length === 0 && (
                <TEmptyRow colSpan={3}>Nobody outside your family has opened this record.</TEmptyRow>
              )}
              {data.audit_trail.map((entry) => (
                <TR key={entry.id}>
                  <TD className="tnum whitespace-nowrap">{formatDateTime(entry.at)}</TD>
                  <TD>
                    {entry.actor_label}
                    {entry.actor_role && (
                      <span className="ml-1 text-caption text-text-muted">({entry.actor_role})</span>
                    )}
                  </TD>
                  <TD className="text-text-secondary">{entry.detail ?? entry.action}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </TableWrap>
      </Card>

      <Card
        title="Have this record destroyed"
        description="You ask, and a member of the DoorDoctor team carries it out. It cannot be undone."
      >
        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <h3 className="text-small font-semibold text-text-primary">What is destroyed</h3>
            <ul className="mt-2 space-y-1 text-small text-text-secondary">
              {data.erasure_destroys.map((line) => (
                <li key={line} className="flex gap-2">
                  <Trash2 aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
                  {line}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="text-small font-semibold text-text-primary">What is kept, and why</h3>
            <ul className="mt-2 space-y-2 text-small text-text-secondary">
              {data.erasure_retains.map((entry) => (
                <li key={entry.label} className="flex gap-2">
                  <Eye aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
                  <span>
                    <span className="font-medium text-text-primary">{entry.label}.</span>{' '}
                    {entry.reason}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-5 border-t border-border-subtle pt-4">
          {pending ? (
            <p className="text-small text-text-secondary">
              A request was sent on{' '}
              {formatDateTime(data.erasure_request?.created_at ?? '')} and is waiting with the
              DoorDoctor team.
            </p>
          ) : data.erasure_request?.status === 'executed' ? (
            <p className="text-small text-text-secondary">This record has been erased.</p>
          ) : (
            <Button variant="danger" onClick={() => setErasing(true)}>
              Request erasure
            </Button>
          )}
        </div>
      </Card>

      <Modal open={erasing} onClose={() => setErasing(false)} title="Request erasure">
        <div className="space-y-4">
          <p className="text-small text-text-secondary">
            This asks DoorDoctor to destroy {data.patient_name}&rsquo;s health record. A member of
            the team will carry it out, and it cannot be undone.
          </p>
          <Textarea
            label="Why? (optional)"
            hint="It helps the team understand, and it is kept with the request."
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={3}
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setErasing(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={requestErasure} disabled={busy}>
              {busy ? 'Sending…' : 'Send the request'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
