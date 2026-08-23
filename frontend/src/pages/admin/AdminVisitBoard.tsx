import { CalendarDays } from 'lucide-react'
import { useState } from 'react'

import { adminOpsApi, type BoardFilters } from '../../api/trust'
import { LocationBadge } from '../../components/trust'
import {
  Card,
  ErrorState,
  LoadingScreen,
  Pagination,
  Select,
  StatTile,
  Table,
  TableWrap,
  TBody,
  TD,
  TEmptyRow,
  TH,
  THead,
  TR,
  VisitStatusBadge,
} from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import { formatDate, formatTime } from '../../lib/format'
import type { VisitBoard as VisitBoardData } from '../../types'

/**
 * The visit board (§4.17).
 *
 * This replaces the old newest-250 visit list, which STATE.md recorded as owed
 * to this phase by name: with a forward schedule in the data, a newest-first cap
 * meant the admin table opened on next week rather than on today.
 *
 * A board is a **window with a page**. The counts above the table describe the
 * whole window, not the page — a summary that changed when you clicked "next"
 * would be reporting a different business each time.
 */

function isoDate(offsetDays = 0): string {
  const date = new Date()
  date.setDate(date.getDate() + offsetDays)
  return date.toISOString().slice(0, 10)
}

const WINDOWS = [
  { value: '0', label: 'Today' },
  { value: '1', label: 'Tomorrow' },
  { value: '7', label: 'Next 7 days' },
  { value: '-7', label: 'Last 7 days' },
]

export function AdminVisitBoard() {
  const [window, setWindow] = useState('0')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)

  const span = Number(window)
  const filters: BoardFilters = {
    from: span >= 0 ? isoDate(span === 7 ? 0 : span) : isoDate(span),
    to: span >= 0 ? isoDate(span === 7 ? 7 : span + 1) : isoDate(1),
    status: status as BoardFilters['status'],
    page,
  }

  const board = useAsync<VisitBoardData>(
    () => adminOpsApi.board(filters),
    [window, status, page],
  )

  if (board.loading && !board.data) return <LoadingScreen label="Loading the board" />
  if (board.error) return <ErrorState message={board.error} onRetry={() => board.reload()} />
  const data = board.data
  if (!data) return null

  const summary = data.summary

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-h1 font-semibold text-text-primary">Visit board</h1>
          <p className="text-small text-text-secondary">
            {formatDate(data.from)} · {data.total} visit{data.total === 1 ? '' : 's'} in this window
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Select
            label="Window"
            hideLabel
            value={window}
            onChange={(event) => {
              setWindow(event.target.value)
              setPage(1)
            }}
            className="w-40"
          >
            {WINDOWS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
          <Select
            label="Status"
            hideLabel
            value={status}
            onChange={(event) => {
              setStatus(event.target.value)
              setPage(1)
            }}
            className="w-44"
          >
            <option value="">Every status</option>
            <option value="scheduled">Scheduled</option>
            <option value="in_progress">In progress</option>
            <option value="completed">Completed</option>
            <option value="missed">Missed</option>
            <option value="cancelled">Cancelled</option>
          </Select>
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Scheduled" value={String(summary.scheduled ?? 0)} />
        <StatTile label="In progress" value={String(summary.in_progress ?? 0)} tone="watch" />
        <StatTile label="Completed" value={String(summary.completed ?? 0)} tone="good" />
        <StatTile
          label="Unassigned"
          value={String(summary.unassigned ?? 0)}
          tone={(summary.unassigned ?? 0) > 0 ? 'attention' : undefined}
        />
      </div>

      <Card>
        <TableWrap>
          <Table>
            <THead>
              <TR>
                <TH>Time</TH>
                <TH>Patient</TH>
                <TH>Nurse</TH>
                <TH>Status</TH>
                <TH>Location</TH>
              </TR>
            </THead>
            <TBody>
              {data.visits.length === 0 && (
                <TEmptyRow colSpan={5}>
                  <span className="flex items-center justify-center gap-2">
                    <CalendarDays aria-hidden className="h-4 w-4" />
                    No visits in this window.
                  </span>
                </TEmptyRow>
              )}
              {data.visits.map((visit) => (
                <TR key={visit.id}>
                  <TD className="tnum whitespace-nowrap">{formatTime(visit.scheduled_at)}</TD>
                  <TD>
                    <span className="font-medium text-text-primary">{visit.patient?.name}</span>
                    <p className="text-caption text-text-muted">{visit.patient?.address}</p>
                  </TD>
                  <TD>
                    {visit.nurse?.name ?? (
                      <span className="text-status-attention">Unassigned</span>
                    )}
                  </TD>
                  <TD>
                    <VisitStatusBadge status={visit.status} />
                  </TD>
                  <TD>
                    {visit.checkin_at ? (
                      <LocationBadge
                        status={visit.location_status}
                        distanceM={visit.location_distance_m}
                        detail={visit.location_detail}
                      />
                    ) : (
                      <span className="text-caption text-text-muted">Not started</span>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </TableWrap>

        {data.pages > 1 && (
          <div className="mt-4">
            <Pagination
              page={data.page}
              pageSize={data.page_size}
              total={data.total}
              onPageChange={setPage}
            />
          </div>
        )}
      </Card>
    </div>
  )
}
