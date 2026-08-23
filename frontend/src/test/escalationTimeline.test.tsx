import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { EscalationTimeline } from '../components/clinical/EscalationTimeline'
import type { EscalationStep } from '../types'

/**
 * The one thing this component must not do is imply a queue. Steps sharing a
 * sequence went out at the same moment, and rendering them as a sequence would
 * tell a family the fourth person was contacted only after the third.
 */

function step(overrides: Partial<EscalationStep> = {}): EscalationStep {
  return {
    id: 1,
    sequence: 1,
    actor: 'Family',
    channel: 'sms',
    target: 'Rajesh Kumar',
    recipient_user_id: 2,
    status: 'simulated',
    detail: 'Family contacted on sms.',
    occurred_at: '2026-08-23T09:00:00',
    ...overrides,
  }
}

describe('EscalationTimeline', () => {
  it('says explicitly when several contacts went out together', () => {
    render(
      <EscalationTimeline
        steps={[
          step({ id: 1, actor: 'Family', channel: 'sms' }),
          step({ id: 2, actor: 'Family', channel: 'email' }),
          step({ id: 3, actor: 'Admin', channel: 'sms', target: 'Sneha Bhaskar' }),
        ]}
      />,
    )
    // The visual grouping alone is a convention the reader never agreed to.
    expect(screen.getByText('3 contacts at the same time')).toBeInTheDocument()
  })

  it('does not label a lone contact as simultaneous', () => {
    render(<EscalationTimeline steps={[step()]} />)
    expect(screen.queryByText(/at the same time/)).not.toBeInTheDocument()
  })

  it('groups by sequence rather than listing every step separately', () => {
    render(
      <EscalationTimeline
        steps={[
          step({ id: 1, sequence: 0, actor: 'Family', channel: 'phone', target: '108' }),
          step({ id: 2, sequence: 1, actor: 'Family' }),
          step({ id: 3, sequence: 1, actor: 'Admin', target: 'Sneha Bhaskar' }),
        ]}
      />,
    )
    expect(screen.getAllByRole('listitem').length).toBeGreaterThan(0)
    expect(screen.getByText('2 contacts at the same time')).toBeInTheDocument()
    expect(screen.getByText(/108/)).toBeInTheDocument()
  })

  it('shows the emergency rung as advisory, with its wording intact', () => {
    render(
      <EscalationTimeline
        steps={[
          step({
            id: 1,
            sequence: 0,
            actor: 'Family',
            channel: 'phone',
            target: '108',
            status: 'skipped',
            detail:
              'If this is an emergency, call 108 for an ambulance. DoorDoctor does not place this call for you.',
          }),
        ]}
      />,
    )
    expect(screen.getByText(/DoorDoctor does not place this call for you/)).toBeInTheDocument()
  })

  it('renders an empty timeline honestly', () => {
    render(<EscalationTimeline steps={[]} />)
    expect(screen.getByText(/Nothing has been recorded yet/)).toBeInTheDocument()
  })
})
