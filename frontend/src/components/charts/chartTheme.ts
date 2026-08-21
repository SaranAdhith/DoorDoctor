/**
 * One chart treatment for the whole product.
 *
 * Axes, gridlines, tooltips and threshold bands are defined here so every
 * chart added in later phases reads the same way as the first one.
 */

export const CHART_COLORS = {
  primary: '#002643', // navy-800
  secondary: '#32B641', // brand-500
  threshold: '#b45309', // status-watch
  grid: '#e2e8f0', // border-subtle
  axis: '#7c8da3', // text-muted
} as const

export const axisProps = {
  tick: { fontSize: 11, fill: CHART_COLORS.axis },
  tickLine: false,
} as const

export const xAxisProps = {
  ...axisProps,
  axisLine: { stroke: CHART_COLORS.grid },
} as const

export const yAxisProps = {
  ...axisProps,
  axisLine: false as const,
} as const

export const gridProps = {
  stroke: CHART_COLORS.grid,
  strokeDasharray: '4 4',
  vertical: false,
} as const

export const tooltipProps = {
  contentStyle: {
    borderRadius: 12,
    border: '1px solid #e2e8f0',
    fontSize: 12,
    boxShadow: '0 4px 12px -2px rgba(0, 38, 67, 0.12)',
    fontVariantNumeric: 'tabular-nums',
  },
  cursor: { stroke: CHART_COLORS.grid, strokeWidth: 1 },
} as const

export const lineProps = {
  type: 'monotone',
  strokeWidth: 2.5,
  dot: { r: 3 },
  activeDot: { r: 5 },
} as const

/** Dashed reference line marking a configured monitoring threshold. */
export const thresholdLineProps = {
  stroke: CHART_COLORS.threshold,
  strokeDasharray: '5 4',
} as const

export const thresholdLabel = {
  value: 'Threshold',
  position: 'insideTopRight',
  fontSize: 10,
  fill: CHART_COLORS.threshold,
  offset: 6,
} as const
