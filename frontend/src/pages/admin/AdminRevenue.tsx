import { AlertTriangle, IndianRupee, TrendingUp, Users } from 'lucide-react'

import { revenueApi } from '../../api/billing'
import { useAsync } from '../../hooks/useAsync'
import { formatINR, formatINRCompact } from '../../lib/money'
import {
  Card,
  ErrorState,
  EmptyState,
  LoadingScreen,
  ProgressMeter,
  StatTile,
} from '../../components/ui'

export function AdminRevenue() {
  const data = useAsync(() => revenueApi.summary(), [])

  if (data.loading) return <LoadingScreen label="Loading revenue" />
  if (data.error) return <ErrorState message={data.error} onRetry={() => void data.reload()} />
  if (!data.data) return null

  const revenue = data.data
  const topPlanMrr = Math.max(1, ...revenue.by_plan.map((row) => row.mrr_paise))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 font-bold text-text-primary">Revenue</h1>
        <p className="mt-1 text-small text-text-secondary">
          Recurring revenue, collections and what is still owed. Only settled invoices count as
          collected.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile
          label="MRR"
          value={formatINRCompact(revenue.mrr_paise)}
          hint={`${formatINRCompact(revenue.arr_paise)} annualised`}
          icon={<TrendingUp className="h-4 w-4" />}
        />
        <StatTile
          label="Active subscriptions"
          value={revenue.active_subscriptions}
          hint={`${formatINR(revenue.arpu_paise)} average per account`}
          icon={<Users className="h-4 w-4" />}
        />
        <StatTile
          label="Collected this month"
          value={formatINRCompact(revenue.collected_this_month_paise)}
          hint={`${formatINRCompact(revenue.collected_all_time_paise)} all time`}
          icon={<IndianRupee className="h-4 w-4" />}
        />
        <StatTile
          label="Outstanding"
          value={formatINRCompact(revenue.outstanding_paise)}
          tone={revenue.overdue_paise > 0 ? 'attention' : 'default'}
          hint={
            revenue.overdue_paise > 0
              ? `${formatINR(revenue.overdue_paise)} overdue`
              : 'All within terms'
          }
          icon={<AlertTriangle className="h-4 w-4" />}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Recurring revenue by plan" description="Annual plans count as a twelfth of their price.">
          {revenue.by_plan.length === 0 ? (
            <EmptyState title="No active subscriptions yet" />
          ) : (
            <div className="space-y-4">
              {revenue.by_plan.map((row) => (
                <ProgressMeter
                  key={row.plan}
                  label={`${row.plan} · ${row.subscribers} subscriber${row.subscribers === 1 ? '' : 's'}`}
                  showLabel
                  valueText={formatINR(row.mrr_paise)}
                  value={row.mrr_paise}
                  max={topPlanMrr}
                  tone="neutral"
                />
              ))}
            </div>
          )}
        </Card>

        <Card title="Account health">
          {/*
            A description list, not a Table: these are four measure/value pairs,
            and `Table` carries a 36rem minimum width that overflows this
            half-width card and scrolls the values out of sight.
          */}
          <dl className="divide-y divide-border-subtle">
            {[
              { label: 'Cancellations scheduled', value: String(revenue.pending_cancellations) },
              { label: 'Subscriptions ended', value: String(revenue.cancelled_subscriptions) },
              {
                label: 'Credits owed to customers',
                value: formatINR(revenue.credits_outstanding_paise),
              },
              { label: 'Overdue', value: formatINR(revenue.overdue_paise) },
            ].map((row) => (
              <div key={row.label} className="flex items-baseline justify-between gap-4 py-2.5">
                <dt className="text-small text-text-secondary">{row.label}</dt>
                <dd className="tnum text-small font-semibold text-text-primary">{row.value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-caption text-text-muted">
            Credits owed are referral and loyalty rewards that have been earned and not yet applied
            to an invoice. They reduce future revenue, not revenue already collected.
          </p>
        </Card>
      </div>
    </div>
  )
}
