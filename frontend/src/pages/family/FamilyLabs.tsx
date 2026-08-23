import { FlaskConical } from 'lucide-react'
import { useState } from 'react'

import { labsApi } from '../../api/clinical'
import { patientsApi } from '../../api/patients'
import { EmergencyBlock, LabResultTable } from '../../components/clinical'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingScreen,
  Modal,
  Select,
  useToast,
} from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import { formatDate } from '../../lib/format'
import { formatINR } from '../../lib/money'
import type { LabOrder, LabPanel, Patient } from '../../types'

/**
 * Labs and tests, for the family (§4.2).
 *
 * The ordering dialogue says what the panel will cost **before** it is ordered,
 * because the plan's allowance and the ₹499 add-on are the same button on this
 * screen and the family has to know which one they are about to press. The
 * price comes from the server; no rupee figure is typed into the frontend.
 */

function statusTone(order: LabOrder) {
  if (order.status === 'cancelled') return 'neutral' as const
  if (order.status !== 'resulted') return 'info' as const
  return order.abnormal_count > 0 ? ('watch' as const) : ('good' as const)
}

function statusLabel(order: LabOrder): string {
  if (order.status === 'ordered') return 'Sample not yet collected'
  if (order.status === 'collected') return 'With the laboratory'
  if (order.status === 'cancelled') return 'Cancelled'
  return order.abnormal_count > 0
    ? `${order.abnormal_count} result${order.abnormal_count > 1 ? 's' : ''} outside range`
    : 'All results in range'
}

export function FamilyLabs() {
  const toast = useToast()
  const [ordering, setOrdering] = useState(false)
  const [panelCode, setPanelCode] = useState('')
  const [busy, setBusy] = useState(false)

  const patients = useAsync<Patient[]>(() => patientsApi.list(), [])
  const patientId = patients.data?.[0]?.id ?? null

  const panels = useAsync<LabPanel[]>(() => labsApi.panels(), [])
  const orders = useAsync<LabOrder[]>(
    async () => (patientId ? labsApi.list(patientId) : []),
    [patientId],
  )

  const selected = panels.data?.find((panel) => panel.code === panelCode) ?? null

  async function submit() {
    if (!patientId || !panelCode) return
    setBusy(true)
    try {
      await labsApi.order(patientId, panelCode)
      toast.notify('Test ordered. The team will arrange collection.', 'success')
      setOrdering(false)
      setPanelCode('')
      await orders.reload({ quiet: true })
    } catch (error) {
      toast.notify(
        error instanceof Error ? error.message : 'Could not order the test.',
        'error',
      )
    } finally {
      setBusy(false)
    }
  }

  if (patients.loading) return <LoadingScreen label="Loading tests" />
  if (patients.error) return <ErrorState message={patients.error} onRetry={() => patients.reload()} />
  if (!patientId) {
    return (
      <EmptyState
        icon={<FlaskConical aria-hidden />}
        title="No patient linked yet"
        description="Ask DoorDoctor to link a patient to your account."
      />
    )
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-h1 font-semibold text-text-primary">Tests and results</h1>
          <p className="text-small text-text-secondary">
            Blood tests arranged at home, with results explained beside the expected range.
          </p>
        </div>
        <Button onClick={() => setOrdering(true)}>Order a test</Button>
      </header>

      <EmergencyBlock compact />

      {orders.loading && <LoadingScreen label="Loading results" />}
      {orders.error && <ErrorState message={orders.error} onRetry={() => orders.reload()} />}

      {orders.data?.length === 0 && (
        <EmptyState
          icon={<FlaskConical aria-hidden />}
          title="No tests yet"
          description="When a blood test is arranged, the results appear here with the range each one is measured against."
          action={<Button onClick={() => setOrdering(true)}>Order a test</Button>}
        />
      )}

      <div className="space-y-4">
        {orders.data?.map((order) => (
          <Card
            key={order.id}
            title={order.panel_name}
            description={`Ordered ${formatDate(order.ordered_at)}${
              order.reported_at ? ` · results ${formatDate(order.reported_at)}` : ''
            }`}
            action={<Badge tone={statusTone(order)}>{statusLabel(order)}</Badge>}
          >
            {order.results.length > 0 ? (
              <LabResultTable results={order.results} />
            ) : (
              <p className="text-small text-text-muted">
                Results are not back yet. We will let you know as soon as they are.
              </p>
            )}

            {order.abnormal_count > 0 && (
              <p className="mt-3 text-caption text-text-secondary">
                A member of the care team is following this up. Results outside the expected range
                are common and are not a diagnosis on their own.
              </p>
            )}
          </Card>
        ))}
      </div>

      <Modal open={ordering} onClose={() => setOrdering(false)} title="Order a test">
        <div className="space-y-4">
          <Select
            label="Which test?"
            value={panelCode}
            onChange={(event) => setPanelCode(event.target.value)}
          >
            <option value="">Choose a test…</option>
            {panels.data?.map((panel) => (
              <option key={panel.code} value={panel.code}>
                {panel.name}
              </option>
            ))}
          </Select>

          {selected && (
            <div className="rounded-md bg-surface-sunken p-3">
              <p className="text-small text-text-secondary">{selected.description}</p>
              <p className="mt-2 text-caption text-text-muted">
                Results usually within {selected.turnaround_hours} hours. Covered by your plan while
                you have tests remaining this year; after that it is{' '}
                {formatINR(selected.price_paise)}.
              </p>
            </div>
          )}

          <div className="flex gap-2">
            <Button onClick={submit} disabled={!panelCode || busy}>
              {busy ? 'Ordering…' : 'Order this test'}
            </Button>
            <Button variant="ghost" onClick={() => setOrdering(false)}>
              Cancel
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
