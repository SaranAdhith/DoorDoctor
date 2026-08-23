import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { SafetyScoreCard } from '../components/clinical/SafetyScoreCard'
import type { SafetyComponent, SafetyScore } from '../types'

/**
 * The score is only defensible if the breakdown is reachable and honest, so
 * these tests are about what the card *says*, not how it looks.
 */

function component(overrides: Partial<SafetyComponent> = {}): SafetyComponent {
  return {
    key: 'vital_stability',
    label: 'Readings in range',
    blurb: 'How often recorded checks sat inside the range set for this patient.',
    weight: 30,
    value: 0.9,
    points: 27,
    detail: '18 of 20 checks were inside the range set for this patient.',
    has_data: true,
    ...overrides,
  }
}

function score(overrides: Partial<SafetyScore> = {}): SafetyScore {
  return {
    patient_id: 1,
    available: true,
    score: 84,
    band: 'steady',
    band_label: 'Steady',
    band_tone: 'good',
    band_blurb: 'Things have been going well.',
    window_days: 30,
    covered_weight: 100,
    total_weight: 100,
    previous_score: 80,
    delta: 4,
    components: [component()],
    calculated_at: '2026-08-23T09:00:00',
    unavailable_reason: null,
    ...overrides,
  }
}

describe('SafetyScoreCard', () => {
  it('shows the score, the band and the scale it is out of', () => {
    render(<SafetyScoreCard score={score()} />)
    expect(screen.getByText('84')).toBeInTheDocument()
    expect(screen.getByText('/ 100')).toBeInTheDocument()
    expect(screen.getByText('Steady')).toBeInTheDocument()
  })

  it('keeps the breakdown one click away, not one screen away', () => {
    render(<SafetyScoreCard score={score()} />)
    expect(screen.queryByText(/18 of 20 checks/)).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /what makes up this score/i }))

    expect(screen.getByText('Readings in range')).toBeInTheDocument()
    expect(screen.getByText(/18 of 20 checks/)).toBeInTheDocument()
    expect(screen.getByText(/27 of 30/)).toBeInTheDocument()
  })

  it('says a component was not counted rather than showing it as zero', () => {
    render(
      <SafetyScoreCard
        score={score({
          covered_weight: 90,
          components: [
            component(),
            component({
              key: 'mood',
              label: 'Mood check',
              weight: 10,
              value: null,
              points: null,
              has_data: false,
              detail: 'No mood check has been recorded recently.',
            }),
          ],
        })}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /what makes up this score/i }))
    expect(screen.getByText('not counted')).toBeInTheDocument()
    // And never as a zero score, which would read as "worst possible mood".
    expect(screen.queryByText('0 of 10')).not.toBeInTheDocument()
  })

  it('says out loud when the score covers only part of the scale', () => {
    render(<SafetyScoreCard score={score({ covered_weight: 75 })} />)
    expect(screen.getByText(/Based on 75 of 100 points/)).toBeInTheDocument()
    expect(screen.getByText(/left out rather than counted against/)).toBeInTheDocument()
  })

  it('does not claim full coverage when it has it', () => {
    render(<SafetyScoreCard score={score()} />)
    expect(screen.queryByText(/Based on/)).not.toBeInTheDocument()
  })

  it('refuses to show a number when there is not enough data', () => {
    render(
      <SafetyScoreCard
        score={score({
          available: false,
          score: null,
          band: null,
          band_label: null,
          band_tone: null,
          covered_weight: 15,
          unavailable_reason: 'There is not enough recorded care yet to publish a safety score.',
        })}
      />,
    )
    expect(screen.getByText(/not enough recorded care/)).toBeInTheDocument()
    expect(screen.queryByText('/ 100')).not.toBeInTheDocument()
  })

  it('distinguishes "no earlier score" from "no change"', () => {
    render(<SafetyScoreCard score={score({ delta: null, previous_score: null })} />)
    expect(screen.getByText(/No earlier score to compare with yet/)).toBeInTheDocument()
    expect(screen.queryByText(/Unchanged/)).not.toBeInTheDocument()
  })

  it('reports a fall as a fall', () => {
    render(<SafetyScoreCard score={score({ score: 68, delta: -12, previous_score: 80 })} />)
    expect(screen.getByText(/down 12/)).toBeInTheDocument()
    expect(screen.getByText(/from 80/)).toBeInTheDocument()
  })
})
