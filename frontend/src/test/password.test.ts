import { describe, expect, it } from 'vitest'

import { passwordProblem, passwordStrength } from '../lib/password'

/**
 * These cases are the same ones `backend/tests/test_password_reset.py` asserts
 * against the server. If the two rules drift, one of these files fails.
 */
describe('passwordProblem', () => {
  it('accepts a password with a letter, a number and enough length', () => {
    expect(passwordProblem('Demo@123')).toBeNull()
    expect(passwordProblem('Fresh@2026pass')).toBeNull()
  })

  it('rejects a short password', () => {
    expect(passwordProblem('Ab1')).toBe('Password must be at least 8 characters.')
  })

  it('rejects a password with no number', () => {
    expect(passwordProblem('onlyletters')).toBe('Password must include at least one number.')
  })

  it('rejects a password with no letter', () => {
    expect(passwordProblem('12345678')).toBe('Password must include at least one letter.')
  })

  it('rejects a password past the bcrypt-safe cap', () => {
    expect(passwordProblem(`a1${'x'.repeat(200)}`)).toBe('Password must be at most 128 characters.')
  })
})

describe('passwordStrength', () => {
  it('rates a long mixed-case password with a symbol as strong', () => {
    expect(passwordStrength('Monsoon@Koramangala7')).toBe('strong')
  })

  it('rates a short but varied password as fair', () => {
    expect(passwordStrength('Demo@123')).toBe('fair')
  })

  it('rates a plain lowercase-and-digits password as weak', () => {
    expect(passwordStrength('bangalore12')).toBe('weak')
  })
})
