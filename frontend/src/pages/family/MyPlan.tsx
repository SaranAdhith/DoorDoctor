import { useState } from 'react'
import { Check, Download, Gift, Minus, Sparkles } from 'lucide-react'

import { openInvoicePdf, invoicesApi, plansApi, referralsApi, subscriptionsApi } from '../../api/billing'
import { ApiError } from '../../api/client'
import { useAsync } from '../../hooks/useAsync'
import { formatDate } from '../../lib/format'
import { formatINR, formatPrice } from '../../lib/money'
import { entitlementLines, quotaTone, quotaValueText } from '../../lib/plan'
import type { BillingCycle, Invoice, Plan, Subscription } from '../../types'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Input,
  LoadingScreen,
  Modal,
  ProgressMeter,
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

const CYCLES = [
  { value: 'monthly' as const, label: 'Monthly' },
  { value: 'annual' as const, label: 'Annual · 2 months free' },
]

const INVOICE_TONES = {
  paid: 'good',
  issued: 'watch',
  draft: 'neutral',
  void: 'neutral',
} as const

export function MyPlan() {
  const { notify } = useToast()
  const [cycle, setCycle] = useState<BillingCycle>('monthly')
  const [confirming, setConfirming] = useState<Plan | null>(null)
  const [cancelling, setCancelling] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [busy, setBusy] = useState(false)

  const data = useAsync(async () => {
    const [subscription, plans, invoices, referrals] = await Promise.all([
      subscriptionsApi.mine(),
      plansApi.list('individual'),
      invoicesApi.list(),
      referralsApi.mine(),
    ])
    return { subscription, plans, invoices, referrals }
  }, [])

  if (data.loading) return <LoadingScreen label="Loading your plan" />
  if (data.error) return <ErrorState message={data.error} onRetry={() => void data.reload()} />
  if (!data.data) return null

  const { subscription, plans, invoices, referrals } = data.data

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true)
    try {
      await action()
      await data.reload({ quiet: true })
      notify(success, 'success')
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'Something went wrong.', 'error')
    } finally {
      setBusy(false)
      setConfirming(null)
      setCancelling(false)
    }
  }

  const outstanding = invoices.find((invoice) => invoice.status === 'issued')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 font-bold text-text-primary">My Plan</h1>
        <p className="mt-1 text-small text-text-secondary">
          What your family pays for, what it includes, and what you have used this month.
        </p>
      </div>

      <CurrentPlan subscription={subscription} outstanding={outstanding} />

      <div className="grid gap-6 lg:grid-cols-2">
        <Usage subscription={subscription} />
        <Included subscription={subscription} />
      </div>

      <Card
        title="Change plan"
        description="A change takes effect straight away. Whatever you have paid for and not used is credited to your next invoice."
        action={
          <SegmentedControl
            legend="Billing cycle"
            hideLegend
            value={cycle}
            options={CYCLES}
            onChange={setCycle}
          />
        }
      >
        <div className="grid gap-4 md:grid-cols-3">
          {plans.map((plan) => (
            <PlanOption
              key={plan.code}
              plan={plan}
              cycle={cycle}
              current={plan.code === subscription.plan.code && cycle === subscription.billing_cycle}
              onChoose={() => setConfirming(plan)}
            />
          ))}
        </div>
      </Card>

      <Referrals
        summary={referrals}
        email={inviteEmail}
        onEmail={setInviteEmail}
        busy={busy}
        onInvite={() =>
          run(async () => {
            await referralsApi.invite(inviteEmail)
            setInviteEmail('')
          }, 'Invitation sent.')
        }
      />

      <Invoices invoices={invoices} onDownload={(id) => void openInvoicePdf(id).catch(() => notify('The invoice could not be opened.', 'error'))} />

      <Card
        title="Cancel subscription"
        description="Care continues until the end of the period you have already paid for."
      >
        {subscription.cancel_at_period_end ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-small text-text-secondary">
              This plan ends on{' '}
              <strong className="text-text-primary">
                {formatDate(subscription.current_period_end)}
              </strong>
              . Nothing more will be charged.
            </p>
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => run(() => subscriptionsApi.resume(subscription.id), 'Your plan will continue.')}
            >
              Keep my plan
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-small text-text-secondary">
              Your nurse visits and monitoring stop when the current period ends.
            </p>
            <Button variant="ghost" onClick={() => setCancelling(true)}>
              Cancel my plan
            </Button>
          </div>
        )}
      </Card>

      <Modal
        open={confirming !== null}
        onClose={() => setConfirming(null)}
        title={`Move to ${confirming?.name ?? ''}?`}
        description={
          confirming
            ? `You will be billed ${formatPrice(
                (cycle === 'annual' ? confirming.annual_paise : confirming.monthly_paise) ?? 0,
                cycle,
              )} from today, and credited for the rest of your current period.`
            : undefined
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirming(null)}>
              Keep current plan
            </Button>
            <Button
              variant="accent"
              loading={busy}
              onClick={() =>
                confirming &&
                run(
                  () => subscriptionsApi.changePlan(subscription.id, confirming.code, cycle),
                  `You are now on ${confirming.name}.`,
                )
              }
            >
              Confirm change
            </Button>
          </>
        }
      >
        <p className="text-small text-text-secondary">
          Your care team, visit history and alerts are unchanged. Only what is included changes.
        </p>
      </Modal>

      <Modal
        open={cancelling}
        onClose={() => setCancelling(false)}
        title="Cancel your DoorDoctor plan?"
        description={`Visits and monitoring continue until ${formatDate(subscription.current_period_end)}.`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCancelling(false)}>
              Keep my plan
            </Button>
            <Button
              variant="danger"
              loading={busy}
              onClick={() =>
                run(
                  () => subscriptionsApi.cancel(subscription.id),
                  'Your plan will end at the close of this period.',
                )
              }
            >
              Cancel at period end
            </Button>
          </>
        }
      >
        <p className="text-small text-text-secondary">
          You can undo this at any time before {formatDate(subscription.current_period_end)}.
        </p>
      </Modal>
    </div>
  )
}

