import { useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { formatDate } from '../../lib/format'
import { TREND_METRICS } from '../../lib/vitals'
import type { Threshold, Vitals } from '../../types'

interface Props {
  history: Vitals[]
  thresholds: Threshold[]
}

const NAVY = '#002643'
const GREEN = '#32B641'
const AMBER = '#f59e0b'

export function VitalsTrendChart({ history, thresholds }: Props) {
  const [metric, setMetric] = useState<(typeof TREND_METRICS)[number]['key']>('blood_pressure')

  const data = history.map((entry) => ({
    label: formatDate(entry.recorded_at),
    systolic: entry.systolic_bp,
    diastolic: entry.diastolic_bp,
    value: metric === 'blood_pressure' ? entry.systolic_bp : (entry[metric as keyof Vitals] as number),
  }))

  const highThreshold =
    metric === 'blood_pressure'
      ? (thresholds.find((t) => t.metric === 'systolic_bp')?.high_threshold ?? null)
      : (thresholds.find((t) => t.metric === metric)?.high_threshold ?? null)

  return (
    <section className="card">
      <header className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="card-heading">Health Trend</h2>
        <div className="-mx-1 flex gap-1 overflow-x-auto px-1" role="tablist" aria-label="Trend metric">
          {TREND_METRICS.map((option) => (
            <button
              key={option.key}
              type="button"
              role="tab"
              aria-selected={metric === option.key}
              onClick={() => setMetric(option.key)}
              className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                metric === option.key
                  ? 'bg-navy-800 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </header>

      {data.length === 0 ? (
        <p className="py-12 text-center text-sm text-slate-500">
          No readings recorded yet. Trends appear after the first nurse visit.
        </p>
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: '#64748b' }}
                tickLine={false}
                axisLine={{ stroke: '#e2e8f0' }}
              />
              <YAxis
                tick={{ fontSize: 11, fill: '#64748b' }}
                tickLine={false}
                axisLine={false}
                domain={['dataMin - 6', 'dataMax + 6']}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 12,
                  border: '1px solid #e2e8f0',
                  fontSize: 12,
                  boxShadow: '0 8px 24px -12px rgba(0,38,67,.3)',
                }}
              />
              {highThreshold !== null && (
                <ReferenceLine
                  y={highThreshold}
                  stroke={AMBER}
                  strokeDasharray="5 4"
                  label={{
                    value: 'Threshold',
                    position: 'insideTopRight',
                    fontSize: 10,
                    fill: AMBER,
                    offset: 6,
                  }}
                />
              )}
              {metric === 'blood_pressure' ? (
                <>
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line
                    type="monotone"
                    dataKey="systolic"
                    name="Systolic"
                    stroke={NAVY}
                    strokeWidth={2.5}
                    dot={{ r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="diastolic"
                    name="Diastolic"
                    stroke={GREEN}
                    strokeWidth={2.5}
                    dot={{ r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </>
              ) : (
                <Line
                  type="monotone"
                  dataKey="value"
                  name={TREND_METRICS.find((option) => option.key === metric)?.label}
                  stroke={NAVY}
                  strokeWidth={2.5}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  )
}
