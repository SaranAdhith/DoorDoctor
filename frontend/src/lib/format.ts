import type { AlertSeverity, VisitStatus, VitalMetric } from '../types'

/**
 * Backend timestamps are naive server wall-clock time, so a value without a
 * timezone suffix is parsed as local time rather than shifted.
 */
function toDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatDate(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '--'
  return date.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })
}

export function formatTime(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '--'
  return date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

export function formatDateTime(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '--'
  return `${formatDate(value)}, ${formatTime(value)}`
}

export function formatRelative(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '--'
  const minutes = Math.round((Date.now() - date.getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} hr ago`
  const days = Math.round(hours / 24)
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days} days ago`
  return formatDate(value)
}

export function isToday(value: string | null | undefined): boolean {
  const date = toDate(value)
  if (!date) return false
  const now = new Date()
  return (
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear()
  )
}

/** `datetime-local` inputs expect a local, timezone-free string. */
export function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`
}

/**
 * `datetime-local` already produces `YYYY-MM-DDTHH:mm` in local time, which is
 * exactly the naive format the API stores - only the seconds are added.
 */
export function localInputToApi(value: string): string {
  return value.length === 16 ? `${value}:00` : value
}

export const METRIC_LABELS: Record<VitalMetric, string> = {
  systolic_bp: 'Systolic BP',
  diastolic_bp: 'Diastolic BP',
  heart_rate: 'Heart Rate',
  blood_glucose: 'Blood Glucose',
  spo2: 'SpO2',
  temperature: 'Temperature',
  weight: 'Weight',
}

export const METRIC_UNITS: Record<VitalMetric, string> = {
  systolic_bp: 'mmHg',
  diastolic_bp: 'mmHg',
  heart_rate: 'bpm',
  blood_glucose: 'mg/dL',
  spo2: '%',
  temperature: '°F',
  weight: 'kg',
}

export function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

export const VISIT_STATUS_LABELS: Record<VisitStatus, string> = {
  scheduled: 'Scheduled',
  in_progress: 'In Progress',
  completed: 'Completed',
  missed: 'Missed',
  cancelled: 'Cancelled',
}

export const SEVERITY_LABELS: Record<AlertSeverity, string> = {
  info: 'Info',
  warning: 'Warning',
  critical: 'Critical',
}

export function greeting(name: string): string {
  const hour = new Date().getHours()
  const part = hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening'
  return `Good ${part}, ${name.split(' ')[0]}`
}