function CurrentPlan({
  subscription,
  outstanding,
}: {
  subscription: Subscription
  outstanding: Invoice | undefined
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatTile
        label="Current plan"
        value={subscription.plan.name}
        hint={formatPrice(subscription.period_price_paise, subscription.billing_cycle)}
      />
      <StatTile
        label={subscription.cancel_at_period_end ? 'Ends on' : 'Renews on'}
        value={formatDate(subscription.current_period_end)}
        tone={subscription.cancel_at_period_end ? 'watch' : 'default'}
        hint={subscription.cancel_at_period_end ? 'Cancellation scheduled' : 'Billed automatically'}
      />
      <StatTile
        label="Next payment"
        value={outstanding ? formatINR(outstanding.total_paise) : '--'}
        hint={outstanding ? `Due ${formatDate(outstanding.due_at)}` : 'Nothing outstanding'}
      />
      <StatTile
        label="Account credit"
        value={formatINR(subscription.credit_balance_paise)}
        tone={subscription.credit_balance_paise > 0 ? 'good' : 'default'}
        hint={
          subscription.credit_balance_paise > 0
            ? 'Applied to your next invoice'
            : `${subscription.months_to_loyalty_reward} months to your next free month`
        }
      />
    </div>
  )
}

function Usage({ subscription }: { subscription: Subscription }) {
  return (
    <Card
      title="This period"
      description={`${formatDate(subscription.current_period_start)} — ${formatDate(subscription.current_period_end)}`}
    >
      <div className="space-y-4">
        {subscription.quotas.map((quota) => (
          <ProgressMeter
            key={quota.quota}
            label={quota.label}
            showLabel
            valueText={quotaValueText(quota)}
            value={quota.used}
            max={quota.unlimited ? Math.max(quota.used, 1) : quota.limit ?? 1}
            tone={quotaTone(quota)}
          />
        ))}
      </div>
      <p className="mt-4 text-caption text-text-muted">
        Allowances reset every {subscription.quotas[0]?.period ?? 'month'}. Lab panels reset yearly.
      </p>
    </Card>
  )
}

