import { useState } from 'react'

import { adminOpsApi } from '../../api/trust'
import {
  Card,
  ErrorState,
  LoadingScreen,
  ProgressMeter,
  Select,
  StatTile,
} from '../../components/ui'
import { useAsync } from '../../hooks/useAsync'
import type { Outcomes } from '../../types'

/**
 * Outcome metrics (§4.17).
 *
 * Every number here is computed from the rows it describes, on read. There is
 * not a stored counter behind this screen, because a metric that can drift from
 * its own data is believed for exactly as long as it takes somebody to check it.
 *
 * Two deliberate absences worth knowing about:
 *
 * * **A rate with nothing to divide reads "No data", never 0%.** 0% looks like
 *   a failure, and "we did not measure anything this week" is not one.
 * * **SLA attainment counts only alerts that have had their chance.** An alert
 *   raised five minutes ago is neither met nor missed, and counting it as met
 *   would flatter every figure on the page.
 */

const WINDOWS = [
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
]

function rate(value: number | null): string {
  return value == null ? 'No data' : `${value}%`
}

function minutes(value: number | null): string {
  if (value == null) return 'No data'
  if (value < 60) return `${value} min`
  return `${Math.round((value / 60) * 10) / 10} hrs`
}

export function AdminOutcomes() {
  const [days, setDays] = useState('30')
  const outcomes = useAsync<Outcomes>(() => adminOpsApi.outcomes(Number(days)), [days])

  if (outcomes.loading && !outcomes.data) return <LoadingScreen label="Loading outcomes" />
  if (outcomes.error)
    return <ErrorState message={outcomes.error} onRetry={() => outcomes.reload()} />
  const data = outcomes.data
  if (!data) return null

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-h1 font-semibold text-text-primary">Outcomes</h1>
          <p className="text-small text-text-secondary">
            Computed from the records themselves every time this page is opened.
          </p>
        </div>
        <Select
          label="Window"
          hideLabel
          value={days}
          onChange={(event) => setDays(event.target.value)}
          className="w-44"
        >
          {WINDOWS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Visits completed" value={String(data.visits.completed)} tone="good" />
        <StatTile label="Visits scheduled" value={String(data.visits.scheduled)} />
        <StatTile label="Alerts raised" value={String(data.alerts.raised)} />
        <StatTile
          label="Escalations still open"
          value={String(data.escalations.still_open)}
          tone={data.escalations.still_open > 0 ? 'attention' : undefined}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Visits" description={`Over the last ${data.window_days} days.`}>
          <ProgressMeter
            value={data.visits.completed}
            max={Math.max(data.visits.scheduled, 1)}
            label="Visits completed"
            showLabel
            valueText={rate(data.visits.completion_rate)}
            tone="good"
          />
          <dl className="mt-4 space-y-2 text-small">
            <div className="flex justify-between">
              <dt className="text-text-secondary">Missed</dt>
              <dd className="tnum text-text-primary">{data.visits.missed}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-text-secondary">Cancelled</dt>
              <dd className="tnum text-text-primary">{data.visits.cancelled}</dd>
            </div>
          </dl>
        </Card>

        <Card title="Alerts" description="How quickly the team closed what was raised.">
          <dl className="space-y-2 text-small">
            <div className="flex justify-between">
              <dt className="text-text-secondary">Resolved</dt>
              <dd className="tnum text-text-primary">
                {data.alerts.resolved} of {data.alerts.raised}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-text-secondary">Median time to resolve</dt>
              <dd className="tnum text-text-primary">
                {minutes(data.alerts.median_minutes_to_resolve)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-text-secondary">Answered inside the SLA</dt>
              <dd className="tnum text-text-primary">{rate(data.alerts.sla_attainment)}</dd>
            </div>
          </dl>
          <p className="mt-3 text-caption text-text-muted">
            {data.alerts.sla_judged} of {data.alerts.raised} alerts have passed their deadline and
            can be counted; the rest are still inside it.
          </p>
        </Card>

        <Card title="Medication" description="Doses recorded by the nurses on visits.">
          <ProgressMeter
            value={data.medication.administered}
            max={Math.max(data.medication.logged, 1)}
            label="Doses taken"
            showLabel
            valueText={rate(data.medication.adherence)}
            tone="good"
          />
        </Card>

        <Card
          title="Check-in locations"
          description="Where visits were recorded from, measured against each home."
        >
          <ProgressMeter
            value={data.location.verified}
            max={Math.max(data.location.checked_in, 1)}
            label="Check-ins verified"
            showLabel
            valueText={rate(data.location.verified_rate)}
            tone="good"
          />
          <dl className="mt-4 space-y-2 text-small">
            <div className="flex justify-between">
              <dt className="text-text-secondary">Recorded away from the home</dt>
              <dd className="tnum text-text-primary">{data.location.out_of_range}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-text-secondary">No location available</dt>
              <dd className="tnum text-text-primary">{data.location.unavailable}</dd>
            </div>
          </dl>
        </Card>
      </div>
    </div>
  )
}
