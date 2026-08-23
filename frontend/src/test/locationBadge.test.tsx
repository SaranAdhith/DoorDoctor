import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { LocationBadge, formatDistance } from '../components/trust'

/**
 * §4.11's three classifications, as a family and a nurse read them.
 *
 * The load-bearing assertion is the third one: `unavailable` must not be
 * dressed as a fault. "We do not know where the nurse was" is a true sentence,
 * and colouring it like an alert would train a family to read a missing GPS fix
 * as a missing nurse.
 */
describe('LocationBadge', () => {
  it('shows the measured distance beside a verified check-in', () => {
    render(<LocationBadge status="verified" distanceM={34} />)
    expect(screen.getByText(/Location verified/)).toBeInTheDocument()
    expect(screen.getByText(/34 m/)).toBeInTheDocument()
  })

  it('says how far away an out-of-range check-in was', () => {
    render(<LocationBadge status="out_of_range" distanceM={1240} />)
    expect(screen.getByText(/Away from home/)).toBeInTheDocument()
    expect(screen.getByText(/1\.2 km/)).toBeInTheDocument()
  })

  it('renders an unavailable check-in as a plain statement, not a warning', () => {
    const { container } = render(<LocationBadge status="unavailable" />)
    expect(screen.getByText(/Location not recorded/)).toBeInTheDocument()
    // No distance is invented for a fix that never existed.
    expect(container.textContent).not.toMatch(/\d\s?m/)
  })

  it('never claims a distance it was not given', () => {
    render(<LocationBadge status="verified" distanceM={null} />)
    expect(screen.getByText('Location verified')).toBeInTheDocument()
  })

  it('formats metres below a kilometre and kilometres above it', () => {
    expect(formatDistance(8)).toBe('8 m')
    expect(formatDistance(999)).toBe('999 m')
    expect(formatDistance(1000)).toBe('1.0 km')
    expect(formatDistance(2450)).toBe('2.5 km')
  })
})
