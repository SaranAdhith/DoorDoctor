import type { LabResult } from '../../types'
import { Badge, Table, TBody, TD, TH, THead, TR, TableWrap } from '../ui'
import type { BadgeTone } from '../ui'

/**
 * Lab results, each beside the range it was judged against (§4.2).
 *
 * The range column is not decoration. A value flagged "high" with no range next
 * to it is a diagnosis by implication; with the range shown, the flag is
 * arithmetic the reader can re-run. The backend stores the range on every
 * result for the same reason, so this column keeps working after somebody edits
 * `core/clinical.py`.
 */

const FLAG_LABELS: Record<string, string> = {
  normal: 'In range',
  low: 'Below range',
  high: 'Above range',
  critical_low: 'Well below range',
  critical_high: 'Well above range',
  unknown: 'No range set',
}

const FLAG_TONES: Record<string, BadgeTone> = {
  normal: 'good',
  low: 'watch',
  high: 'watch',
  critical_low: 'critical',
  critical_high: 'critical',
  unknown: 'neutral',
}

function formatRange(result: LabResult): string {
  const unit = result.unit ? ` ${result.unit}` : ''
  if (result.ref_low !== null && result.ref_high !== null) {
    return `${result.ref_low}–${result.ref_high}${unit}`
  }
  if (result.ref_high !== null) return `up to ${result.ref_high}${unit}`
  if (result.ref_low !== null) return `${result.ref_low}${unit} and above`
  return '—'
}

export function LabResultTable({ results }: { results: LabResult[] }) {
  return (
    <TableWrap>
      <Table>
        <THead>
          <TR>
            <TH>Test</TH>
            <TH numeric>Result</TH>
            <TH numeric>Expected range</TH>
            <TH>Reading</TH>
          </TR>
        </THead>
        <TBody>
          {results.map((result) => (
            <TR key={result.id}>
              <TD>{result.label}</TD>
              <TD numeric className="font-medium">
                {result.value}
                {result.unit && <span className="text-text-muted"> {result.unit}</span>}
              </TD>
              <TD numeric className="text-text-muted">
                {formatRange(result)}
              </TD>
              <TD>
                <Badge tone={FLAG_TONES[result.flag] ?? 'neutral'}>
                  {FLAG_LABELS[result.flag] ?? result.flag}
                </Badge>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </TableWrap>
  )
}
