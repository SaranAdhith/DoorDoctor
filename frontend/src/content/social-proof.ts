/**
 * ============================================================================
 *  PLACEHOLDER CONTENT — REPLACE EVERY ENTRY BELOW BEFORE LAUNCH.
 * ============================================================================
 *
 * `docs/build-log/STATE.md` locks the rule this file bends: *"Invent no
 * traction, testimonials, customer counts, certifications or partner logos —
 * DoorDoctor is pre-launch."* The reviews and tie-up sections were built anyway,
 * on an explicit instruction, so the finished design exists and can be judged.
 * What is here is scaffolding, not copy.
 *
 * Every entry carries `placeholder: true`. While that flag is on an entry, the
 * section renders a visible "not real yet" notice above it, so nothing on this
 * site can present sample text as a genuine endorsement. Delete the flag when
 * you paste in the real thing and the notice clears itself — there is no second
 * switch to remember.
 *
 * Before any of this goes in front of a paying family:
 *
 *   REVIEWS   — a quote needs the person's written consent to be published,
 *               with their name and the detail they agreed to. A review about
 *               a named relative's health is personal data; consent for it is
 *               not implied by them having said something nice on a call.
 *               Do not add star ratings you did not collect through a real
 *               review process, and do not emit `aggregateRating` structured
 *               data (see `Seo.tsx`) — that puts a rating into Google's index
 *               as a factual claim.
 *
 *   PARTNERS  — list an organisation only where a signed agreement exists, and
 *               only in the form that agreement permits. Using a hospital's
 *               name or mark without one is a trademark problem and implies a
 *               clinical relationship a family may rely on in an emergency.
 *
 * Misleading endorsements in Indian advertising fall under the ASCI code and
 * the Consumer Protection Act 2019 (§2(28), misleading advertisement), and a
 * healthcare service is exactly where that is enforced hardest.
 *
 * To hide both sections entirely — the honest pre-launch state — set
 * `SHOW_SOCIAL_PROOF` to `false`. Nothing else needs to change.
 */

/** Master switch for the reviews and tie-up bands on the home page. */
export const SHOW_SOCIAL_PROOF = true

export interface Review {
  /** The quote itself. One or two sentences reads best in the card. */
  quote: string
  /** Who said it, as they agreed to be named. */
  name: string
  /** Their relationship to the patient, and the area. "Daughter · HSR Layout". */
  context: string
  /** 1–5. Only set this if it came from a real review process. */
  rating: number
  /** Remove once this entry is a real, consented quote. */
  placeholder?: boolean
}

export const REVIEWS: readonly Review[] = [
  {
    quote:
      'Placeholder quote. Replace with a real sentence from a family about something they could ' +
      'see that they could not see before — roughly this length, in their own words.',
    name: 'Family member’s name',
    context: 'Relationship · Area',
    rating: 5,
    placeholder: true,
  },
  {
    quote:
      'Placeholder quote. The most useful reviews name the specific thing that changed: a reading ' +
      'that was caught, a week they did not have to chase anyone for an update.',
    name: 'Family member’s name',
    context: 'Relationship · Area',
    rating: 5,
    placeholder: true,
  },
  {
    quote:
      'Placeholder quote. Keep one that is measured rather than glowing — a page of five-star ' +
      'superlatives reads as bought, and families choosing elder care are reading carefully.',
    name: 'Family member’s name',
    context: 'Relationship · Country, for an NRI family',
    rating: 4,
    placeholder: true,
  },
]

export type PartnerKind = 'hospital' | 'employer' | 'diagnostics' | 'residence'

export interface Partner {
  /** The organisation's name, exactly as the agreement permits it to appear. */
  name: string
  kind: PartnerKind
  /** What the tie-up actually covers. Be specific; vagueness reads as filler. */
  note: string
  /** Remove once a signed agreement exists. */
  placeholder?: boolean
}

export const PARTNER_KIND_LABELS: Record<PartnerKind, string> = {
  hospital: 'Hospital',
  diagnostics: 'Diagnostics',
  employer: 'Employer',
  residence: 'Residence',
}

export const PARTNERS: readonly Partner[] = [
  {
    name: 'Partner hospital',
    kind: 'hospital',
    note: 'Where an escalation is handed over, and who receives the patient’s record when it is.',
    placeholder: true,
  },
  {
    name: 'Partner hospital',
    kind: 'hospital',
    note: 'Second escalation route, so a single hospital being full is not a single point of failure.',
    placeholder: true,
  },
  {
    name: 'Diagnostics lab',
    kind: 'diagnostics',
    note: 'Home sample collection for the blood panels included in a plan.',
    placeholder: true,
  },
  {
    name: 'Employer',
    kind: 'employer',
    note: 'Elder care offered to employees as a benefit, billed to the company.',
    placeholder: true,
  },
  {
    name: 'Employer',
    kind: 'employer',
    note: 'Covering parents of staff working outside the city.',
    placeholder: true,
  },
  {
    name: 'Senior residence',
    kind: 'residence',
    note: 'Clinical monitoring for every resident, priced per resident per day.',
    placeholder: true,
  },
]

/** True while any entry in the list is still scaffolding. */
export function hasPlaceholders(items: readonly { placeholder?: boolean }[]): boolean {
  return items.some((item) => item.placeholder === true)
}
