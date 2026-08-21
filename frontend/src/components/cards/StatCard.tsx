import type { ReactNode } from 'react'

interface Props {
  label: string
  value: ReactNode
  hint?: string
  tone?: 'default' | 'critical' | 'success'
}

const TONES = {
  default: 'text-navy-800',
  critical: 'text-critical-600',
  success: 'text-brand-600',
}

export function StatCard({ label, value, hint, tone = 'default' }: Props) {
  return (
    <article className="card">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</h3>
      <p className={`mt-2 text-3xl font-bold tabular-nums ${TONES[tone]}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </article>
  )
}
