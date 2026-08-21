import type { Adherence } from '../../types'

export function AdherenceCard({ adherence }: { adherence: Adherence }) {
  const hasData = adherence.percentage !== null

  return (
    <section className="card">
      <h2 className="card-heading">Medication Adherence</h2>

      <div className="mt-3 flex items-end gap-4">
        {/* No data is shown as "No data", never 0% - that would imply missed doses. */}
        <p className="text-4xl font-extrabold tabular-nums text-navy-800">
          {hasData ? `${adherence.percentage}%` : <span className="text-2xl text-slate-400">No data</span>}
        </p>
        {hasData && (
          <p className="pb-1.5 text-xs text-slate-500">
            {adherence.administered} of {adherence.total} logged doses
          </p>
        )}
      </div>

      {hasData && (
        <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-brand-500 transition-all"
            style={{ width: `${adherence.percentage}%` }}
            role="presentation"
          />
        </div>
      )}

      <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-xl bg-brand-50 py-2">
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-brand-700">Administered</dt>
          <dd className="text-lg font-bold tabular-nums text-brand-700">{adherence.administered}</dd>
        </div>
        <div className="rounded-xl bg-warning-50 py-2">
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-warning-700">Skipped</dt>
          <dd className="text-lg font-bold tabular-nums text-warning-700">{adherence.skipped}</dd>
        </div>
        <div className="rounded-xl bg-critical-50 py-2">
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-critical-700">Refused</dt>
          <dd className="text-lg font-bold tabular-nums text-critical-700">{adherence.refused}</dd>
        </div>
      </dl>
    </section>
  )
}
