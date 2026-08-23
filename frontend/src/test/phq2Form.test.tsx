import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { Phq2Form } from '../components/clinical/Phq2Form'
import type { ScreeningInstrument } from '../types'

const INSTRUMENT: ScreeningInstrument = {
  code: 'phq2',
  name: 'PHQ-2',
  preamble: 'Over the last 2 weeks, how often have you been bothered by the following problems?',
  questions: [
    'Little interest or pleasure in doing things',
    'Feeling down, depressed, or hopeless',
  ],
  answers: [
    { value: 0, label: 'Not at all' },
    { value: 1, label: 'Several days' },
    { value: 2, label: 'More than half the days' },
    { value: 3, label: 'Nearly every day' },
  ],
  max_total: 6,
  positive_cutoff: 3,
  cadence_days: 30,
  disclaimer: 'PHQ-2 is a two-question screen, not a diagnosis.',
}

describe('Phq2Form', () => {
  it('renders the instrument wording exactly as served', () => {
    render(<Phq2Form instrument={INSTRUMENT} onSubmit={vi.fn()} />)
    expect(screen.getByText(INSTRUMENT.preamble)).toBeInTheDocument()
    for (const question of INSTRUMENT.questions) {
      expect(screen.getByText(new RegExp(question))).toBeInTheDocument()
    }
  })

  it('shows the disclaimer before anything is answered', () => {
    render(<Phq2Form instrument={INSTRUMENT} onSubmit={vi.fn()} />)
    // A screening tool does its harm at the moment somebody answers it, not at
    // the moment they read the score.
    expect(screen.getByText(/not a diagnosis/)).toBeInTheDocument()
  })

  it('will not submit a partial screen', () => {
    const onSubmit = vi.fn()
    render(<Phq2Form instrument={INSTRUMENT} onSubmit={onSubmit} />)

    const submit = screen.getByRole('button', { name: /record mood check/i })
    expect(submit).toBeDisabled()

    fireEvent.click(screen.getAllByLabelText('Several days')[0])
    expect(submit).toBeDisabled()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits both answers in order', () => {
    const onSubmit = vi.fn()
    render(<Phq2Form instrument={INSTRUMENT} onSubmit={onSubmit} />)

    fireEvent.click(screen.getAllByLabelText('Nearly every day')[0])
    fireEvent.click(screen.getAllByLabelText('Not at all')[1])
    fireEvent.click(screen.getByRole('button', { name: /record mood check/i }))

    // (3, 0) and (1, 2) both total 3 and are not the same clinical picture.
    expect(onSubmit).toHaveBeenCalledWith([3, 0])
  })
})
