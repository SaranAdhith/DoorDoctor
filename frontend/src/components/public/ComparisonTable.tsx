import { Check, Minus, X } from 'lucide-react'

import { cn } from '../../lib/cn'

/**
 * How DoorDoctor differs from the alternatives a family is actually weighing.
 *
 * The columns are *approaches*, never named competitors. Comparing mechanisms
 * is something we can defend line by line; a grid with another company's name
 * down one side is a claim about their product that we cannot keep accurate and
 * would have to defend.
 *
 * The `no smartphone needed` row exists on purpose: the alternatives win it too.
 * A comparison where one column is a full sweep of ticks is read as marketing
 * and discounted whole — the honest row is what makes the other six credible.
 */

type Level = 'yes' | 'partial' | 'no'

interface Capability {
  label: string
  /** DoorDoctor, then the three alternatives, in column order. */
  values: [Level, Level, Level, Level]
  /** Shown under the row label — why the answer is what it is. */
  note?: string
}

const COLUMNS = [
  'DoorDoctor',
  'Phoning to check in',
  'A live-in attendant',
  'A wearable monitor',
] as const

const CAPABILITIES: Capability[] = [
  {
    label: 'Someone qualified sees them in person',
    values: ['yes', 'no', 'partial', 'no'],
    note: 'An RN or ANM on a schedule, versus an attendant who is present but usually not clinically trained.',
  },
  {
    label: 'Vitals recorded and kept over time',
    values: ['yes', 'no', 'partial', 'partial'],
    note: 'A device records what it measures. A nurse records blood pressure, pulse, sugar, oxygen, temperature and weight into one history.',
  },
  {
    label: 'Every dose marked given, skipped or refused',
    values: ['yes', 'no', 'partial', 'no'],
    note: 'Supervision that is remembered is not supervision that can be reviewed three weeks later.',
  },
  {
    label: 'Readings checked against ranges set for that patient',
    values: ['yes', 'no', 'no', 'partial'],
    note: 'A consumer device compares against a general population. Thresholds here are configured per patient by clinical staff.',
  },
  {
    label: 'Anything out of range is escalated and worked until it is closed',
    values: ['yes', 'no', 'no', 'no'],
    note: 'An alert reaches the family and the care team together, and stays open until an admin records what was done about it.',
  },
  {
    label: 'The whole record is visible to family from anywhere',
    values: ['yes', 'no', 'no', 'partial'],
    note: 'Visits, trends, doses, alerts and how each was resolved — readable at 2am in another timezone.',
  },
  {
    label: 'Works without your parents using an app or a smartphone',
    values: ['yes', 'yes', 'yes', 'no'],
    note: 'Nothing is asked of the patient. The record is made for them, by the person in the room.',
  },
]

const MARK: Record<Level, { icon: typeof Check; className: string; label: string }> = {
  yes: { icon: Check, className: 'bg-status-good-bg text-status-good', label: 'Yes' },
  partial: { icon: Minus, className: 'bg-status-watch-bg text-status-watch', label: 'Partly' },
  no: { icon: X, className: 'bg-surface-sunken text-text-muted', label: 'No' },
}

function Mark({ level }: { level: Level }) {
  const { icon: Icon, className, label } = MARK[level]
  return (
    <span
      className={cn('inline-flex h-8 w-8 items-center justify-center rounded-full', className)}
      title={label}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </span>
  )
}

export function ComparisonTable() {
  return (
    <div className="mt-10">
      {/* Desktop: one grid, DoorDoctor's column tinted so the eye keeps its place. */}
      <div className="hidden overflow-x-auto lg:block">
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">
            DoorDoctor compared with phoning to check in, a live-in attendant and a wearable monitor
          </caption>
          <thead>
            <tr>
              <th scope="col" className="w-[38%] pb-4 pr-4 align-bottom">
                <span className="text-caption font-semibold uppercase tracking-[0.12em] text-brand-700">
                  What you want
                </span>
              </th>
              {COLUMNS.map((column, i) => (
                <th
                  key={column}
                  scope="col"
                  className={cn(
                    'px-4 pb-4 align-bottom text-body font-bold',
                    i === 0
                      ? 'rounded-t-xl bg-brand-50 pt-4 text-brand-700'
                      : 'text-text-secondary',
                  )}
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {CAPABILITIES.map((capability, rowIndex) => (
              <tr key={capability.label} className="border-t border-border-subtle align-top">
                <th scope="row" className="py-5 pr-4 font-normal">
                  <span className="block text-body font-semibold text-text-primary">
                    {capability.label}
                  </span>
                  {capability.note && (
                    <span className="mt-1 block text-small text-text-secondary">
                      {capability.note}
                    </span>
                  )}
                </th>
                {capability.values.map((level, i) => (
                  <td
                    key={`${capability.label}-${i}`}
                    className={cn(
                      'px-4 py-5',
                      // The tint runs the height of the column, so it closes at
                      // the last row rather than being cut off square.
                      i === 0 && 'bg-brand-50',
                      i === 0 && rowIndex === CAPABILITIES.length - 1 && 'rounded-b-xl',
                    )}
                  >
                    <Mark level={level} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Below lg the same data stacks: a seven-column table on a phone is a
          horizontal scrollbar nobody drags. */}
      <div className="space-y-4 lg:hidden">
        {CAPABILITIES.map((capability) => (
          <div
            key={capability.label}
            className="rounded-2xl border border-border-subtle bg-surface-raised p-5"
          >
            <p className="text-body font-semibold text-text-primary">{capability.label}</p>
            {capability.note && (
              <p className="mt-1 text-small text-text-secondary">{capability.note}</p>
            )}
            <dl className="mt-4 space-y-2">
              {capability.values.map((level, i) => (
                <div
                  key={`${capability.label}-m-${i}`}
                  className={cn(
                    'flex items-center justify-between gap-3 rounded-lg px-3 py-2',
                    i === 0 ? 'bg-brand-50' : 'bg-surface',
                  )}
                >
                  <dt
                    className={cn(
                      'text-small',
                      i === 0 ? 'font-semibold text-brand-700' : 'text-text-secondary',
                    )}
                  >
                    {COLUMNS[i]}
                  </dt>
                  <dd className="shrink-0">
                    <Mark level={level} />
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </div>
  )
}
