import { FlaskConical } from 'lucide-react'
import { useState } from 'react'

import { labsApi, tasksApi } from '../../api/clinical'
import { LabResultTable } from '../../components/clinical'
import {
  Badge,
  Button,
  Card,
  Drawer,
  EmptyState,
  ErrorState,
  Input,
  LoadingScreen,
  Table,
  TableWrap,
  TBody,
  TD,
  TEmptyRow,
  TH,
  THead,
  TR,
  useToast,
} from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import { formatDate, formatRelative } from '../../lib/format'
import type { FollowUpTask, LabOrder, LabPanel } from '../../types'

/**
 * Lab operations: orders waiting on the laboratory, and the follow-up tasks an
 * abnormal result opened (§4.2).
 *
 * The result form is generated from the panel served by the API, so a panel
 * added to `core/clinical.py` appears here with no frontend change — and, more
 * importantly, this screen can never offer a field the server would reject.
 */

export function AdminLabs() {
  const toast = useToast()
  const [entering, setEntering] = useState<LabOrder | null>(null)
  const [values, setValues] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)

  const panels = useAsync<LabPanel[]>(() => labsApi.panels(), [])
  const awaiting = useAsync<LabOrder[]>(() => labsApi.awaitingResults(), [])
  const tasks = useAsync<FollowUpTask[]>(() => tasksApi.list('open'), [])

  const panel = panels.data?.find((candidate) => candidate.code === entering?.panel_code) ?? null

  function open(order: LabOrder) {
    setEntering(order)
    setValues({})
  }

  async function submit() {
    if (!entering) return
    const numeric: Record<string, number> = {}
    for (const [code, raw] of Object.entries(values)) {
      if (raw.trim() !== '') numeric[code] = Number(raw)
    }
    if (Object.keys(numeric).length === 0) {
      toast.notify('Enter at least one result.', 'warning')
      return
    }

    setBusy(true)
    try {
      const updated = await labsApi.recordResults(entering.id, numeric)
      toast.notify(
        updated.abnormal_count > 0
          ? `Recorded. ${updated.abnormal_count} result(s) outside range — an alert and a follow-up task were raised.`
          : 'Recorded. All results in range.',
        updated.abnormal_count > 0 ? 'warning' : 'success',
      )
      setEntering(null)
      await Promise.all([awaiting.reload({ quiet: true }), tasks.reload({ quiet: true })])
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not record results.', 'error')
    } finally {
      setBusy(false)
    }
  }

  async function closeTask(task: FollowUpTask) {
    try {
      await tasksApi.complete(task.id, 'Followed up with the family.')
      toast.notify('Task closed.', 'success')
      await tasks.reload({ quiet: true })
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not close the task.', 'error')
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-h1 font-semibold text-text-primary">Labs</h1>
        <p className="text-small text-text-secondary">
          Orders waiting on the laboratory, and the follow-ups an abnormal result opened.
        </p>
      </header>

      {awaiting.loading && <LoadingScreen label="Loading lab orders" />}
      {awaiting.error && <ErrorState message={awaiting.error} onRetry={() => awaiting.reload()} />}

      {awaiting.data?.length === 0 && (
        <EmptyState
          icon={<FlaskConical aria-hidden />}
          title="Nothing waiting"
          description="Every ordered panel has results recorded against it."
        />
      )}

      {awaiting.data && awaiting.data.length > 0 && (
        <Card title="Awaiting results" flush>
          <TableWrap>
            <Table>
              <THead>
                <TR>
                  <TH>Patient</TH>
                  <TH>Panel</TH>
                  <TH>Ordered</TH>
                  <TH>Status</TH>
                  <TH>{''}</TH>
                </TR>
              </THead>
              <TBody>
                {awaiting.data.map((order) => (
                  <TR key={order.id}>
                    <TD>{order.patient_name}</TD>
                    <TD>{order.panel_name}</TD>
                    <TD>{formatDate(order.ordered_at)}</TD>
                    <TD>
                      <Badge tone="info">
                        {order.status === 'ordered' ? 'Awaiting collection' : 'With the lab'}
                      </Badge>
                    </TD>
                    <TD>
                      <Button variant="ghost" size="sm" onClick={() => open(order)}>
                        Record results
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </TableWrap>
        </Card>
      )}

      <Card title="Open follow-ups" description="Raised automatically by a clinical finding." flush>
        {tasks.loading && <LoadingScreen label="Loading tasks" />}
        {tasks.error && <ErrorState message={tasks.error} onRetry={() => tasks.reload()} />}
        {tasks.data && (
          <TableWrap>
            <Table>
              <THead>
                <TR>
                  <TH>Patient</TH>
                  <TH>What needs doing</TH>
                  <TH>Due</TH>
                  <TH>{''}</TH>
                </TR>
              </THead>
              <TBody>
                {tasks.data.length === 0 && <TEmptyRow colSpan={4}>Nothing open.</TEmptyRow>}
                {tasks.data.map((task) => (
                  <TR key={task.id}>
                    <TD>{task.patient_name}</TD>
                    <TD>
                      <p>{task.title}</p>
                      {task.detail && (
                        <p className="text-caption text-text-muted">{task.detail}</p>
                      )}
                    </TD>
                    <TD>
                      {task.is_overdue ? (
                        <Badge tone="critical">Overdue</Badge>
                      ) : (
                        <span className="text-text-muted">{formatRelative(task.due_at)}</span>
                      )}
                    </TD>
                    <TD>
                      <Button variant="ghost" size="sm" onClick={() => closeTask(task)}>
                        Close
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </TableWrap>
        )}
      </Card>

      <Drawer
        open={entering !== null}
        onClose={() => setEntering(null)}
        title={entering ? `${entering.panel_name} — ${entering.patient_name}` : 'Record results'}
      >
        {panel && (
          <div className="space-y-4">
            <p className="text-small text-text-secondary">
              {/* The ranges are shown while typing, so an obvious transcription
                  slip is visible before it becomes an alert to a family. */}
              Expected ranges are shown beside each field. Leave a field blank to omit it.
            </p>

            {panel.analytes.map((analyte) => (
              <Input
                key={analyte.code}
                label={analyte.label}
                hint={
                  analyte.ref_low !== null && analyte.ref_high !== null
                    ? `Expected ${analyte.ref_low}–${analyte.ref_high} ${analyte.unit}`
                    : analyte.ref_high !== null
                      ? `Expected up to ${analyte.ref_high} ${analyte.unit}`
                      : `Measured in ${analyte.unit}`
                }
                type="number"
                step="any"
                value={values[analyte.code] ?? ''}
                onChange={(event) =>
                  setValues((current) => ({ ...current, [analyte.code]: event.target.value }))
                }
              />
            ))}

            <div className="flex gap-2 border-t border-border-subtle pt-4">
              <Button onClick={submit} disabled={busy}>
                {busy ? 'Recording…' : 'Record results'}
              </Button>
              <Button variant="ghost" onClick={() => setEntering(null)}>
                Cancel
              </Button>
            </div>
          </div>
        )}

        {entering && entering.results.length > 0 && (
          <div className="mt-6">
            <h3 className="mb-2 text-small font-semibold text-text-primary">Current results</h3>
            <LabResultTable results={entering.results} />
          </div>
        )}
      </Drawer>
    </div>
  )
}
