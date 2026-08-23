import { ShieldCheck } from 'lucide-react'
import { useState } from 'react'

import { privacyApi } from '../../api/trust'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingScreen,
  Modal,
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
import type { AuditEntry, ErasureRequest } from '../../types'

/**
 * Erasure requests and the audit log (§4.14).
 *
 * Erasure is executed here rather than by the family who asked for it, because
 * it is irreversible and it destroys a named person's health record. The dialog
 * says so in those words, and the outcome — what was actually destroyed, dataset
 * by dataset — is stored on the request afterwards, so the promise made on the
 * family's privacy page can be checked rather than trusted.
 */

const STATUS: Record<ErasureRequest['status'], { label: string; tone: 'watch' | 'good' | 'neutral' }> = {
  requested: { label: 'Waiting', tone: 'watch' },
  executed: { label: 'Erased', tone: 'good' },
  declined: { label: 'Declined', tone: 'neutral' },
}

export function AdminPrivacy() {
  const toast = useToast()
  const [acting, setActing] = useState<{ request: ErasureRequest; mode: 'execute' | 'decline' } | null>(
    null,
  )
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const requests = useAsync<ErasureRequest[]>(() => privacyApi.queue(), [])
  const audit = useAsync<AuditEntry[]>(() => privacyApi.audit(), [])

  async function submit() {
    if (!acting) return
    setBusy(true)
    try {
      if (acting.mode === 'execute') {
        const result = await privacyApi.execute(acting.request.id, note.trim() || null)
        toast.notify(`${result.patient_name}'s record has been erased.`, 'success')
      } else {
        await privacyApi.decline(acting.request.id, note.trim())
        toast.notify('The request was declined.', 'success')
      }
      setActing(null)
      setNote('')
      await Promise.all([requests.reload({ quiet: true }), audit.reload({ quiet: true })])
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not do that.', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (requests.loading) return <LoadingScreen label="Loading privacy requests" />
  if (requests.error)
    return <ErrorState message={requests.error} onRetry={() => requests.reload()} />

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-h1 font-semibold text-text-primary">Privacy</h1>
        <p className="text-small text-text-secondary">
          Erasure requests from families, and the record of who has opened whose data.
        </p>
      </header>

      <Card title="Erasure requests">
        {requests.data?.length === 0 ? (
          <EmptyState
            icon={<ShieldCheck aria-hidden />}
            title="No requests"
            description="Families who ask for a record to be destroyed appear here."
          />
        ) : (
          <TableWrap>
            <Table>
              <THead>
                <TR>
                  <TH>Requested</TH>
                  <TH>Patient</TH>
                  <TH>By</TH>
                  <TH>Reason</TH>
                  <TH>Status</TH>
                  <TH>Action</TH>
                </TR>
              </THead>
              <TBody>
                {requests.data?.map((request) => (
                  <TR key={request.id}>
                    <TD className="tnum whitespace-nowrap">{formatDateTime(request.created_at)}</TD>
                    <TD className="font-medium text-text-primary">{request.patient_name}</TD>
                    <TD>{request.requested_by_name}</TD>
                    <TD className="max-w-xs text-text-secondary">{request.reason ?? '—'}</TD>
                    <TD>
                      <Badge tone={STATUS[request.status].tone}>{STATUS[request.status].label}</Badge>
                      {request.outcome && (
                        <p className="mt-1 whitespace-pre-line text-caption text-text-muted">
                          {request.outcome}
                        </p>
                      )}
                    </TD>
                    <TD>
                      {request.status === 'requested' ? (
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() => setActing({ request, mode: 'execute' })}
                          >
                            Erase
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setActing({ request, mode: 'decline' })}
                          >
                            Decline
                          </Button>
                        </div>
                      ) : (
                        <span className="text-caption text-text-muted">
                          {request.decided_by_name}
                        </span>
                      )}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </TableWrap>
        )}
      </Card>

      <Card title="Audit log" description="Append-only. Nothing here can be edited or removed.">
        {audit.loading && <LoadingScreen label="Loading" />}
        {audit.error && <ErrorState message={audit.error} onRetry={() => audit.reload()} />}
        {audit.data && (
          <TableWrap>
            <Table>
              <THead>
                <TR>
                  <TH>When</TH>
                  <TH>Who</TH>
                  <TH>Action</TH>
                  <TH>Detail</TH>
                </TR>
              </THead>
              <TBody>
                {audit.data.length === 0 && <TEmptyRow colSpan={4}>Nothing recorded yet.</TEmptyRow>}
                {audit.data.map((entry) => (
                  <TR key={entry.id}>
                    <TD className="tnum whitespace-nowrap">{formatDateTime(entry.at)}</TD>
                    <TD>
                      {entry.actor_label}
                      {entry.actor_role && (
                        <span className="ml-1 text-caption text-text-muted">
                          ({entry.actor_role})
                        </span>
                      )}
                    </TD>
                    <TD className="whitespace-nowrap text-text-secondary">
                      {entry.action.replace(/_/g, ' ')}
                    </TD>
                    <TD className="text-text-secondary">{entry.detail ?? '—'}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </TableWrap>
        )}
      </Card>

      <Modal
        open={acting !== null}
        onClose={() => setActing(null)}
        title={acting?.mode === 'execute' ? 'Erase this record' : 'Decline this request'}
      >
        <div className="space-y-4">
          {acting?.mode === 'execute' ? (
            <p className="text-small text-text-secondary">
              This permanently destroys {acting.request.patient_name}&rsquo;s health record. Issued
              invoices and the audit log are kept — everything else goes. It cannot be undone.
            </p>
          ) : (
            <p className="text-small text-text-secondary">
              The family will be told the request was declined. Say why.
            </p>
          )}
          <Textarea
            label={acting?.mode === 'execute' ? 'Note (optional)' : 'Reason'}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={3}
            required={acting?.mode === 'decline'}
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setActing(null)}>
              Cancel
            </Button>
            <Button
              variant={acting?.mode === 'execute' ? 'danger' : 'primary'}
              onClick={submit}
              disabled={busy || (acting?.mode === 'decline' && !note.trim())}
            >
              {busy ? 'Working…' : acting?.mode === 'execute' ? 'Erase the record' : 'Decline'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
