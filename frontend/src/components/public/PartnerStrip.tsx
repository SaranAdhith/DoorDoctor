import { Building2, FlaskConical, Hospital, Users } from 'lucide-react'

import { PARTNERS, PARTNER_KIND_LABELS, type PartnerKind } from '../../content/social-proof'

/**
 * Who DoorDoctor works with.
 *
 * Wordmark tiles, not logo images. Partly because the repo has no logo assets,
 * mostly because reproducing another organisation's mark is the part of a
 * "trusted by" strip that needs a signed agreement behind it.
 *
 * **The names in `content/social-proof.ts` are invented on purpose** — see that
 * file's header before replacing them with real ones.
 *
 * Each tile says what the tie-up actually covers. A row of names with no stated
 * relationship invites a family to assume a clinical one, which in an emergency
 * is the assumption that hurts.
 */

const ICONS: Record<PartnerKind, typeof Hospital> = {
  hospital: Hospital,
  diagnostics: FlaskConical,
  employer: Building2,
  residence: Users,
}

export function PartnerStrip() {
  if (PARTNERS.length === 0) return null

  return (
    <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {PARTNERS.map((partner, i) => {
        const Icon = ICONS[partner.kind]
        return (
          <div
            key={`${partner.name}-${i}`}
            className="flex gap-4 rounded-2xl border border-border-subtle bg-surface-raised p-5 transition-colors hover:border-brand-200"
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
              <Icon className="h-5 w-5" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="text-caption font-semibold uppercase tracking-[0.12em] text-brand-700">
                {PARTNER_KIND_LABELS[partner.kind]}
              </p>
              <p className="mt-0.5 text-body font-semibold text-text-primary">{partner.name}</p>
              <p className="mt-1 text-small text-text-secondary">{partner.note}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
