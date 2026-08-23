import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { CredentialList } from '../components/trust'
import type { NurseCredential } from '../types'

const verified: NurseCredential = {
  id: 1,
  kind: 'nursing_registration',
  title: 'Registered Nurse',
  issuing_body: 'Karnataka State Nursing Council',
  verified_at: '2026-03-12T12:00:00',
  verified_by_name: 'Priya Raghavan',
  expires_on: '2032-01-01',
  expired: false,
}

/**
 * §4.10's whole point: a credential is checkable, and the check has a name on it.
 */
describe('CredentialList', () => {
  it('names who verified the credential and when', () => {
    render(<CredentialList credentials={[verified]} />)
    expect(screen.getByText('Registered Nurse')).toBeInTheDocument()
    expect(screen.getByText('Karnataka State Nursing Council')).toBeInTheDocument()
    expect(screen.getByText(/Checked by Priya Raghavan/)).toBeInTheDocument()
  })

  it('never renders a registration number', () => {
    // The family projection does not contain the field at all — this asserts the
    // component does not go looking for one either.
    const { container } = render(
      <CredentialList credentials={[{ ...verified, registration_number: 'KSNC/2019/12345' }]} />,
    )
    expect(container.textContent).not.toContain('KSNC/2019/12345')
  })

  it('marks an expired credential rather than hiding it', () => {
    render(<CredentialList credentials={[{ ...verified, expired: true }]} />)
    expect(screen.getByText('Expired')).toBeInTheDocument()
  })

  it('says plainly when there is nothing on file', () => {
    render(<CredentialList credentials={[]} />)
    expect(screen.getByText(/No verified credentials/)).toBeInTheDocument()
  })
})
