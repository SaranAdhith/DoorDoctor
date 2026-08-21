import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AdherenceCard } from '../components/cards/AdherenceCard'

describe('AdherenceCard', () => {
  it('shows the adherence percentage and dose breakdown', () => {
    render(
      <AdherenceCard
        adherence={{ percentage: 87, administered: 13, skipped: 1, refused: 1, total: 15 }}
      />,
    )
    expect(screen.getByText('87%')).toBeInTheDocument()
    expect(screen.getByText('13 of 15 logged doses')).toBeInTheDocument()
  })

  it('shows "No data" instead of 0% when nothing has been logged', () => {
    render(
      <AdherenceCard adherence={{ percentage: null, administered: 0, skipped: 0, refused: 0, total: 0 }} />,
    )
    expect(screen.getByText('No data')).toBeInTheDocument()
    expect(screen.queryByText('0%')).not.toBeInTheDocument()
  })
})
