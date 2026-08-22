/**
 * Mirror of `backend/app/core/security.password_problem`.
 *
 * This exists so the user finds out about a weak password while typing rather
 * than after a round trip. The server is still the authority — it re-checks
 * every submission and this file is never trusted.
 */

export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 128
export const PASSWORD_RULE = 'At least 8 characters, including one letter and one number.'

/** Why the password is unacceptable, or null when it is fine. */
export function passwordProblem(password: string): string | null {
  if (password.length < PASSWORD_MIN_LENGTH) return 'Password must be at least 8 characters.'
  if (password.length > PASSWORD_MAX_LENGTH) return 'Password must be at most 128 characters.'
  if (!/[a-zA-Z]/.test(password)) return 'Password must include at least one letter.'
  if (!/[0-9]/.test(password)) return 'Password must include at least one number.'
  return null
}

export type PasswordStrength = 'weak' | 'fair' | 'strong'

/**
 * A rough four-signal score, shown only once the password already passes the
 * rule — it is encouragement, never a gate. Nothing here is sent anywhere.
 */
export function passwordStrength(password: string): PasswordStrength {
  const signals = [
    password.length >= 12,
    /[a-z]/.test(password) && /[A-Z]/.test(password),
    /[0-9]/.test(password),
    /[^a-zA-Z0-9]/.test(password),
  ].filter(Boolean).length

  if (signals >= 4) return 'strong'
  if (signals === 3) return 'fair'
  return 'weak'
}
