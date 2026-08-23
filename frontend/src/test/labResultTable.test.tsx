import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { LabResultTable } from '../components/clinical/LabResultTable'
import type { LabResult } from '../types'

/**
 * The range column is the point. A value flagged "high" with no range beside it
 * is a diagnosis by implication.
 */

function result(overrides: Partial<LabResult> = {}): LabResult {
  return {
    id: 1,
    analyte_code: 'fasting_glucose',
    label: 'Fasting blood sugar',
    value: 148,
    unit: 'mg/dL',
    ref_low: 70,
    ref_high: 110,
    flag: 'high',
    is_abnormal: true,
    description: 'Fasting blood sugar 148 mg/dL (expected 70–110 mg/dL)',
    ...overrides,
  }
}

describe('LabResultTable', () => {
  it('shows every value beside the range it was judged against', () => {
    render(<LabResultTable results={[result()]} />)
    expect(screen.getByText('Fasting blood sugar')).toBeInTheDocument()
    expect(screen.getByText('148')).toBeInTheDocument()
    expect(screen.getByText('70–110 mg/dL')).toBeInTheDocument()
    expect(screen.getByText('Above range')).toBeInTheDocument()
  })

  it('never shows a flag without its range', () => {
    render(
      <LabResultTable
        results={[
          result(),
          result({ id: 2, analyte_code: 'hba1c', label: 'HbA1c', value: 6.8, unit: '%', ref_low: null, ref_high: 5.7 }),
        ]}
      />,
    )
    expect(screen.getByText('up to 5.7 %')).toBeInTheDocument()
  })

  it('reads an in-range result as in range, not as an absence of finding', () => {
    render(<LabResultTable results={[result({ flag: 'normal', is_abnormal: false, value: 92 })]} />)
    expect(screen.getByText('In range')).toBeInTheDocument()
  })

  it('separates "no range configured" from "in range"', () => {
    render(
      <LabResultTable
        results={[result({ flag: 'unknown', is_abnormal: false, ref_low: null, ref_high: null })]}
      />,
    )
    expect(screen.getByText('No range set')).toBeInTheDocument()
    expect(screen.queryByText('In range')).not.toBeInTheDocument()
  })

  it('marks a critical result more strongly than a merely abnormal one', () => {
    render(<LabResultTable results={[result({ flag: 'critical_high', value: 400 })]} />)
    expect(screen.getByText('Well above range')).toBeInTheDocument()
  })
})
