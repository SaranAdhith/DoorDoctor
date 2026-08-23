import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { OnboardingChecklist } from '../components/trust'
import type { OnboardingProgress } from '../types'

function progress(overrides: Partial<OnboardingProgress> = {}): OnboardingProgress {
  const steps = [
    {
      key: 'confirm_patient',
      label: "Check your relative's details",
      blurb: 'Their name, age and address.',
      path: '/family/dashboard',
      done: false,
      derived: false,
    },
    {
      key: 'care_circle',
      label: 'Add the people who should know',
      blurb: 'Anyone who should be told.',
      path: '/family/care-circle',
      done: false,
      derived: true,
    },
  ]
  return {
    patient_id: 1,
    steps,
    completed: 0,
    total: steps.length,
    complete: false,
    next_step: steps[0],
    ...overrides,
  }
}

function renderChecklist(data: OnboardingProgress, onAcknowledge = vi.fn()) {
  render(
    <MemoryRouter>
      <OnboardingChecklist progress={data} onAcknowledge={onAcknowledge} />
    </MemoryRouter>,
  )
  return onAcknowledge
}

/**
 * §4.15. The distinction the checklist is built on: a derived step completes
 * itself when the work is done, so offering a tick for one would invite somebody
 * to mark a thing done that is not.
 */
describe('OnboardingChecklist', () => {
  it('offers a tick only for the step that has nothing else to prove it', () => {
    renderChecklist(progress())
    expect(screen.getByRole('button', { name: /Looks right/ })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Looks right/ })).toHaveLength(1)
    expect(screen.getByRole('link', { name: 'Open' })).toHaveAttribute(
      'href',
      '/family/care-circle',
    )
  })

  it('acknowledges the step it was asked about', () => {
    const onAcknowledge = renderChecklist(progress())
    fireEvent.click(screen.getByRole('button', { name: /Looks right/ }))
    expect(onAcknowledge).toHaveBeenCalledWith('confirm_patient')
  })

  it('disappears once every step is done rather than sitting there ticked', () => {
    const { container } = render(
      <MemoryRouter>
        <OnboardingChecklist
          progress={progress({ complete: true, completed: 2 })}
          onAcknowledge={vi.fn()}
        />
      </MemoryRouter>,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
