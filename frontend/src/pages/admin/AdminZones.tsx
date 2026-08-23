import { adminOpsApi } from '../../api/trust'
import {
  Badge,
  Card,
  ErrorState,
  LoadingScreen,
  Table,
  TableWrap,
  TBody,
  TD,
  TEmptyRow,
  TH,
  THead,
  TR,
} from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import type { ZoneRow, ZoneView } from '../../types'

/**
 * The zone view (§4.17).
 *
 * The 30–45 subscriber break-even band is the one business figure DoorDoctor
 * actually recorded. The cost model behind it was never supplied — so this
 * screen says **which side of the band each zone sits on** and stops. It does
 * not estimate a margin, a contribution or a payback month, because inventing
 * one and putting it next to a real number is how an invented number becomes a
 * quoted one.
 *
 * The note under the heading comes from the server, so the caveat travels with
 * the numbers rather than being a sentence somebody typed on one screen.
 */

const POSITION: Record<ZoneRow['break_even'], { label: string; tone: 'good' | 'watch' | 'attention' }> = {
  above: { label: 'Above the band', tone: 'good' },
  within: { label: 'Inside the band', tone: 'watch' },
  below: { label: 'Below the band', tone: 'attention' },
}

export function AdminZones() {
  const zones = useAsync<ZoneView>(() => adminOpsApi.zones(), [])

  if (zones.loading) return <LoadingScreen label="Loading zones" />
  if (zones.error) return <ErrorState message={zones.error} onRetry={() => zones.reload()} />
  const data = zones.data
  if (!data) return null

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-h1 font-semibold text-text-primary">Zones</h1>
        <p className="max-w-3xl text-small text-text-secondary">{data.note}</p>
      </header>

      <Card>
        <TableWrap>
          <Table>
            <THead>
              <TR>
                <TH>Zone</TH>
                <TH>Active patients</TH>
                <TH>Nurses</TH>
                <TH>Patients per nurse</TH>
                <TH>Visits ({data.window_days}d)</TH>
                <TH>Open alerts</TH>
                <TH>Break-even</TH>
              </TR>
            </THead>
            <TBody>
              {data.zones.length === 0 && <TEmptyRow colSpan={7}>No zones yet.</TEmptyRow>}
              {data.zones.map((zone) => {
                const position = POSITION[zone.break_even]
                return (
                  <TR key={zone.zone}>
                    <TD className="font-medium text-text-primary">{zone.zone}</TD>
                    <TD className="tnum">{zone.active_patients}</TD>
                    <TD className="tnum">{zone.nurses}</TD>
                    <TD className="tnum">{zone.patients_per_nurse ?? '—'}</TD>
                    <TD className="tnum">{zone.visits_in_window}</TD>
                    <TD className="tnum">{zone.open_alerts}</TD>
                    <TD>
                      <Badge tone={position.tone}>{position.label}</Badge>
                      {zone.to_break_even > 0 && (
                        <p className="mt-1 text-caption text-text-muted">
                          {zone.to_break_even} more to reach {data.break_even_min}
                        </p>
                      )}
                    </TD>
                  </TR>
                )
              })}
            </TBody>
          </Table>
        </TableWrap>
      </Card>
    </div>
  )
}
