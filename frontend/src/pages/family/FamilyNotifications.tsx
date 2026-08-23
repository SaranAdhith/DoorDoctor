import { BellRing, Moon } from 'lucide-react'
import { useState } from 'react'

import { notificationsApi } from '../../api/trust'
import {
  Badge,
  Card,
  ErrorState,
  LoadingScreen,
  Select,
  Switch,
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
import { formatDateTime } from '../../lib/format'
import type { DeliveryRecord, NotificationPreferences } from '../../types'

/**
 * How DoorDoctor reaches you (§4.18).
 *
 * Two things this screen is careful about.
 *
 * **There is no switch for the app itself.** What a family sees when they open
 * DoorDoctor is not a delivery preference, and a control that could hide their
 * mother's reading inside the product is not one anybody asked for.
 *
 * **Quiet hours are stated as never applying to a critical alert** — on the
 * screen, in the sentence next to the switch, rather than in a policy nobody
 * reads. A quiet-hours setting that could silence a critical alert is a setting
 * that can kill somebody.
 *
 * The delivery record below is the same list an admin sees when a family says
 * "I never got the alert", including the messages that were held back or could
 * not be sent — those are recorded decisions, not gaps.
 */

const CHANNEL_LABELS: Record<string, string> = {
  email: 'Email',
  sms: 'SMS',
  whatsapp: 'WhatsApp',
  push: 'Push notification',
}

const STATUS_LABELS: Record<DeliveryRecord['status'], { label: string; tone: 'good' | 'neutral' | 'watch' | 'attention' }> = {
  sent: { label: 'Sent', tone: 'good' },
  simulated: { label: 'Sent', tone: 'good' },
  suppressed: { label: 'Held back', tone: 'neutral' },
  unreachable: { label: 'No address', tone: 'watch' },
  failed: { label: 'Failed', tone: 'attention' },
}

const HOURS = Array.from({ length: 24 }, (_, hour) => hour)

function hourLabel(hour: number): string {
  return `${String(hour).padStart(2, '0')}:00`
}

export function FamilyNotifications() {
  const toast = useToast()
  const [saving, setSaving] = useState(false)

  const preferences = useAsync<NotificationPreferences>(() => notificationsApi.preferences(), [])
  const log = useAsync<DeliveryRecord[]>(() => notificationsApi.deliveryLog(), [])

  async function save(body: Record<string, unknown>) {
    setSaving(true)
    try {
      const updated = await notificationsApi.savePreferences(body)
      preferences.setData(updated)
    } catch (error) {
      toast.notify(error instanceof Error ? error.message : 'Could not save that.', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (preferences.loading) return <LoadingScreen label="Loading your settings" />
  if (preferences.error)
    return <ErrorState message={preferences.error} onRetry={() => preferences.reload()} />
  const data = preferences.data
  if (!data) return null

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-h1 font-semibold text-text-primary">How we reach you</h1>
        <p className="max-w-2xl text-small text-text-secondary">
          Alerts always appear in DoorDoctor. These settings decide what is also sent to your phone
          or inbox.
        </p>
      </header>

      <Card
        title="Channels"
        description={`Something urgent goes out on ${data.critical_channel_count} channels at once, chosen from the ones switched on here.`}
      >
        <ul className="space-y-3">
          {Object.entries(data.channels).map(([channel, enabled]) => (
            <li key={channel} className="flex items-center justify-between gap-3">
              <div>
                <p className="font-medium text-text-primary">
                  {CHANNEL_LABELS[channel] ?? channel}
                </p>
                {channel === 'push' && (
                  <p className="text-caption text-text-muted">
                    Available once the DoorDoctor mobile app is released.
                  </p>
                )}
              </div>
              <Switch
                checked={enabled}
                disabled={saving || channel === 'push'}
                onChange={(value) => save({ channels: { [channel]: value } })}
                label={enabled ? 'On' : 'Off'}
              />
            </li>
          ))}
        </ul>
      </Card>

      <Card
        title="Quiet hours"
        description="Routine messages wait until the morning. Anything critical is always sent, whatever the time."
      >
        <div className="flex flex-wrap items-end gap-4">
          <Switch
            checked={data.quiet_hours_enabled}
            disabled={saving}
            onChange={(value) => save({ quiet_hours_enabled: value })}
            label="Hold routine messages overnight"
          />
          {data.quiet_hours_enabled && (
            <>
              <Select
                label="From"
                value={String(data.quiet_start_hour)}
                onChange={(event) => save({ quiet_start_hour: Number(event.target.value) })}
                className="w-32"
              >
                {HOURS.map((hour) => (
                  <option key={hour} value={hour}>
                    {hourLabel(hour)}
                  </option>
                ))}
              </Select>
              <Select
                label="Until"
                value={String(data.quiet_end_hour)}
                onChange={(event) => save({ quiet_end_hour: Number(event.target.value) })}
                className="w-32"
              >
                {HOURS.map((hour) => (
                  <option key={hour} value={hour}>
                    {hourLabel(hour)}
                  </option>
                ))}
              </Select>
            </>
          )}
        </div>

        {data.in_quiet_hours_now && (
          <p className="mt-4 flex items-center gap-2 rounded-lg bg-surface-raised px-3 py-2 text-small text-text-secondary">
            <Moon aria-hidden className="h-4 w-4" />
            You are inside your quiet hours right now. Routine messages are waiting; anything
            critical is still being sent.
          </p>
        )}

        {data.critical_always_delivered && (
          <p className="mt-3 flex items-center gap-2 text-caption text-text-muted">
            <BellRing aria-hidden className="h-4 w-4" />
            A critical alert is never held back by these settings.
          </p>
        )}
      </Card>

      <Card
        title="What we have sent you"
        description="Including messages that were held back or could not be delivered."
      >
        {log.loading && <LoadingScreen label="Loading" />}
        {log.error && <ErrorState message={log.error} onRetry={() => log.reload()} />}
        {log.data && (
          <TableWrap>
            <Table>
              <THead>
                <TR>
                  <TH>When</TH>
                  <TH>Channel</TH>
                  <TH>About</TH>
                  <TH>Outcome</TH>
                </TR>
              </THead>
              <TBody>
                {log.data.length === 0 && (
                  <TEmptyRow colSpan={4}>Nothing has been sent to you yet.</TEmptyRow>
                )}
                {log.data.map((record) => {
                  const status = STATUS_LABELS[record.status] ?? {
                    label: record.status,
                    tone: 'neutral' as const,
                  }
                  return (
                    <TR key={record.id}>
                      <TD className="tnum whitespace-nowrap">{formatDateTime(record.created_at)}</TD>
                      <TD>{CHANNEL_LABELS[record.channel] ?? record.channel}</TD>
                      <TD className="text-text-secondary">{record.subject}</TD>
                      <TD>
                        <Badge tone={status.tone}>{status.label}</Badge>
                        {record.detail && (
                          <p className="mt-1 text-caption text-text-muted">{record.detail}</p>
                        )}
                      </TD>
                    </TR>
                  )
                })}
              </TBody>
            </Table>
          </TableWrap>
        )}
      </Card>
    </div>
  )
}
