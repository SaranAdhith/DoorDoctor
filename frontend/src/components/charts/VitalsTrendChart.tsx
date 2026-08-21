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
import { Card, EmptyState, Tabs } from '../ui'
import {
  CHART_COLORS,
  gridProps,
  lineProps,
  thresholdLabel,
  thresholdLineProps,
  tooltipProps,
  xAxisProps,
  yAxisProps,
} from './chartTheme'

interface Props {
  history: Vitals[]
  thresholds: Threshold[]
}

type MetricKey = (typeof TREND_METRICS)[number]['key']

export function VitalsTrendChart({ history, thresholds }: Props) {
  const [metric, setMetric] = useState<MetricKey>('blood_pressure')

  const data = history.map((entry) => ({
    label: formatDate(entry.recorded_at),
    systolic: entry.systolic_bp,
    diastolic: entry.diastolic_bp,
    value: metric === 'blood_pressure' ? entry.systolic_bp : (entry[metric as keyof Vitals] as number),
  }))

  const thresholdMetric = metric === 'blood_pressure' ? 'systolic_bp' : metric
  const highThreshold = thresholds.find((t) => t.metric === thresholdMetric)?.high_threshold ?? null

  return (
    <Card
      title="Health trend"
      action={
        <Tabs
          items={TREND_METRICS.map((option) => ({ value: option.key, label: option.label }))}
          value={metric}
          onChange={setMetric}
          label="Trend metric"
          variant="segmented"
          className="w-full lg:w-auto"
        />
      }
    >
      {data.length === 0 ? (
        <EmptyState
          title="No readings yet"
          description="Trends appear here after the first nurse visit."
        />
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="label" {...xAxisProps} />
              <YAxis {...yAxisProps} domain={['dataMin - 6', 'dataMax + 6']} />
              <Tooltip {...tooltipProps} />
              {highThreshold !== null && (
                <ReferenceLine y={highThreshold} {...thresholdLineProps} label={thresholdLabel} />
              )}
              {metric === 'blood_pressure' ? (
                <>
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line
                    {...lineProps}
                    dataKey="systolic"
                    name="Top number"
                    stroke={CHART_COLORS.primary}
                  />
                  <Line
                    {...lineProps}
                    dataKey="diastolic"
                    name="Bottom number"
                    stroke={CHART_COLORS.secondary}
                  />
                </>
              ) : (
                <Line
                  {...lineProps}
                  dataKey="value"
                  name={TREND_METRICS.find((option) => option.key === metric)?.label}
                  stroke={CHART_COLORS.primary}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  )
}
