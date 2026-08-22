import { useMemo, useState } from 'react'
import { Download } from 'lucide-react'

import { invoicesApi, openInvoicePdf, subscriptionsApi } from '../../api/billing'
import { ApiError } from '../../api/client'
import { useAsync } from '../../hooks/useAsync'
import { formatDate } from '../../lib/format'
import { formatINR, formatPrice } from '../../lib/money'
import type { Invoice, Subscription } from '../../types'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingScreen,
  SegmentedControl,
  StatTile,
  Table,
  TableWrap,
  TBody,
  TD,
  TH,
  THead,
  TR,
  useToast,
} from '../../components/ui'

type Filter = 'all' | 'individual' | 'organization'

const FILTERS = [
  { value: 'all' as const, label: 'All' },
  { value: 'individual' as const, label: 'Families' },
  { value: 'organization' as const, label: 'Organizations' },
]

const STATUS_TONES = {
  active: 'good',
  past_due: 'watch',
  cancelled: 'neutral',
  expired: 'neutral',
} as const

export function AdminSubscriptions() {
  const { notify } = useToast()
  const [filter, setFilter] = useState<Filter>('all')
  const [payingId, setPayingId] = useState<number | null>(null)

  const data = useAsync(async () => {
    const [subscriptions, invoices] = await Promise.all([
      subscriptionsApi.all(),
      invoicesApi.list(),
    ])
    return { subscriptions, invoices }
  }, [])

  const rows = useMemo(() => {
    const all = data.data?.subscriptions ?? []
    if (filter === 'individual') return all.filter((s) => s.family_user_id !== null)
    if (filter === 'organization') return all.filter((s) => s.organization_id !== null)
    return all
  }, [data.data, filter])

  if (data.loading) return <LoadingScreen label="Loading subscriptions" />
  if (data.error) return <ErrorState message={data.error} onRetry={() => void data.reload()} />
  if (!data.data) return null

  const { subscriptions, invoices } = data.data
  const outstanding = invoices.filter((invoice) => invoice.status === 'issued')

  async function settle(invoice: Invoice) {
    setPayingId(invoice.id)
    try {
      await invoicesApi.pay(invoice.id)
      await data.reload({ quiet: true })
      notify(`${invoice.number} marked paid.`, 'success')
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'Something went wrong.', 'error')
    } finally {
      setPayingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 font-bold text-text-primary">Subscriptions</h1>
        <p className="mt-1 text-small text-text-secondary">
          Every paying relationship — families, employers and residences.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label="Active" value={subscriptions.filter((s) => s.status === 'active').length} />
        <StatTile
          label="Families"
          value={subscriptions.filter((s) => s.family_user_id !== null).length}
        />
        <StatTile
          label="Organizations"
          value={subscriptions.filter((s) => s.organization_id !== null).length}
        />
        <StatTile
          label="Ending soon"
          value={subscriptions.filter((s) => s.cancel_at_period_end).length}
          tone={subscriptions.some((s) => s.cancel_at_period_end) ? 'watch' : 'default'}
          hint="Cancellation scheduled"
        />
      </div>

      <Card
        title="Subscribers"
        flush
        action={
          <SegmentedControl
            legend="Filter subscriptions"
            hideLegend
            value={filter}
            options={FILTERS}
            onChange={setFilter}
          />
        }
      >
        {rows.length === 0 ? (
          <div className="p-5">
            <EmptyState title="No subscriptions match this filter" />
          </div>
        ) : (
          <TableWrap>
            <Table className="min-w-[52rem]">
              <THead>
                <TR>
                  <TH>Subscriber</TH>
                  <TH>Plan</TH>
                  <TH numeric>Price</TH>
                  <TH>Period ends</TH>
                  <TH numeric>Paid months</TH>
                  <TH>Status</TH>
                </TR>
              </THead>
              <TBody>
                {rows.map((subscription) => (
                  <SubscriptionRow key={subscription.id} subscription={subscription} />
                ))}
              </TBody>
            </Table>
          </TableWrap>
        )}
      </Card>

      <Card
        title="Outstanding invoices"
        description="No payment gateway is integrated in this build. Settling records a payment an admin has confirmed out of band."
        flush
      >
        {outstanding.length === 0 ? (
          <div className="p-5">
            <EmptyState title="Nothing outstanding" description="Every invoice raised has been settled." />
          </div>
        ) : (
          <TableWrap>
            <Table>
              <THead>
                <TR>
                  <TH>Invoice</TH>
                  <TH>Billed to</TH>
                  <TH>Due</TH>
                  <TH numeric>Amount</TH>
                  <TH>Action</TH>
                </TR>
              </THead>
              <TBody>
                {outstanding.map((invoice) => (
                  <TR key={invoice.id}>
                    <TD>
                      <span className="font-medium text-text-primary">{invoice.number}</span>
                    </TD>
                    <TD>{invoice.billed_to}</TD>
                    <TD>
                      <span
                        className={
                          new Date(invoice.due_at) < new Date()
                            ? 'font-medium text-status-attention'
                            : 'text-text-secondary'
                        }
                      >
                        {formatDate(invoice.due_at)}
                      </span>
                    </TD>
                    <TD numeric>
                      <span className="font-semibold text-text-primary">
                        {formatINR(invoice.total_paise)}
                      </span>
                    </TD>
                    <TD>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => void openInvoicePdf(invoice.id)}
                        >
                          <Download className="h-4 w-4" aria-hidden="true" />
                          <span className="sr-only">Download {invoice.number}</span>
                        </Button>
                        <Button
                          size="sm"
                          variant="accent"
                          loading={payingId === invoice.id}
                          onClick={() => void settle(invoice)}
                        >
                          Mark paid
                        </Button>
                      </div>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </TableWrap>
        )}
      </Card>
    </div>
  )
}

function SubscriptionRow({ subscription }: { subscription: Subscription }) {
  return (
    <TR>
      <TD>
        <span className="font-medium text-text-primary">{subscription.owner_label}</span>
        <span className="block text-caption text-text-muted">
          {subscription.organization_id !== null
            ? `${subscription.seats} ${subscription.plan.unit_label ?? 'seat'}s`
            : 'Family account'}
        </span>
      </TD>
      <TD>
        <span className="text-text-primary">{subscription.plan.name}</span>
        <span className="block text-caption text-text-muted capitalize">
          {subscription.billing_cycle}
        </span>
      </TD>
      <TD numeric>
        <span className="font-semibold text-text-primary">
          {formatPrice(subscription.period_price_paise, subscription.billing_cycle)}
        </span>
      </TD>
      <TD>{formatDate(subscription.current_period_end)}</TD>
      <TD numeric>{subscription.paid_months}</TD>
      <TD>
        <div className="flex flex-wrap gap-1.5">
          <Badge tone={STATUS_TONES[subscription.status]}>{subscription.status}</Badge>
          {subscription.cancel_at_period_end && <Badge tone="watch">Ending</Badge>}
        </div>
      </TD>
    </TR>
  )
}
