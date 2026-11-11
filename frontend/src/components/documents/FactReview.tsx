import { Check, Pencil, RotateCcw, X } from 'lucide-react'
import { useState } from 'react'

import type { ExtractedFact, FactAction, FactFields, FactKind, FactStatus } from '../../types/intelligence'
import { Badge, Button, Input, Select, type BadgeTone } from '../ui'

/**
 * Phase 12, Stage 2 — one proposed fact, and the admin's decision on it.
 *
 * The layout puts the evidence next to the claim: the exact page text a fact
 * came from (`source_quote`) and where it came from (a table cell, the AI, or a
 * person) sit under the value, so the reviewer can check "8.1" against the line
 * it was read from without hunting through the page.
 */

export const FACT_KIND_LABELS: Record<FactKind, string> = {
  lab_value: 'Lab value',
  vital_sign: 'Vital sign',
  medication: 'Medicine',
  diagnosis: 'Diagnosis / impression',
  allergy: 'Allergy',
  instruction: 'Instruction',
  other: 'Other',
}

const STATUS: Record<FactStatus, { label: string; tone: BadgeTone }> = {
  proposed: { label: 'Needs a decision', tone: 'info' },
  confirmed: { label: 'Confirmed', tone: 'neutral' },
  edited: { label: 'Corrected', tone: 'neutral' },
  added: { label: 'Added by hand', tone: 'neutral' },
  rejected: { label: 'Rejected', tone: 'neutral' },
}

const SOURCE: Record<string, string> = {
  table: 'Read from a table',
  llm: 'Suggested by AI',
  manual: 'Entered by an admin',
}

function formatRange(low: number | null | undefined, high: number | null | undefined): string {
  if (low != null && high != null) return `${low} – ${high}`
  if (high != null) return `up to ${high}`
  if (low != null) return `above ${low}`
  return ''
}

export function FactValue({ fact }: { fact: Pick<ExtractedFact, 'value_text' | 'unit' | 'ref_low' | 'ref_high' | 'out_of_range'> }) {
  const range = formatRange(fact.ref_low, fact.ref_high)
  const showUnit = fact.unit && !fact.value_text.includes(fact.unit)
  return (
    <span className="text-body text-text-primary">
      <span className="tnum font-medium">{fact.value_text || '—'}</span>
      {showUnit ? ` ${fact.unit}` : ''}
      {range && <span className="text-small text-text-muted"> (range {range})</span>}
      {fact.out_of_range && (
        <Badge tone="watch" className="ml-2">
          Outside range
        </Badge>
      )}
    </span>
  )
}

// --- the form, shared by "edit" and "add" ------------------------------------------

