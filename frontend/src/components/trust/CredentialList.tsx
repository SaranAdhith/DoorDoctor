import { BadgeCheck, ShieldAlert } from 'lucide-react'

import { Badge } from '../ui'
import { formatDate } from '../../lib/format'
import type { NurseCredential } from '../../types'

/**
 * A nurse's credentials as a family reads them (§4.10).
 *
 * Every row says **who** verified it and **when**. That sentence is the feature:
 * a tick with nobody's name against it is a badge the platform awarded itself,
 * and the backend refuses to produce one — a credential is only `is_verified`
 * with a verifier and a date on it.
 *
 * There is no registration number here because the family projection does not
 * contain the field at all.
 */
export function CredentialList({ credentials }: { credentials: NurseCredential[] }) {
  if (credentials.length === 0) {
    return (
      <p className="text-small text-text-secondary">
        No verified credentials are on file for this nurse yet.
      </p>
    )
  }

  return (
    <ul className="space-y-3">
      {credentials.map((credential) => (
        <li
          key={credential.id}
          className="flex items-start gap-3 rounded-lg border border-border-subtle bg-surface p-3"
        >
          <span className="mt-0.5 text-status-good" aria-hidden>
            {credential.expired ? <ShieldAlert className="h-5 w-5" /> : <BadgeCheck className="h-5 w-5" />}
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-medium text-text-primary">{credential.title}</p>
            <p className="text-small text-text-secondary">{credential.issuing_body}</p>
            {credential.verified_at && credential.verified_by_name && (
              <p className="mt-1 text-caption text-text-muted">
                Checked by {credential.verified_by_name} on {formatDate(credential.verified_at)}
              </p>
            )}
          </div>
          {credential.expired && <Badge tone="attention">Expired</Badge>}
        </li>
      ))}
    </ul>
  )
}