function Included({ subscription }: { subscription: Subscription }) {
  return (
    <Card title="What your plan includes">
      <dl className="space-y-2.5">
        {entitlementLines(subscription.plan).map((line) => (
          <div key={line.label} className="flex items-start justify-between gap-3 text-small">
            <dt className="flex items-center gap-2 text-text-secondary">
              {line.included ? (
                <Check className="h-4 w-4 shrink-0 text-status-good" aria-hidden="true" />
              ) : (
                <Minus className="h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
              )}
              {line.label}
            </dt>
            <dd
              className={
                line.included
                  ? 'text-right font-medium text-text-primary'
                  : 'text-right text-text-muted'
              }
            >
              {line.value}
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}

function PlanOption({
  plan,
  cycle,
  current,
  onChoose,
}: {
  plan: Plan
  cycle: BillingCycle
  current: boolean
  onChoose: () => void
}) {
  const price = cycle === 'annual' ? plan.annual_paise : plan.monthly_paise

  return (
    <article
      className={`rounded-2xl border p-5 ${
        current ? 'border-brand-500 bg-brand-50/40' : 'border-border-subtle bg-surface-raised'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-body font-semibold text-text-primary">{plan.name}</h3>
        {plan.recommended && !current && (
          <Badge tone="info">
            <Sparkles className="h-3 w-3" aria-hidden="true" />
            Recommended
          </Badge>
        )}
        {current && <Badge tone="good">Current</Badge>}
      </div>

      <p className="tnum mt-2 text-h2 font-bold text-text-primary">
        {price === null ? '--' : formatPrice(price, cycle)}
      </p>
      <p className="mt-1 text-caption text-text-muted">{plan.tagline}</p>

      <Button
        className="mt-4"
        fullWidth
        variant={current ? 'subtle' : plan.recommended ? 'accent' : 'ghost'}
        disabled={current || price === null}
        onClick={onChoose}
      >
        {current ? 'Your plan' : price === null ? 'Not available' : `Switch to ${plan.name}`}
      </Button>
    </article>
  )
}

function Referrals({
  summary,
  email,
  onEmail,
  onInvite,
  busy,
}: {
  summary: { code: string; reward_paise: number; friend_credit_paise: number; total_earned_paise: number; joined_count: number; pending_count: number; referrals: Array<{ id: number; email: string; status: string; reward_paise: number }> }
  email: string
  onEmail: (value: string) => void
  onInvite: () => void
  busy: boolean
}) {
  return (
    <Card
      title="Refer a family"
      description={`They get ${formatINR(summary.friend_credit_paise)} off their first month. You get a free month when they join and pay.`}
    >
      <div className="grid gap-5 md:grid-cols-2">
        <div>
          <p className="text-caption font-semibold uppercase tracking-wide text-text-secondary">
            Your referral code
          </p>
          <p className="tnum mt-1 text-h2 font-bold tracking-wide text-brand-700">{summary.code}</p>

          <div className="mt-4 flex flex-wrap items-end gap-2">
            <Input
              label="Invite by email"
              type="email"
              className="min-w-[14rem] flex-1"
              value={email}
              placeholder="their-email@example.com"
              onChange={(event) => onEmail(event.target.value)}
            />
            <Button variant="accent" disabled={busy || !email} onClick={onInvite}>
              <Gift className="h-4 w-4" aria-hidden="true" />
              Send invite
            </Button>
          </div>
        </div>

        <div>
          <div className="flex gap-6">
            <div>
              <p className="text-caption uppercase tracking-wide text-text-secondary">Earned</p>
              <p className="tnum text-h2 font-bold text-status-good">
                {formatINR(summary.total_earned_paise)}
              </p>
            </div>
            <div>
              <p className="text-caption uppercase tracking-wide text-text-secondary">Joined</p>
              <p className="tnum text-h2 font-bold text-text-primary">{summary.joined_count}</p>
            </div>
            <div>
              <p className="text-caption uppercase tracking-wide text-text-secondary">Pending</p>
              <p className="tnum text-h2 font-bold text-text-primary">{summary.pending_count}</p>
            </div>
          </div>

          {summary.referrals.length > 0 && (
            <ul className="mt-4 space-y-2">
              {summary.referrals.slice(0, 4).map((referral) => (
                <li key={referral.id} className="flex items-center justify-between gap-3 text-small">
                  <span className="truncate text-text-secondary">{referral.email}</span>
                  <Badge tone={referral.status === 'rewarded' ? 'good' : 'neutral'}>
                    {referral.status}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Card>
  )
}

function Invoices({
  invoices,
  onDownload,
}: {
  invoices: Invoice[]
  onDownload: (id: number) => void
}) {
  return (
    <Card title="Invoices" flush>
      {invoices.length === 0 ? (
        <div className="p-5">
          <EmptyState title="No invoices yet" description="Your first invoice appears when your plan renews." />
        </div>
      ) : (
        <TableWrap>
          <Table>
            <THead>
              <TR>
                <TH>Invoice</TH>
                <TH>Period</TH>
                <TH numeric>Amount</TH>
                <TH>Status</TH>
                <TH>PDF</TH>
              </TR>
            </THead>
            <TBody>
              {invoices.map((invoice) => (
                <TR key={invoice.id}>
                  <TD>
                    <span className="font-medium text-text-primary">{invoice.number}</span>
                    <span className="block text-caption text-text-muted">
                      Issued {formatDate(invoice.issued_at)}
                    </span>
                  </TD>
                  <TD>
                    <span className="text-text-secondary">
                      {formatDate(invoice.period_start)} — {formatDate(invoice.period_end)}
                    </span>
                  </TD>
                  <TD numeric>
                    <span className="font-semibold text-text-primary">
                      {formatINR(invoice.total_paise)}
                    </span>
                    {invoice.credit_paise > 0 && (
                      <span className="block text-caption text-status-good">
                        {formatINR(invoice.credit_paise)} credit applied
                      </span>
                    )}
                  </TD>
                  <TD>
                    <Badge tone={INVOICE_TONES[invoice.status]}>{invoice.status}</Badge>
                  </TD>
                  <TD>
                    <Button size="sm" variant="ghost" onClick={() => onDownload(invoice.id)}>
                      <Download className="h-4 w-4" aria-hidden="true" />
                      <span className="sr-only">Download invoice {invoice.number}</span>
                    </Button>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </TableWrap>
      )}
    </Card>
  )
}