const numberOrNull = (value: string): number | null => {
  const trimmed = value.trim()
  if (!trimmed) return null
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

export function FactForm({
  initial,
  submitLabel,
  busy,
  onSubmit,
  onCancel,
}: {
  initial?: Partial<ExtractedFact>
  submitLabel: string
  busy?: boolean
  onSubmit: (fields: FactFields & { label: string }) => void
  onCancel: () => void
}) {
  const [kind, setKind] = useState<FactKind>(initial?.kind ?? 'other')
  const [label, setLabel] = useState(initial?.label ?? '')
  const [valueText, setValueText] = useState(initial?.value_text ?? '')
  const [valueNum, setValueNum] = useState(initial?.value_num != null ? String(initial.value_num) : '')
  const [unit, setUnit] = useState(initial?.unit ?? '')
  const [refLow, setRefLow] = useState(initial?.ref_low != null ? String(initial.ref_low) : '')
  const [refHigh, setRefHigh] = useState(initial?.ref_high != null ? String(initial.ref_high) : '')
  const [pageNo, setPageNo] = useState(initial?.page_no != null ? String(initial.page_no) : '')

  return (
    <form
      className="space-y-3 rounded-md bg-surface-sunken p-3"
      onSubmit={(event) => {
        event.preventDefault()
        if (!label.trim()) return
        onSubmit({
          kind,
          label: label.trim(),
          value_text: valueText.trim(),
          value_num: numberOrNull(valueNum),
          unit: unit.trim(),
          ref_low: numberOrNull(refLow),
          ref_high: numberOrNull(refHigh),
          page_no: pageNo.trim() ? Number(pageNo) : null,
        })
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Select label="Kind" value={kind} onChange={(e) => setKind(e.target.value as FactKind)}>
          {(Object.keys(FACT_KIND_LABELS) as FactKind[]).map((k) => (
            <option key={k} value={k}>
              {FACT_KIND_LABELS[k]}
            </option>
          ))}
        </Select>
        <Input label="What it is" value={label} maxLength={120} required onChange={(e) => setLabel(e.target.value)} />
        <Input
          label="Value as written"
          value={valueText}
          maxLength={200}
          placeholder="e.g. 8.1, 500 mg 1-0-1"
          onChange={(e) => setValueText(e.target.value)}
        />
        <Input label="Number (if any)" inputMode="decimal" value={valueNum} onChange={(e) => setValueNum(e.target.value)} />
        <Input label="Unit" value={unit} maxLength={30} onChange={(e) => setUnit(e.target.value)} />
        <Input label="Page" inputMode="numeric" value={pageNo} onChange={(e) => setPageNo(e.target.value)} />
        <Input label="Range from" inputMode="decimal" value={refLow} onChange={(e) => setRefLow(e.target.value)} />
        <Input label="Range to" inputMode="decimal" value={refHigh} onChange={(e) => setRefHigh(e.target.value)} />
      </div>
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={busy || !label.trim()}>
          {submitLabel}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

// --- one fact ------------------------------------------------------------------------

export function FactRow({
  fact,
  locked,
  onDecide,
}: {
  fact: ExtractedFact
  /** The document is verified or rejected: show the decision, offer nothing. */
  locked: boolean
  onDecide: (action: FactAction, changes?: FactFields) => Promise<void>
}) {
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)
  const status = STATUS[fact.status]
  const rejected = fact.status === 'rejected'

  async function run(action: FactAction, changes?: FactFields) {
    setBusy(true)
    try {
      await onDecide(action, changes)
      setEditing(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className={`space-y-2 py-3 ${rejected ? 'opacity-60' : ''}`} data-testid={`fact-${fact.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className={`text-small font-semibold text-text-primary ${rejected ? 'line-through' : ''}`}>
            {fact.label}
            <span className="ml-2 font-normal text-text-muted">{FACT_KIND_LABELS[fact.kind]}</span>
          </p>
          <FactValue fact={fact} />
        </div>
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>

      <p className="text-caption text-text-muted">
        {fact.source ? SOURCE[fact.source] : ''}
        {fact.page_no ? ` · page ${fact.page_no}` : ''}
        {fact.source_quote ? (
          <>
            {' · from: '}
            <q className="text-text-secondary">{fact.source_quote}</q>
          </>
        ) : null}
      </p>
      {fact.original && (
        <p className="text-caption text-text-muted">
          Originally read as: <span className="text-text-secondary">{fact.original.label}</span>{' '}
          <span className="tnum text-text-secondary">{fact.original.value_text}</span>
          {fact.original.unit ? ` ${fact.original.unit}` : ''}
        </p>
      )}

      {editing ? (
        <FactForm
          initial={fact}
          submitLabel="Save correction"
          busy={busy}
          onCancel={() => setEditing(false)}
          onSubmit={(fields) => void run('edit', fields)}
        />
      ) : (
        !locked && (
          <div className="flex flex-wrap gap-2">
            {fact.status === 'proposed' ? (
              <>
                <Button size="sm" onClick={() => void run('confirm')} disabled={busy}>
                  <Check className="h-4 w-4" aria-hidden /> Confirm
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setEditing(true)} disabled={busy}>
                  <Pencil className="h-4 w-4" aria-hidden /> Correct
                </Button>
                <Button size="sm" variant="subtle" onClick={() => void run('reject')} disabled={busy}>
                  <X className="h-4 w-4" aria-hidden /> Reject
                </Button>
              </>
            ) : (
              <>
                {fact.status !== 'rejected' && (
                  <Button size="sm" variant="ghost" onClick={() => setEditing(true)} disabled={busy}>
                    <Pencil className="h-4 w-4" aria-hidden /> Correct
                  </Button>
                )}
                {fact.source !== 'manual' ? (
                  <Button size="sm" variant="subtle" onClick={() => void run('reopen')} disabled={busy}>
                    <RotateCcw className="h-4 w-4" aria-hidden /> Undo decision
                  </Button>
                ) : (
                  fact.status !== 'rejected' && (
                    <Button size="sm" variant="subtle" onClick={() => void run('reject')} disabled={busy}>
                      <X className="h-4 w-4" aria-hidden /> Remove
                    </Button>
                  )
                )}
              </>
            )}
          </div>
        )
      )}
    </li>
  )
}
