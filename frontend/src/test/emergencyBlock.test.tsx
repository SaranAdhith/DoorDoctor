import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { escalationsApi } from '../api/clinical'
import { EmergencyBlock } from '../components/clinical/EmergencyBlock'

vi.mock('../api/clinical', () => ({
  escalationsApi: { emergency: vi.fn() },
}))

const emergency = vi.mocked(escalationsApi.emergency)

/**
 * 108 is the one string in this codebase worth duplicating, and this component
 * holds the only duplicate. These tests pin why: a screen that renders no
 * emergency number is worse than one that renders the number and nothing else.
 */
describe('EmergencyBlock', () => {
  beforeEach(() => {
    emergency.mockReset()
  })

  it('renders the served wording and ladder', async () => {
    emergency.mockResolvedValue({
      number: '108',
      title: 'In an emergency, call 108',
      body: 'DoorDoctor monitors and coordinates care. It is not an emergency service.',
      ladder: ['Call 108 for an ambulance', 'Contact the assigned nurse', 'Contact the DoorDoctor admin team'],
    })

    render(<EmergencyBlock />)

    await waitFor(() => expect(screen.getByText('In an emergency, call 108')).toBeInTheDocument())
    expect(screen.getByText(/not an emergency service/)).toBeInTheDocument()
    expect(screen.getByText(/Contact the assigned nurse/)).toBeInTheDocument()
  })

  it('still shows 108 when the API cannot be reached', async () => {
    emergency.mockRejectedValue(new Error('offline'))
    render(<EmergencyBlock />)
    await waitFor(() =>
      expect(screen.getByText('In an emergency, call 108')).toBeInTheDocument(),
    )
    expect(screen.getByText(/not an emergency service/)).toBeInTheDocument()
  })

  it('is a note, not an assertive live region', async () => {
    emergency.mockRejectedValue(new Error('offline'))
    render(<EmergencyBlock />)
    // An alert announced on every clinical page load makes a screen reader
    // unusable; this is standing guidance, not an event.
    await waitFor(() => expect(screen.getByRole('note')).toBeInTheDocument())
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('drops the body in compact mode but keeps the number', async () => {
    emergency.mockResolvedValue({
      number: '108',
      title: 'In an emergency, call 108',
      body: 'A long explanation that should not appear inline.',
      ladder: ['Call 108 for an ambulance'],
    })
    render(<EmergencyBlock compact />)
    await waitFor(() => expect(screen.getByText('In an emergency, call 108')).toBeInTheDocument())
    expect(screen.queryByText(/long explanation/)).not.toBeInTheDocument()
  })
})
